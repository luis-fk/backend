from datetime import datetime
from typing import cast

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_openai import ChatOpenAI

from plants.api.chatbot.schemas import ChatInfo, LLMAnswerSchema, Routing
from plants.api.chatbot.tools import web_search

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def call_router_agent(
    message: HumanMessage,
) -> Routing:
    instructions = (
        "You are tasked with determining whether the user's question "
        "is something you can answer yourself and would warrant a "
        "web search. If the question is something you can answer "
        "yourself, you can continue. If the question is something "
        "you can't answer yourself, you should redirect to the web search"
    )

    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(instructions),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=Routing, method="json_schema"
    )

    response = chain.invoke({"input": message})

    return Routing.model_validate(response)


def call_user_info_agent(
    messages: list[BaseMessage],
) -> ChatInfo:
    instructions = (
        "You will receive an exchange of messages between a human and an AI. "
        "Summarize the conversation so far, including the latest messages. "
        "Add or update any relevant user information while retaining existing "
        "details."
    )

    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(instructions),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=ChatInfo, method="json_schema"
    )

    response = chain.invoke({"input": messages})

    return ChatInfo.model_validate(response)


def call_chatbot_agent(messages: list[BaseMessage], memory: str) -> LLMAnswerSchema:
    instructions = (
        "You are a plants expert, you will receive details about a conversation "
        "between a human and an AI and other summarized relevant information about the conversation "
        "and the user so far. You will analyze the conversation and provide relevant "
        "and accurate information to the user. Respond in a friendly and helpful manner. "
        "Do not send any links or markdown text in your answer, use plaintext only.\n"
        f"The current date is {datetime.now()}.\n"
    )

    system_prompt = instructions + memory
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=LLMAnswerSchema, method="json_schema"
    )

    response = chain.invoke({"input": messages})

    return LLMAnswerSchema.model_validate(response)


def call_tools_agent(message: HumanMessage, memory: str) -> str:
    instructions = (
        "You are a plants expert, you will receive details about a conversation "
        "between a human and an AI and other summarized relevant information about the conversation "
        "and the user so far. You will analyze the conversation and provide relevant "
        "and accurate information to the user. To do that you have several tools to use at your disposal. "
        "Respond in a friendly and helpful manner. DO NOT send any LINKS or MARKDOWN text in your "
        "answer, use plaintext only.\n"
        "You have access to the following tools:\n"
        "web_search: Use this to fetch info for things you can't answer yourself, for instance, "
        "information about plants, the current weather or other things. "
        f"The current date is {datetime.now()}.\n"
    )

    system_prompt = instructions + memory
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template("{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    tools = [web_search]
    agent = create_tool_calling_agent(llm_4, tools, prompt=instructions_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    response = agent_executor.invoke({"input": message.content})

    return cast(str, response["output"])
