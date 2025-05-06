from typing import cast

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_openai import ChatOpenAI

from political_culture.api.chatbot import tools as chatbot_tools
from political_culture.api.chatbot.prompts import (
    TEXT_TECHNICAL_ANALYSIS_PROMPT,
    USER_INFO_PROMPT,
)
from political_culture.api.chatbot.schemas import ChatInfo

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def text_analyist_agent(
    input: str,
) -> str:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(TEXT_TECHNICAL_ANALYSIS_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template("{agent_scratchpad}"),
        ]
    )

    tools = [
        chatbot_tools.get_all_texts_info,
        chatbot_tools.get_text_by_id,
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


def call_user_info_agent(
    message: str,
) -> ChatInfo:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(USER_INFO_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=ChatInfo, method="json_schema"
    )

    response = chain.invoke({"input": message})

    return ChatInfo.model_validate(response)
