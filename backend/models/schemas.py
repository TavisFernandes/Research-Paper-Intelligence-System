"""Pydantic request/response schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

PaperId = str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    paper_ids: Optional[List[PaperId]] = Field(default=None, max_length=50)
    section_name: Optional[str] = Field(default=None, max_length=64)
    top_k: int = Field(default=8, ge=1, le=50)
    mode: Optional[Literal["dense", "lexical", "hybrid"]] = None
    include_low_confidence: bool = False

    @field_validator("query")
    @classmethod
    def _strip(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value.strip()


class AnswerRequest(SearchRequest):
    top_k: int = Field(default=6, ge=1, le=20)


class SummaryRequest(BaseModel):
    paper_id: PaperId
    section_name: Optional[str] = Field(default=None, max_length=64)
    max_sentences: int = Field(default=5, ge=1, le=15)
    per_section: bool = True


class CompareRequest(BaseModel):
    paper_ids: List[PaperId] = Field(min_length=2, max_length=2)
    use_llm: bool = False


class InsightsRequest(BaseModel):
    paper_ids: List[PaperId] = Field(min_length=2, max_length=20)
    use_llm: bool = False


class RetrievalEvalQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    relevant_chunk_ids: List[str] = Field(default_factory=list)
    relevant_paper_ids: List[PaperId] = Field(default_factory=list)


class RetrievalEvalRequest(BaseModel):
    queries: List[RetrievalEvalQuery] = Field(min_length=1, max_length=500)
    mode: Optional[Literal["dense", "lexical", "hybrid"]] = None
    paper_ids: Optional[List[PaperId]] = None


class SummarizationEvalRequest(BaseModel):
    predictions: Optional[List[str]] = None
    references: Optional[List[str]] = None
    paper_id: Optional[PaperId] = None
    reference_summary: Optional[str] = None
    section_name: Optional[str] = None


class ReindexRequest(BaseModel):
    reset: bool = False


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    components: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
