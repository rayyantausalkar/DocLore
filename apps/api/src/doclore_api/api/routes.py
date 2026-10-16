from datetime import datetime
import json
import os
import re
import uuid
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from doclore_api.code_analysis.service import CodeAnalysisService
from doclore_api.diagnostics.models import (
    CitationContext,
    CitationLine,
    DiagnosticReport,
    DiagnosticRequest,
)
from doclore_api.diagnostics.service import DiagnosticEngine, ProjectNotFoundError
from doclore_api.models import (
    ChatMessage,
    ChatSession,
    Document,
    Project,
    Source,
    SourceStatus,
    SourceType,
    SyncResult,
)
from doclore_api.persistence.memory import (
    InMemoryChatRepository,
    InMemoryDocumentRepository,
    InMemoryProjectRepository,
    InMemorySourceRepository,
)
from doclore_api.retrieval.dense import LMStudioEmbeddingAdapter
from doclore_api.retrieval.models import Evidence, RetrievalScope, SearchRequest, SearchResponse
from doclore_api.retrieval.service import RetrievalService
from doclore_api.sources.service import (
    SourceNotFoundError,
    SourceService,
    UnsupportedSourceTypeError,
)

# Global singleton stores for the running application instance.
# State is snapshotted to DOCLORE_DATA_DIR so projects/chats/documents survive restarts.
_DATA_DIR = os.getenv("DOCLORE_DATA_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".doclore_data"
)
_DATA_DIR = os.path.abspath(_DATA_DIR)
project_repo = InMemoryProjectRepository(os.path.join(_DATA_DIR, "projects.json"))
source_repo = InMemorySourceRepository(os.path.join(_DATA_DIR, "sources.json"))
document_repo = InMemoryDocumentRepository(os.path.join(_DATA_DIR, "documents.json"))
chat_repo = InMemoryChatRepository(os.path.join(_DATA_DIR, "chats.json"))
source_service = SourceService(
    project_repo=project_repo,
    source_repo=source_repo,
    document_repo=document_repo,
)
retrieval_service = RetrievalService(
    source_repo=source_repo,
    document_repo=document_repo,
    embedding_adapter=LMStudioEmbeddingAdapter(),
)
code_analysis_service = CodeAnalysisService(retrieval_service=retrieval_service)
diagnostic_engine = DiagnosticEngine(
    project_repo=project_repo,
    retrieval_service=retrieval_service,
    code_service=code_analysis_service,
)

router = APIRouter(prefix="/api/v1")


class CreateProjectRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    github_url: Optional[str] = None
    branch: Optional[str] = None
    subpath: Optional[str] = None


class CreateSourceRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    source_type: SourceType
    config: dict[str, Any] = Field(default_factory=dict)


class SyncSourceRequest(BaseModel):
    force: bool = False


class SupportedSourceTypeInfo(BaseModel):
    source_type: str
    status: str
    description: str


