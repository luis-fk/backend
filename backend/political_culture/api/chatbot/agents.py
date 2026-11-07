from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from political_culture.api.chatbot import prompts
from political_culture.api.chatbot import tools as chatbot_tools
from political_culture.api.chatbot.schemas import ChatInfo, Routing
from political_culture.api.utils import llm_4
from political_culture.api.word_counter.tools import query_vectors


def _make_tool_prompt(system_prompt: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template("{agent_scratchpad}"),
        ]
    )


def _invoke_tool_agent(prompt: ChatPromptTemplate, tools: list[Any], input: str) -> str:
    llm_with_tools = llm_4.bind_tools(tools)
    messages = prompt.invoke({"input": input, "agent_scratchpad": ""})
    response = llm_with_tools.invoke(messages)
    return str(response.content)


def word_analyist_agent(input: str) -> str:
    tools = [
        chatbot_tools.get_all_texts_info,
        chatbot_tools.get_text_word_count_by_id,
    ]
    return _invoke_tool_agent(
        _make_tool_prompt(prompts.WORD_COUNT_COMPARISON_PROMPT), tools, input
    )


def text_analyist_agent(input: str) -> str:
    tools = [
        query_vectors,
        chatbot_tools.get_all_texts_info,
    ]
    return _invoke_tool_agent(
        _make_tool_prompt(prompts.TEXT_ANALYSIS_PROMPT), tools, input
    )


def text_ideology_analyist_agent(input: str) -> str:
    tools = [
        chatbot_tools.get_ideologies,
        chatbot_tools.get_ideology_definition,
        chatbot_tools.get_all_texts_info,
    ]
    return _invoke_tool_agent(
        _make_tool_prompt(prompts.TEXT_IDEOLOGY_ANALYSIS_PROMPT), tools, input
    )


def call_user_info_agent(message: str, chat_history: list[BaseMessage]) -> ChatInfo:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(prompts.USER_INFO_PROMPT),
            HumanMessagePromptTemplate.from_template("{input} {chat_history}"),
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
            SystemMessagePromptTemplate.from_template(prompts.ROUTER_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )
    chain = instructions_prompt | llm_4.with_structured_output(
        schema=Routing, method="json_schema"
    )
    response = chain.invoke({"input": message})
    return Routing.model_validate(response)


def general_chat_agent(input: str, chat_history: list[BaseMessage]) -> str:
    tools = [
        query_vectors,
        chatbot_tools.get_user_submitted_texts_info,
        chatbot_tools.get_text_word_count_by_id,
        chatbot_tools.get_recent_chat_history,
        chatbot_tools.get_user_memory,
    ]
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(prompts.GENERAL_CHAT_PROMPT),
            HumanMessagePromptTemplate.from_template("{input} {chat_history}"),
            AIMessagePromptTemplate.from_template("{agent_scratchpad}"),
        ]
    )
    llm_with_tools = llm_4.bind_tools(tools)
    messages = instructions_prompt.invoke(
        {"input": input, "chat_history": chat_history or "", "agent_scratchpad": ""}
    )
    response = llm_with_tools.invoke(messages)
    return str(response.content)


def call_text_concatenation_agent(input: str) -> str:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(prompts.MERGE_RESPONSES_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )
    chain = instructions_prompt | llm_4
    response = chain.invoke({"input": input})
    return str(response.content)
