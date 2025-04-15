from langchain import hub
from langchain_openai import ChatOpenAI

from political_culture.api.word_counter.schemas import TitleAndAuthorSchema

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def call_title_and_author_extractor_agent(text: str) -> TitleAndAuthorSchema:
    instructions = hub.pull("extract_title_and_author")

    chain = instructions | llm_4.with_structured_output(
        schema=TitleAndAuthorSchema, method="json_schema"
    )
    
    response = chain.invoke({"input": text})

    return TitleAndAuthorSchema.model_validate(response)
