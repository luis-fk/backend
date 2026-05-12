from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from plants.api.chatbot.prompts import (
    CHAT_BOT_AGENT_PROMPT,
    ROUTER_AGENT_PROMPT,
    TOOLS_AGENT_PROMPT,
    USER_INFO_AGENT_PROMPT,
)
from plants.api.chatbot.schemas import ChatInfo, LLMAnswerSchema, Routing
from plants.api.chatbot.tools import web_search

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
llm_4_with_tools = llm_4.bind_tools([web_search])


def call_router_agent(message: HumanMessage) -> Routing:
    chain = ROUTER_AGENT_PROMPT | llm_4.with_structured_output(
        schema=Routing, method="json_schema"
    )
    response = chain.invoke({"input": message})
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
        {"date": datetime.now(), "user_memory": memory, "input": messages}
    )
    return LLMAnswerSchema.model_validate(response)


def call_tools_agent(message: HumanMessage, memory: str) -> BaseMessage:
    prompt = TOOLS_AGENT_PROMPT.invoke(
        {
            "input": message.content,
            "date": datetime.now(),
            "user_memory": memory,
            "agent_scratchpad": "",
        }
    )
    return llm_4_with_tools.invoke(prompt)


def call_tool_response_agent(messages: list[BaseMessage], memory: str) -> BaseMessage:
    chain = TOOLS_AGENT_PROMPT | llm_4
    return chain.invoke(
        {
            "input": messages,
            "date": datetime.now(),
            "user_memory": memory,
            "agent_scratchpad": "",
        }
    )
