import re
from collections import Counter

from django.db import router, transaction
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
    TEXT_INFO_EXTRACTION_PROMPT,
    WORD_EXTRACTION_PROMPT,
)
from political_culture.api.word_counter.schemas import (
    TitleAndAuthorSchema,
    WordFrequencySquema,
)
from political_culture.models import (
    AUTHOR_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    TextChunks,
    Texts,
    TextWordCount,
)

# Enough for a title page, a table of contents and the start of an introduction.
OPENING_CHARS = 8000
SAMPLED_PASSAGES = 3
# A book has tens of thousands of different words. Its most frequent ones are enough
# to pick from, and keep the call small.
MAX_PICKER_WORDS = 2000


class NoText(Exception):
    """The PDF has no text to read, like a scan without OCR."""


def fit(value: str | None, max_length: int) -> str | None:
    """A value the model wrote, cut to its column: PostgreSQL refuses a longer one,
    which would lose a reading already paid for."""
    return value[:max_length] if value else value


def readable(text: str) -> str:
    """PyPDF's text as PostgreSQL takes it: without NUL characters, and with the
    halves of the surrogate pairs some math fonts produce rejoined, or replaced
    when alone."""
    text = text.replace("\x00", "")
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def extract_text_info(text: str) -> TitleAndAuthorSchema:
    """Reads the title, the author and a summary straight from the text."""
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(TEXT_INFO_EXTRACTION_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=TitleAndAuthorSchema, method="json_schema"
    )

    response = chain.invoke({"input": text})

    return TitleAndAuthorSchema.model_validate(response)


def text_sample(text: str, chunk_texts: list[str]) -> str:
    """A long text's opening, where the title and the author are, plus a few
    passages spread through the rest, so the summary covers the whole text."""
    if len(text) <= OPENING_CHARS:
        return text
    step = max(len(chunk_texts) // (SAMPLED_PASSAGES + 1), 1)
    passages = chunk_texts[step::step][:SAMPLED_PASSAGES]
    return "\n\n[...]\n\n".join([text[:OPENING_CHARS], *passages])


def save_text_info(text_db: Texts, chunk_texts: list[str]) -> None:
    info = extract_text_info(text_sample(text_db.text, chunk_texts))

    text_db.title = fit(info.title, TITLE_MAX_LENGTH)
    text_db.author = fit(info.author, AUTHOR_MAX_LENGTH)
    text_db.content_description = info.content_description

    text_db.save()


def analyse_again(text_db: Texts) -> None:
    """Redoes the title, author, summary and word count of a stored text, without
    computing its embeddings again."""
    chunks = text_db.chunks.order_by("id").values_list("chunk_text", flat=True)
    save_text_info(text_db, [chunk for chunk in chunks if chunk])

    TextWordCount.objects.filter(text=text_db).delete()
    add_text_word_count(text_db)


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
        {
            "input": words[:MAX_PICKER_WORDS],
            "content_description": content_description,
        }
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


def picked_word_counts(
    text: str, content_description: str | None
) -> tuple[dict[str, int], int]:
    """The words the model finds relevant, with their counts, and the text's total."""
    words, total_word_count = count_words(text)
    picked = word_picker(words, content_description)
    return {word.word: word.count for word in picked.words_list}, total_word_count


def add_text_word_count(text_db: Texts) -> TextWordCount:
    word_frequencies, total_word_count = picked_word_counts(
        text_db.text, text_db.content_description
    )

    return TextWordCount.objects.create(
        text=text_db,
        total_word_count=total_word_count,
        word_frequencies=word_frequencies,
    )


def add_pdf_text(path: str, file_hash: str, user_id: int) -> Texts:
    """Reads a PDF into the library: its text, its chunks with their embeddings, its
    title, author and summary, and its word count. The model calls come first and
    the rows are saved in one transaction, so a failure leaves nothing behind."""
    pages = PyPDFLoader(path).load()
    for page in pages:
        page.page_content = readable(page.page_content)
    text = "".join(page.page_content for page in pages)
    if not text.strip():
        raise NoText()

    chunk_texts, vectors = get_embeddings(pages)
    info = extract_text_info(text_sample(text, chunk_texts))
    word_frequencies, total_word_count = picked_word_counts(
        text, info.content_description
    )

    with transaction.atomic(using=router.db_for_write(Texts)):
        text_db = Texts.objects.create(
            user_id=user_id,
            text=text,
            file_hash=file_hash,
            title=fit(info.title, TITLE_MAX_LENGTH),
            author=fit(info.author, AUTHOR_MAX_LENGTH),
            content_description=info.content_description,
        )
        TextChunks.objects.bulk_create(
            TextChunks(text=text_db, chunk_text=chunk_text, vector=vector)
            for chunk_text, vector in zip(chunk_texts, vectors)
        )
        TextWordCount.objects.create(
            text=text_db,
            total_word_count=total_word_count,
            word_frequencies=word_frequencies,
        )

    return text_db


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
