from datetime import datetime
from typing import cast

from langchain import hub
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from plants.api.chatbot.schemas import ChatInfo, LLMAnswerSchema, Routing
from plants.api.chatbot.tools import web_search

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def call_router_agent(
    message: HumanMessage,
) -> Routing:
    instructions = hub.pull("router-agent-prompt")

    chain = instructions | llm_4.with_structured_output(
        schema=Routing, method="json_schema"
    )

    response = chain.invoke({"input": message})

    return Routing.model_validate(response)


def call_user_info_agent(
    messages: list[BaseMessage],
) -> ChatInfo:
    instructions = hub.pull("user-info-agent-prompt")

    chain = instructions | llm_4.with_structured_output(
        schema=ChatInfo, method="json_schema"
    )

    response = chain.invoke({"input": messages})

    return ChatInfo.model_validate(response)


def call_chatbot_agent(messages: list[BaseMessage], memory: str) -> LLMAnswerSchema:
    instructions = hub.pull("chat-bot-agent-prompt")

    user_memory = memory if memory else ""

    chain = instructions | llm_4.with_structured_output(
        schema=LLMAnswerSchema, method="json_schema"
    )

    response = chain.invoke(
        {"date": datetime.now(), "user_memory": user_memory, "input": messages}
    )

    return LLMAnswerSchema.model_validate(response)


def call_tools_agent(message: HumanMessage, memory: str) -> str:
    instructions = hub.pull("tools-agent-prompt")

    tools = [web_search]
    agent = create_tool_calling_agent(llm_4, tools, prompt=instructions)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    response = agent_executor.invoke(
        {
            "input": message.content,
            "date": datetime.now(),
            "user_memory": memory,
            "agent_scratchpad": "",
        }
    )

    return cast(str, response["output"])