@router.get("/sources/supported-types", response_model=list[SupportedSourceTypeInfo], tags=["sources"])
def list_supported_source_types() -> list[SupportedSourceTypeInfo]:
    """Explicitly declare implemented vs planned source adapters."""
    return [
        SupportedSourceTypeInfo(
            source_type="markdown",
            status="supported",
            description="Markdown documentation with exact line-preserving provenance and heading hierarchy.",
        ),
        SupportedSourceTypeInfo(
            source_type="openapi",
            status="supported",
            description="OpenAPI 3.x specifications for endpoint, parameter, and auth schema inspection.",
        ),
        SupportedSourceTypeInfo(
            source_type="repository",
            status="supported",
            description="Source code repository with Python AST analysis extracting endpoints, handlers, and symbols with line numbers.",
        ),
        SupportedSourceTypeInfo(
            source_type="issue_logs",
            status="supported",
            description="Historical bug and incident postmortems preserving symptoms, root cause, and verified resolution with line fidelity.",
        ),
        SupportedSourceTypeInfo(
            source_type="style_guide",
            status="supported",
            description="Internal engineering style guides, API security standards, and error-payload conventions.",
        ),
        SupportedSourceTypeInfo(
            source_type="architecture_diagram",
            status="supported",
            description="System architecture specifications, Mermaid sequence/flowchart diagrams, and component topologies.",
        ),
    ]


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED, tags=["projects"])
def create_project(req: CreateProjectRequest) -> Project:
    if not req.name.strip():
        raise HTTPException(
            status_code=422,
            detail="Project name cannot be blank.",
        )
    req.name = req.name.strip()
    if req.github_url is not None:
        req.github_url = req.github_url.strip() or None
    project_id = req.id or f"proj-{uuid.uuid4().hex[:8]}"
    if project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with id '{project_id}' already exists.",
        )
    project = Project(
        id=project_id,
        name=req.name,
        description=req.description,
        github_url=req.github_url,
        branch=req.branch,
        subpath=req.subpath,
    )
    saved_project = project_repo.create(project)

    # If GitHub URL is provided, immediately ingest and index the repository
    if req.github_url:
        try:
            source_id = f"src-gh-{project_id}"
            source = Source(
                id=source_id,
                project_id=project_id,
                name=f"{req.name} Repository",
                source_type=SourceType.REPOSITORY,
                config={
                    "github_url": req.github_url,
                    "branch": req.branch,
                    "subpath": req.subpath,
                },
            )
            source_repo.create(source)
            sync_res = source_service.sync(source_id, force=True)
            saved_project.repo_status = "synced"
            saved_project.commit_hash = sync_res.revision
            saved_project.document_count = sync_res.document_count
            project_repo.update(saved_project)
        except Exception as exc:
            # Roll back so a failed import never leaves an unusable, silent project behind.
            _purge_project_data(project_id)
            project_repo.delete(project_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not import repository: {exc}",
            )

    return saved_project


@router.get("/projects", response_model=list[Project], tags=["projects"])
def list_projects() -> list[Project]:
    projects = project_repo.list()
    for project in projects:
        sources = source_repo.list_by_project(project.id)
        total_docs = sum(len(document_repo.list_by_source(s.id)) for s in sources)
        if project.document_count != total_docs:
            project.document_count = total_docs
            project_repo.update(project)
    return projects


@router.get("/projects/{project_id}", response_model=Project, tags=["projects"])
def get_project(project_id: str) -> Project:
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    sources = source_repo.list_by_project(project_id)
    total_docs = sum(len(document_repo.list_by_source(s.id)) for s in sources)
    if project.document_count != total_docs:
        project.document_count = total_docs
        project = project_repo.update(project)
    return project


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    github_url: Optional[str] = None
    branch: Optional[str] = None
    subpath: Optional[str] = None


@router.patch("/projects/{project_id}", response_model=Project, tags=["projects"])
def update_project(project_id: str, req: UpdateProjectRequest) -> Project:
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    if req.name is not None:
        trimmed = req.name.strip()
        if not trimmed:
            raise HTTPException(
                status_code=422,
                detail="Project name cannot be blank.",
            )
        project.name = trimmed
    if req.description is not None:
        project.description = req.description.strip()
    if req.github_url is not None:
        project.github_url = req.github_url.strip() or None
    if req.branch is not None:
        project.branch = req.branch.strip() or None
    if req.subpath is not None:
        project.subpath = req.subpath.strip() or None
    return project_repo.update(project)


def _purge_project_data(project_id: str) -> None:
    """Remove every record that belongs to a project (sources, documents, chats)."""
    for source_id in source_repo.delete_by_project(project_id):
        document_repo.delete_by_source(source_id)
    chat_repo.delete_by_project(project_id)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["projects"])
def delete_project(project_id: str) -> None:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    _purge_project_data(project_id)
    project_repo.delete(project_id)


# ============================================================================
# Chat Sessions and Messages within Projects
# ============================================================================

class CreateChatSessionRequest(BaseModel):
    title: Optional[str] = None


class SendChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


@router.get("/projects/{project_id}/chats", response_model=list[ChatSession], tags=["chats"])
def list_project_chats(project_id: str) -> list[ChatSession]:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    return chat_repo.list_sessions_by_project(project_id)


@router.post(
    "/projects/{project_id}/chats",
    response_model=ChatSession,
    status_code=status.HTTP_201_CREATED,
    tags=["chats"],
)
def create_chat_session(project_id: str, req: CreateChatSessionRequest) -> ChatSession:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    session_id = f"chat-{uuid.uuid4().hex[:8]}"
    session = ChatSession(
        id=session_id,
        project_id=project_id,
        title=req.title or "New Chat",
    )
    return chat_repo.create_session(session)


@router.get("/projects/{project_id}/chats/{chat_id}", response_model=ChatSession, tags=["chats"])
def get_chat_session(project_id: str, chat_id: str) -> ChatSession:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    session = chat_repo.get_session(chat_id)
    if not session or session.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{chat_id}' not found in project '{project_id}'.",
        )
    return session


class UpdateChatSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


@router.patch("/projects/{project_id}/chats/{chat_id}", response_model=ChatSession, tags=["chats"])
def update_chat_session(project_id: str, chat_id: str, req: UpdateChatSessionRequest) -> ChatSession:
    session = chat_repo.get_session(chat_id)
    if not session or session.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{chat_id}' not found.",
        )
    trimmed = req.title.strip()
    if not trimmed:
        raise HTTPException(status_code=422, detail="Title cannot be blank.")
    session.title = trimmed
    return chat_repo.update_session(session)


@router.delete("/projects/{project_id}/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["chats"])
def delete_chat_session(project_id: str, chat_id: str) -> None:
    session = chat_repo.get_session(chat_id)
    if not session or session.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{chat_id}' not found.",
        )
    chat_repo.delete_session(chat_id)


@router.post("/projects/{project_id}/chats/{chat_id}/messages", response_model=ChatSession, tags=["chats"])
def send_chat_message(project_id: str, chat_id: str, req: SendChatMessageRequest) -> ChatSession:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    session = chat_repo.get_session(chat_id)
    if not session or session.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{chat_id}' not found.",
        )

    query_text = req.content.strip()
    if not query_text:
        raise HTTPException(
            status_code=422,
            detail="Message cannot be blank.",
        )

    # 1. Record user question in simple English
    user_msg = ChatMessage(
        id=f"msg-{uuid.uuid4().hex[:8]}",
        session_id=chat_id,
        role="user",
        content=query_text,
    )
    chat_repo.add_message(chat_id, user_msg)

    # 2. Run diagnostic workflow on the project's actual indexed repository documents
    report = None
    try:
        report = diagnostic_engine.run(project_id=project_id, query=query_text)
        summary = report.summary
        root_cause = report.root_cause
        recommended_actions = report.recommended_actions
        citations = [c.model_dump() for c in report.citations]
        workflow_trace = report.workflow_trace
        raw_exp = (report.explanation or report.root_cause or report.summary or "").strip()

        # Unpack raw JSON wrapper if present
        if raw_exp.startswith("{") and raw_exp.endswith("}"):
            try:
                parsed = json.loads(raw_exp, strict=False)
                if isinstance(parsed, dict):
                    raw_exp = str(parsed.get("explanation") or parsed.get("summary") or raw_exp).strip()
            except Exception:
                match = re.search(r'"explanation"\s*:\s*"(.*?)(?:"\s*,\s*"\w+"|\s*\}\s*$)', raw_exp, re.DOTALL)
                if match:
                    raw_exp = match.group(1).replace("\\n", "\n").replace('\\"', '"').strip()

        # Enforce zero-emoji brand standard
        explanation = re.sub(r"[\U00010000-\U0010ffff]", "", raw_exp)
    except Exception as exc:
        summary = "Analysis grounded in repository."
        root_cause = str(exc)
        recommended_actions = []
        citations = []
        workflow_trace = [f"Workflow report: {exc}"]
        explanation = f"I encountered an error retrieving or synthesizing an answer: {exc}"

    # 3. Record agent response with full conversational explanation, reasoning trace, and verified citations
    asst_msg = ChatMessage(
        id=f"msg-{uuid.uuid4().hex[:8]}",
        session_id=chat_id,
        role="assistant",
        content=explanation,
        intent=getattr(report, "intent", None),
        intent_label=getattr(report, "intent_label", None),
        summary=summary,
        root_cause=root_cause,
        recommended_actions=recommended_actions,
        citations=citations,
        workflow_trace=workflow_trace,
    )
    chat_repo.add_message(chat_id, asst_msg)

    # 4. If title was "New Chat", give it a readable title from the question
    if session.title == "New Chat":
        session.title = query_text[:35].strip() + ("..." if len(query_text) > 35 else "")
        chat_repo.persist()

    return session


