from django.utils import timezone
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from plants.api.chatbot.prompts import (
    CHAT_BOT_AGENT_PROMPT,
    ROUTER_AGENT_PROMPT,
    TOOLS_AGENT_PROMPT,
    USER_INFO_AGENT_PROMPT,
)
from plants.api.chatbot.schemas import ChatInfo, LLMAnswerSchema, Routing
from plants.api.chatbot.tools import TOOLS
from plants.api.sensors.summary import LOCAL_TIME

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
llm_4_with_tools = llm_4.bind_tools(TOOLS)


def now_in_sao_paulo() -> str:
    """The current time as the tools give theirs: in São Paulo's zone."""
    now = timezone.localtime(timezone.now(), LOCAL_TIME)
    return now.strftime("%Y-%m-%d %H:%M") + " (São Paulo time)"


def call_router_agent(messages: list[BaseMessage]) -> Routing:
    """Routes the latest message, with the ones before it as context: a follow-up
    like "and over 7 days?" names no plant."""
    chain = ROUTER_AGENT_PROMPT | llm_4.with_structured_output(
        schema=Routing, method="json_schema"
    )
    response = chain.invoke({"conversation": messages})
    return Routing.model_validate(response)


def call_user_info_agent(messages: list[BaseMessage]) -> ChatInfo:
    chain = USER_INFO_AGENT_PROMPT | llm_4.with_structured_output(
        schema=ChatInfo, method="json_schema"
    )
    response = chain.invoke({"input": messages})
    return ChatInfo.model_validate(response)


def call_chatbot_agent(messages: list[BaseMessage], memory: str) -> LLMAnswerSchema:
    chain = CHAT_BOT_AGENT_PROMPT | llm_4.with_structured_output(
        schema=LLMAnswerSchema, method="json_schema"
    )
    response = chain.invoke(
        {"date": now_in_sao_paulo(), "user_memory": memory, "input": messages}
    )
    return LLMAnswerSchema.model_validate(response)


def call_tools_agent(message: HumanMessage, memory: str) -> BaseMessage:
    prompt = TOOLS_AGENT_PROMPT.invoke(
        {
            "input": message.content,
            "date": now_in_sao_paulo(),
            "user_memory": memory,
            "agent_scratchpad": "",
        }
    )
    return llm_4_with_tools.invoke(prompt)


def call_tool_response_agent(
    messages: list[BaseMessage], memory: str, allow_tools: bool
) -> BaseMessage:
    """Answers from the tool results; with allow_tools, the model may first ask for
    more, such as each plant's readings after the list of plants."""
    chain = TOOLS_AGENT_PROMPT | (llm_4_with_tools if allow_tools else llm_4)
    return chain.invoke(
        {
            "input": messages,
            "date": now_in_sao_paulo(),
            "user_memory": memory,
            "agent_scratchpad": "",
        }
    )
