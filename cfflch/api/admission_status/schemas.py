from pydantic import BaseModel


class StudentFoundResult(BaseModel):
    student_name: str
    normalized_name: str
    year_found: int
    search_query: str
    pdf_url: str
    search_title: str
    found: bool = True


class StudentNotFoundResult(BaseModel):
    student_name: str
    found: bool = False


StudentResult = StudentFoundResult | StudentNotFoundResult
