from typing import Any, Optional
from pydantic import BaseModel, Field

from doclore_api.models import SourceType


class DiagnosticRequest(BaseModel):
    project_id: str
    query: str = Field(..., min_length=3)
    source_ids: Optional[list[str]] = None
    context: Optional[dict[str, Any]] = None


class Citation(BaseModel):
    """Verified citation linking an explanation directly to source evidence."""
    source_id: str
    document_id: str
    chunk_id: str
    source_type: SourceType
    canonical_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    section_path: Optional[str] = None
    snippet: str
    relevance_note: Optional[str] = None


class DiagnosticReport(BaseModel):
    """The canonical diagnostic result produced by the LangGraph workflow."""
    id: str
    project_id: str
    query: str
    intent: Optional[str] = None
    intent_label: Optional[str] = None
    summary: str
    root_cause: str
    recommended_actions: list[str]
    insufficient_evidence: bool = False
    citations: list[Citation] = Field(default_factory=list)
    workflow_trace: list[str] = Field(default_factory=list)
    explanation: Optional[str] = None


class CitationLine(BaseModel):
    line_number: int
    content: str
    is_highlighted: bool


class CitationContext(BaseModel):
    """Rich context payload for deep citation inspection in the UI."""
    chunk_id: str
    document_id: str
    source_id: str
    source_type: SourceType
    canonical_path: str
    section_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    snippet: str
    document_title: str
    surrounding_lines: list[CitationLine]
