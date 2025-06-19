from typing import cast

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from political_culture.api.chatbot import tools as chatbot_tools
from political_culture.api.chatbot.prompts import (
    GENERAL_CHAT_PROMPT,
    ROUTER_PROMPT,
    TEXT_ANALYSIS_PROMPT,
    TEXT_IDEOLOGY_ANALYSIS_PROMPT,
    USER_INFO_PROMPT,
    WORD_COUNT_COMPARISON_PROMPT,
)
from political_culture.api.chatbot.schemas import ChatInfo, Routing
from political_culture.api.utils import llm_4
from political_culture.api.word_counter.tools import query_vectors


def word_analyist_agent(input: str) -> str:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(WORD_COUNT_COMPARISON_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template("{agent_scratchpad}"),
        ]
    )

    tools = [
        chatbot_tools.get_all_texts_info,
        chatbot_tools.get_text_word_count_by_id,
    ]
    agent = create_tool_calling_agent(llm_4, tools, prompt=instructions_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    response = agent_executor.invoke(
        {
            "input": input,
            "agent_scratchpad": "",
        }
    )

    return cast(str, response["output"])


def text_analyist_agent(input: str) -> str:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(TEXT_ANALYSIS_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template("{agent_scratchpad}"),
        ]
    )

    tools = [
        query_vectors,
        chatbot_tools.get_all_texts_info,
    ]
    agent = create_tool_calling_agent(llm_4, tools, prompt=instructions_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    response = agent_executor.invoke(
        {
            "input": input,
            "agent_scratchpad": "",
        }
    )

    return cast(str, response["output"])


def text_ideology_analyist_agent(input: str) -> str:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(TEXT_IDEOLOGY_ANALYSIS_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template("{agent_scratchpad}"),
        ]
    )

    tools = [
        chatbot_tools.get_ideologies,
        chatbot_tools.get_ideology_definition,
        chatbot_tools.get_all_texts_info,
    ]
    agent = create_tool_calling_agent(llm_4, tools, prompt=instructions_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    response = agent_executor.invoke(
        {
            "input": input,
            "agent_scratchpad": "",
        }
    )

    return cast(str, response["output"])


def call_user_info_agent(message: str, chat_history: list[BaseMessage]) -> ChatInfo:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(USER_INFO_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}, {chat_history}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=ChatInfo, method="json_schema"
    )

    response = chain.invoke({"input": message, "chat_history": chat_history})

    return ChatInfo.model_validate(response)


def call_router_agent(message: HumanMessage) -> Routing:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(ROUTER_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=Routing, method="json_schema"
    )

    response = chain.invoke({"input": message})

    return Routing.model_validate(response)


def general_chat_agent(input: str, chat_history: list[BaseMessage]) -> str:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(GENERAL_CHAT_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}, {chat_history}"),
            AIMessagePromptTemplate.from_template("{agent_scratchpad}"),
        ]
    )

    tools = [
        query_vectors,
        chatbot_tools.get_user_submitted_texts_info,
        chatbot_tools.get_text_word_count_by_id,
        chatbot_tools.get_recent_chat_history,
        chatbot_tools.get_user_memory,
    ]
    agent = create_tool_calling_agent(llm_4, tools, prompt=instructions_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    response = agent_executor.invoke(
        {
            "input": input,
            "chat_history": chat_history,
            "agent_scratchpad": "",
        }
    )

    return cast(str, response["output"])
