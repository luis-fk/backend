from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent

from plants.chatbot.schemas import ChatInfo, Routing, SquadState
from plants.models import ChatHistory, UserMemory

load_dotenv()

llm_personality = "You are a web search assistant. Retrieve accurate and relevant information based on the user query."


class LLM:
    def __init__(self):
        self.user_id: str = None
        self.llm: ChatOpenAI = None
        self.user_memory: str = None
        self.user_message: str = None
        self.llm_response: str = None
        self.graph: StateGraph = None
        self.routing_llm: ChatOpenAI = None
        self.user_info_llm: ChatOpenAI = None
        self.web_search_llm: ChatOpenAI = None
        self.chat_history: list[BaseMessage] = None

    def setup(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini")

        self.web_search_llm = create_react_agent(
            self.llm,
            [TavilySearchResults(max_results=2)],
            state_modifier=SystemMessage(content=llm_personality),
        )
        self.routing_llm = self.llm.with_structured_output(
            Routing, method="json_schema"
        )
        self.user_info_llm = self.llm.with_structured_output(
            ChatInfo, method="json_schema"
        )

        self.graph = self.build_graph()

    def process_message(self, message: str, user_id: str) -> str:
        try:
            self.user_memory = UserMemory.objects.get(user_id=user_id).memory
        except UserMemory.DoesNotExist:
            self.user_memory = None

        human_messages = ChatHistory.objects.filter(
            user_id=user_id, role="human"
        ).order_by("id")[:5]
        ai_messages = ChatHistory.objects.filter(user_id=user_id, role="ai").order_by(
            "id"
        )[:5]
        chat_history = []

        for human, ai in zip(human_messages, ai_messages):
            chat_history.append(HumanMessage(content=human.message))
            chat_history.append(AIMessage(content=ai.message))

        print(chat_history)
        self.user_id = user_id
        self.user_message = message
        self.graph.invoke(
            input={
                "messages": chat_history + [HumanMessage(content=message)],
                "memory": self.user_memory,
            }
        )
        return self.llm_response

    def route_picker(self, state: SquadState):
        if state["route"] in ["web_search", "continue"]:
            return state["route"]
        else:
            raise ValueError(
                f"Invalid route '{state['route']}'. Supported routes are 'end', 'web_search' and 'continue'."
            )

    def wrap_up(self, state: SquadState) -> None:
        UserMemory.objects.update_or_create(
            user_id=self.user_id,
            defaults={"user_id": self.user_id, "memory": state["memory"]},
        )

        ChatHistory.objects.create(
            user_id=self.user_id,
            message=state["messages"][-2].content,
            role="human",
        )

        self.llm_response = state["messages"][-1].content
        ChatHistory.objects.create(
            user_id=self.user_id,
            message=self.llm_response,
            role="ai",
        )

    def update_memory(self, state: SquadState) -> SquadState:
        messages = state["messages"]
        llm_response = self.user_info_llm.invoke(
            [
                SystemMessage(
                    content=(
                        "Summarize the conversation so far, including the latest messages. "
                        "Add or update any relevant user information while retaining existing "
                        "details."
                    )
                )
            ]
            + messages
        )

        return {
            "messages": state["messages"],
            "memory": llm_response.info,
            "route": state["route"],
        }

    def router(self, state: SquadState) -> SquadState:
        response = self.routing_llm.invoke(state["messages"])
        return {
            "route": response.route,
        }

    def call_agent(self, state: SquadState) -> SquadState:
        memory = state["memory"] if state["memory"] else []
        llm_response = self.llm.invoke(
            state["messages"] + [SystemMessage(content=memory)]
        )

        return {"messages": [llm_response]}

    def web_search_agent(self, state: SquadState) -> str:
        llm_response = self.web_search_llm.invoke(
            {
                "messages": state["messages"][-1].content,
            }
        )

        return {"messages": [AIMessage(content=llm_response["messages"][-1].content)]}

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(SquadState)

        workflow.set_entry_point("router")

        workflow.add_node("agent", self.call_agent)
        workflow.add_node("router", self.router)
        workflow.add_node("web_search_agent", self.web_search_agent)
        workflow.add_node("update_memory", self.update_memory)
        workflow.add_node("wrap_up", self.wrap_up)

        workflow.add_conditional_edges(
            "router",
            self.route_picker,
            {
                "continue": "agent",
                "web_search": "web_search_agent",
                "update_memory": "update_memory",
            },
        )

        workflow.add_edge("update_memory", "wrap_up")
        workflow.add_edge("agent", "update_memory")
        workflow.add_edge("web_search_agent", "update_memory")

        workflow.set_finish_point("wrap_up")

        return workflow.compile()
