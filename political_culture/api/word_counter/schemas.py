from pydantic import BaseModel, Field


class TitleAndAuthorSchema(BaseModel):
    reasoning: str = Field(
        ...,
        description="The reasoning behind the response in a clear and concise manner.",
    )
    author: str | None = Field(..., description="The name of the author of the text")
    title: str | None = Field(..., description="The title of the text")
