from pydantic import BaseModel, Field


class TitleAndAuthorSchema(BaseModel):
    reasoning: str = Field(
        ...,
        description="The reasoning behind the responses in a clear and concise manner",
    )
    author: str = Field(..., description="The name of the author of the text")
    title: str = Field(..., description="The title of the text")
    content_description: str = Field(
        ...,
        description="The content description of the text",
    )


class WordCount(BaseModel):
    word: str = Field(..., description="The word")
    count: int = Field(..., description="How many times it appeared")


class WordFrequencySquema(BaseModel):
    reasoning: str = Field(
        ...,
        description="The reasoning behind the responses in a clear and concise manner",
    )
    words_list: list[WordCount] = Field(..., description="A list of word/count objects")
