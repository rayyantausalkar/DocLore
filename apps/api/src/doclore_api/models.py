from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    MARKDOWN = "markdown"
    OPENAPI = "openapi"
    REPOSITORY = "repository"
    ISSUE_LOGS = "issue_logs"
    STYLE_GUIDE = "style_guide"
    ARCHITECTURE_DIAGRAM = "architecture_diagram"


class SourceStatus(str, Enum):
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"


class Provenance(BaseModel):
    """Guarantees exact traceability for every retrieved chunk."""
    project_id: str
    source_id: str
    document_id: str
    chunk_id: str
    source_type: SourceType
    canonical_path: str
    source_revision: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    section_path: Optional[str] = None
    parser_version: str = "markdown-v1"


class Chunk(BaseModel):
    """Normalized searchable unit of content with guaranteed provenance."""
    id: str
    document_id: str
    text: str
    provenance: Provenance


class Document(BaseModel):
    """Canonical document representation emitted by an ingestion adapter."""
    id: str
    source_id: str
    title: str
    canonical_path: str
    revision: str
    chunks: list[Chunk] = Field(default_factory=list)
    raw_content: Optional[str] = None


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    github_url: Optional[str] = None
    branch: Optional[str] = None
    subpath: Optional[str] = None
    repo_status: Optional[str] = None
    commit_hash: Optional[str] = None
    document_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatMessage(BaseModel):
    id: str
    session_id: str
    role: str  # "user" | "assistant"
    content: str
    intent: Optional[str] = None
    intent_label: Optional[str] = None
    summary: Optional[str] = None
    root_cause: Optional[str] = None
    code_diff: Optional[str] = None
    recommended_actions: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    workflow_trace: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatSession(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[ChatMessage] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    project_id: str
    name: str
    source_type: SourceType
    config: dict[str, Any] = Field(default_factory=dict)
    status: SourceStatus = SourceStatus.PENDING
    current_revision: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SyncResult(BaseModel):
    source_id: str
    status: SourceStatus
    revision: str
    document_count: int
    chunk_count: int
    is_idempotent_skip: bool = False
    error: Optional[str] = None
