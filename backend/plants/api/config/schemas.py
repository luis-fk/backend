from typing import Optional

from pydantic import BaseModel, Field


class InfoSchema(BaseModel):
    error_message: Optional[str] = Field(None, description="Error message")
