import json
import logging

from langchain_core.messages import BaseMessage, HumanMessage, ToolCall, ToolMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.tools import BaseTool

from political_culture.api.chatbot import prompts
from political_culture.api.chatbot import tools as chatbot_tools
from political_culture.api.chatbot.schemas import ChatInfo, Routing
from political_culture.api.utils import llm_4

logger = logging.getLogger(__name__)

# Room for the text analysis, which searches a text several times in a row.
MAX_TOOL_ROUNDS = 8


def _answer_with_tools(messages: list[BaseMessage], tools: list[BaseTool]) -> str:
    """Asks the model, runs the tools it calls and asks again with their results,
    until it answers without calling tools. After MAX_TOOL_ROUNDS it has to answer
    with what it has."""
    messages = list(messages)
    llm_with_tools = llm_4.bind_tools(tools)
    tools_by_name = {tool.name: tool for tool in tools}

    for _ in range(MAX_TOOL_ROUNDS):
        response = llm_with_tools.invoke(messages)
        if not response.tool_calls and not response.invalid_tool_calls:
            return str(response.content)
        messages.append(response)
        for call in response.tool_calls:
            messages.append(_run_tool(tools_by_name.get(call["name"]), call))
        # Every call the answer lists needs a reply, or OpenAI refuses the next request.
        for invalid in response.invalid_tool_calls:
            messages.append(
                ToolMessage(
                    f"Error: invalid arguments ({invalid['error']})",
                    tool_call_id=invalid["id"] or "",
                    status="error",
                )
            )

    final = llm_4.bind_tools(tools, tool_choice="none").invoke(messages)
    return str(final.content)


def _run_tool(tool: BaseTool | None, call: ToolCall) -> ToolMessage:
    """Runs one call and gives the model the result as JSON text: OpenAI refuses an
    empty list as content. A failure goes back as text too, so the model can carry
    on instead of the whole reply failing."""
    call_id = call["id"] or ""
    try:
        if tool is None:
            raise ValueError(f"there is no tool named {call['name']}")
        output = tool.invoke(call["args"])
    except Exception as error:
        logger.warning(f"Tool {call['name']} failed: {error}")
        return ToolMessage(f"Error: {error}", tool_call_id=call_id, status="error")
    content = json.dumps(output, ensure_ascii=False, default=str)
    return ToolMessage(content, tool_call_id=call_id)


def _invoke_tool_agent(system_prompt: str, tools: list[BaseTool], input: str) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )
    return _answer_with_tools(prompt.invoke({"input": input}).to_messages(), tools)


def word_analyist_agent(input: str, user_id: int) -> str:
    user_tools = chatbot_tools.user_tools(user_id)
    tools = [user_tools.library_texts, user_tools.word_count]
    return _invoke_tool_agent(prompts.WORD_COUNT_COMPARISON_PROMPT, tools, input)


def text_analyist_agent(input: str, user_id: int) -> str:
    user_tools = chatbot_tools.user_tools(user_id)
    tools = [user_tools.search_text, user_tools.library_texts]
    return _invoke_tool_agent(prompts.TEXT_ANALYSIS_PROMPT, tools, input)


def text_ideology_analyist_agent(input: str, user_id: int) -> str:
    tools = [
        chatbot_tools.get_ideologies,
        chatbot_tools.get_ideology_definition,
        chatbot_tools.user_tools(user_id).library_texts,
    ]
    return _invoke_tool_agent(prompts.TEXT_IDEOLOGY_ANALYSIS_PROMPT, tools, input)


def call_user_info_agent(
    message: str, chat_history: list[BaseMessage], memory: str | None
) -> ChatInfo:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(prompts.USER_INFO_PROMPT),
            HumanMessagePromptTemplate.from_template(
                "Current memory: {memory}\n\n{input} {chat_history}"
            ),
        ]
    )
    chain = instructions_prompt | llm_4.with_structured_output(
        schema=ChatInfo, method="json_schema"
    )
    response = chain.invoke(
        {"input": message, "chat_history": chat_history, "memory": memory or "none"}
    )
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


def general_chat_agent(
    input: str, chat_history: list[BaseMessage], user_id: int
) -> str:
    user_tools = chatbot_tools.user_tools(user_id)
    tools = [
        user_tools.library_texts,
        user_tools.search_text,
        user_tools.word_count,
        user_tools.submitted_texts,
        user_tools.memory,
    ]
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(prompts.GENERAL_CHAT_PROMPT),
            HumanMessagePromptTemplate.from_template("{input} {chat_history}"),
        ]
    )
    messages = instructions_prompt.invoke(
        {"input": input, "chat_history": chat_history or ""}
    ).to_messages()
    return _answer_with_tools(messages, tools)


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
