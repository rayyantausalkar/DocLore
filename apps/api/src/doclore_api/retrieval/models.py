from typing import Literal, Optional
from pydantic import BaseModel, Field

from doclore_api.models import Provenance, SourceType


class RetrievalScope(BaseModel):
    """Scope filtering for retrieval queries."""
    project_id: str
    source_ids: Optional[list[str]] = None
    source_types: Optional[list[SourceType]] = None


class Evidence(BaseModel):
    """Evidence chunk retrieved and ranked via Reciprocal Rank Fusion."""
    chunk_id: str
    document_id: str
    text: str
    provenance: Provenance
    rrf_score: float
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None
    match_type: Literal["hybrid", "exact_sparse", "dense_semantic"] = "hybrid"


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
    source_ids: Optional[list[str]] = None
    source_types: Optional[list[SourceType]] = None


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[Evidence]
