from typing import Any, Literal
from pydantic import BaseModel, Field


class Citation(BaseModel):
    paper_id: str
    filename: str = ""
    chunk_id: str
    section_name: str
    page_start: int
    page_end: int
    text: str
    score: float | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    paper_ids: list[str] | None = None
    section_name: str | None = None
    limit: int = Field(default=8, ge=1, le=30)


class AnswerRequest(SearchRequest):
    pass


class SummaryRequest(BaseModel):
    paper_id: str
    section_name: str | None = None
    max_sentences: int = Field(default=5, ge=1, le=15)


class CompareRequest(BaseModel):
    paper_ids: list[str] = Field(min_length=2, max_length=10)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    vector_store: str
    embedding_backend: str
    llm_backend: str
    details: dict[str, Any] = Field(default_factory=dict)