@router.get("/projects/{project_id}/sources", response_model=list[Source], tags=["sources"])
def list_project_sources(project_id: str) -> list[Source]:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    return source_repo.list_by_project(project_id)


def _recalculate_project_document_count(project_id: str) -> None:
    project = project_repo.get(project_id)
    if not project:
        return
    sources = source_repo.list_by_project(project_id)
    total_docs = sum(len(document_repo.list_by_source(s.id)) for s in sources)
    if project.document_count != total_docs:
        project.document_count = total_docs
        project_repo.update(project)


@router.post(
    "/projects/{project_id}/sources",
    response_model=Source,
    status_code=status.HTTP_201_CREATED,
    tags=["sources"],
)
def create_source(project_id: str, req: CreateSourceRequest) -> Source:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )

    # Validate support
    if req.source_type not in SourceService.SUPPORTED_SOURCE_TYPES:
        supported = [st.value for st in SourceService.SUPPORTED_SOURCE_TYPES]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Source type '{req.source_type.value}' is not supported yet. "
                f"Currently supported: {supported}"
            ),
        )

    clean_name = req.name.strip()
    if not clean_name:
        raise HTTPException(status_code=422, detail="Source name cannot be blank.")

    # Prevent duplicate source name in same project
    existing_sources = source_repo.list_by_project(project_id)
    if any(s.name.strip().lower() == clean_name.lower() for s in existing_sources):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A knowledge source named '{clean_name}' already exists in this project.",
        )

    source_id = req.id or f"src-{uuid.uuid4().hex[:8]}"
    if source_repo.get(source_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with id '{source_id}' already exists.",
        )

    source = Source(
        id=source_id,
        project_id=project_id,
        name=clean_name,
        source_type=req.source_type,
        config=req.config,
    )
    return source_repo.create(source)


@router.get("/sources/{source_id}", response_model=Source, tags=["sources"])
def get_source(source_id: str) -> Source:
    source = source_repo.get(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found.",
        )
    return source


@router.post("/sources/{source_id}/sync", response_model=SyncResult, tags=["sources"])
def sync_source(source_id: str, req: Optional[SyncSourceRequest] = None) -> SyncResult:
    force = req.force if req else False
    try:
        result = source_service.sync(source_id=source_id, force=force)
        source = source_repo.get(source_id)
        if source:
            _recalculate_project_document_count(source.project_id)
        return result
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except UnsupportedSourceTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/sources/{source_id}/documents", response_model=list[Document], tags=["sources"])
def list_source_documents(source_id: str) -> list[Document]:
    if not source_repo.get(source_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found.",
        )
    return document_repo.list_by_source(source_id)


class UpdateSourceRequest(BaseModel):
    name: Optional[str] = None


