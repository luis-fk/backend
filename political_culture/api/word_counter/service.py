import logging
import os
import re
import tempfile
from collections import Counter
from typing import IO, Optional, cast

from environ import Env
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_core.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from political_culture.api.utils import llm_4
from political_culture.api.word_counter.prompts import (
    STRUCTURED_OUTPUT_PROMPT,
    TEXT_INFO_EXTRACTION_PROMPT,
    WORD_EXTRACTION_PROMPT,
)
from political_culture.api.word_counter.schemas import (
    TitleAndAuthorSchema,
    WordFrequencySquema,
)
from political_culture.api.word_counter.tools import query_vectors
from political_culture.models import TextChunks, Texts, TextWordCount

env = Env()
Env.read_env()


def text_info_extractor(text_id: int) -> str:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(TEXT_INFO_EXTRACTION_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template("{agent_scratchpad}"),
        ]
    )

    tools = [query_vectors]
    agent = create_tool_calling_agent(llm_4, tools, prompt=instructions_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    response = agent_executor.invoke(
        {
            "input": text_id,
            "agent_scratchpad": "",
        }
    )

    return cast(str, response["output"])


def structured_text_info_extractor(content_description: str) -> TitleAndAuthorSchema:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(STRUCTURED_OUTPUT_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=TitleAndAuthorSchema, method="json_schema"
    )

    response = chain.invoke({"input": content_description})

    return TitleAndAuthorSchema.model_validate(response)


def word_picker(
    words: list[tuple[str, int]], content_description: str | None
) -> WordFrequencySquema:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(WORD_EXTRACTION_PROMPT),
            AIMessagePromptTemplate.from_template("{input}, {content_description}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=WordFrequencySquema, method="json_schema"
    )

    response = chain.invoke(
        {"input": words, "content_description": content_description}
    )

    return WordFrequencySquema.model_validate(response)


def count_words(text: str) -> tuple[list[tuple[str, int]], int]:
    all_words = re.findall(r"\w+", text.lower())

    words = [word for word in all_words if len(word) > 2]

    word_counts = Counter(words)

    sorted_word_counts = sorted(
        word_counts.items(), key=lambda item: item[1], reverse=True
    )

    total_word_count = sum(word_counts.values())

    return sorted_word_counts, total_word_count


def add_text(
    content: IO, user_id: int, *, user_submitted_text: Optional[bool] = False
) -> Texts:
    text, chunk_texts, vectors = extract_pdf_embeddings_and_metadata(content)

    logging.info("Adding text to the database")

    text_db = Texts.objects.create(
        user_id=user_id,
        text=text,
        user_submitted_text=bool(user_submitted_text),
    )

    for vector, chunk_text in zip(vectors, chunk_texts):
        TextChunks.objects.create(text=text_db, chunk_text=chunk_text, vector=vector)

    content_description = text_info_extractor(text_db.pk)

    structured_content = structured_text_info_extractor(content_description)

    text_db.title = structured_content.title
    text_db.author = structured_content.author
    text_db.content_description = structured_content.content_description

    text_db.save()

    return text_db


def add_text_word_count(text_db: Texts) -> TextWordCount:
    word_frequencies, total_word_count = count_words(text_db.text)

    new_word_frequencies = word_picker(word_frequencies, text_db.content_description)

    dict_word_frequencies = dict(
        (word_count.word, word_count.count)
        for word_count in new_word_frequencies.words_list
    )

    return TextWordCount.objects.create(
        text=text_db,
        total_word_count=total_word_count,
        word_frequencies=dict_word_frequencies,
    )


def extract_pdf_embeddings_and_metadata(
    content: IO,
) -> tuple[str, list[str], list[list[float]]]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content.read())
        tmp.flush()
        tmp_path = tmp.name

    loader = PyPDFLoader(tmp_path)
    pages = loader.load()

    text = "".join(page.page_content for page in pages)

    chunk_texts, vector = get_embeddings(pages)

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    return text, chunk_texts, vector


def get_embeddings(pages: list[Document]) -> tuple[list[str], list[list[float]]]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=2500, chunk_overlap=250)
    chunks = splitter.split_documents(pages)

    chunk_texts = [chunk.page_content for chunk in chunks]

    embeddings = OpenAIEmbeddings()

    vectors: list[list[float]] = []

    batch_size = 100
    for i in range(0, len(chunk_texts), batch_size):
        batch_texts = chunk_texts[i : i + batch_size]
        batch_vectors = embeddings.embed_documents(batch_texts)
        vectors.extend(batch_vectors)

    return chunk_texts, vectors
