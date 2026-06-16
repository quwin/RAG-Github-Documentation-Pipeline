from pydantic import BaseModel, Field
from typing import Any


class IngestRequest(BaseModel):
    repo_url: str
    branch: str | None = None
    collection_name: str = "github_docs"
    chunk_strategy: str = Field(default="header", pattern="^(recursive|header)$")


class IngestResponse(BaseModel):
    repo_url: str
    branch: str
    documents_loaded: int
    chunks_created: int
    collection_name: str
    status: str


class AskRequest(BaseModel):
    question: str
    collection_name: str = "github_docs"
    top_k: int = 20
    rerank_top_k: int = 5
    dense_weight: float = 1.0
    sparse_weight: float = 1.0


class SourceChunk(BaseModel):
    chunk_id: str | None = None
    source_path: str | None = None
    repo_url: str | None = None
    section_heading: str | None = None
    retrieval_score: float | None = None
    cross_score: float | None = None
    text_preview: str


class ConfidenceScores(BaseModel):
    retrieval_confidence: float
    answer_completeness: float
    valid_citations: list[int]
    invalid_citations: list[int]


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceChunk]
    confidence: ConfidenceScores | None = None