@router.patch("/sources/{source_id}", response_model=Source, tags=["sources"])
def update_source(source_id: str, req: UpdateSourceRequest) -> Source:
    source = source_repo.get(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found.",
        )
    if req.name is not None:
        trimmed = req.name.strip()
        if not trimmed:
            raise HTTPException(status_code=422, detail="Source name cannot be blank.")
        existing_sources = source_repo.list_by_project(source.project_id)
        if any(s.id != source.id and s.name.strip().lower() == trimmed.lower() for s in existing_sources):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A knowledge source named '{trimmed}' already exists in this project.",
            )
        source.name = trimmed
    return source_repo.update(source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["sources"])
def delete_source(source_id: str) -> None:
    source = source_repo.get(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found.",
        )
    project_id = source.project_id
    document_repo.delete_by_source(source_id)
    source_repo.delete(source_id)
    _recalculate_project_document_count(project_id)


@router.post(
    "/projects/{project_id}/search",
    response_model=SearchResponse,
    tags=["retrieval"],
)
def search_project_knowledge(project_id: str, req: SearchRequest) -> SearchResponse:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )

    scope = RetrievalScope(
        project_id=project_id,
        source_ids=req.source_ids,
        source_types=req.source_types,
    )
    evidence = retrieval_service.search(query=req.query, scope=scope, limit=req.limit)
    return SearchResponse(
        query=req.query,
        total_results=len(evidence),
        results=evidence,
    )


@router.post(
    "/projects/{project_id}/code/inspect",
    response_model=SearchResponse,
    tags=["code_analysis"],
)
def inspect_project_code(project_id: str, req: SearchRequest) -> SearchResponse:
    if not project_repo.get(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    evidence = code_analysis_service.inspect(project_id=project_id, query=req.query, limit=req.limit)
    return SearchResponse(
        query=req.query,
        total_results=len(evidence),
        results=evidence,
    )


@router.post(
    "/diagnoses",
    response_model=DiagnosticReport,
    tags=["diagnostics"],
)
def run_diagnosis(req: DiagnosticRequest) -> DiagnosticReport:
    """Submit a question or runtime error and receive an evidence-grounded diagnosis with exact citations."""
    try:
        return diagnostic_engine.diagnose(req)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnostic workflow failure: {str(exc)}",
        )


@router.get(
    "/citations/{chunk_id}/context",
    response_model=CitationContext,
    tags=["citations"],
)
def get_citation_context(chunk_id: str) -> CitationContext:
    """Fetch rich source context for a cited chunk with surrounding line numbers and highlight markers."""
    result = document_repo.get_chunk_with_document(chunk_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cited chunk '{chunk_id}' not found.",
        )
    doc, chunk = result
    source = source_repo.get(doc.source_id)
    source_type = source.source_type if source else SourceType.MARKDOWN

    # Parse surrounding lines from raw_content
    raw_lines = doc.raw_content.splitlines() if doc.raw_content else chunk.text.splitlines()
    start_line = chunk.provenance.start_line
    end_line = chunk.provenance.end_line

    surrounding_lines: list[CitationLine] = []
    if raw_lines:
        if start_line is not None and end_line is not None:
            # 1-indexed padding: show up to 15 lines before and after
            pad_before = 15
            pad_after = 15
            window_start = max(1, start_line - pad_before)
            window_end = min(len(raw_lines), end_line + pad_after)
            for idx in range(window_start, window_end + 1):
                line_idx = idx - 1
                content = raw_lines[line_idx] if line_idx < len(raw_lines) else ""
                is_hl = start_line <= idx <= end_line
                surrounding_lines.append(
                    CitationLine(line_number=idx, content=content, is_highlighted=is_hl)
                )
        else:
            for idx, content in enumerate(raw_lines[:40], start=1):
                surrounding_lines.append(
                    CitationLine(line_number=idx, content=content, is_highlighted=False)
                )

    return CitationContext(
        chunk_id=chunk.id,
        document_id=doc.id,
        source_id=doc.source_id,
        source_type=source_type,
        canonical_path=chunk.provenance.canonical_path,
        section_path=chunk.provenance.section_path,
        start_line=start_line,
        end_line=end_line,
        snippet=chunk.text,
        document_title=doc.title,
        surrounding_lines=surrounding_lines,
    )



