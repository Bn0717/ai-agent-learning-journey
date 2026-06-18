from pydantic import BaseModel


class WebSearchInput(BaseModel):
    query: str


class EmailInput(BaseModel):
    to: str
    subject: str
    content: str