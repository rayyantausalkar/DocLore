import json
import os
import tempfile
import threading
from typing import Any, Callable, Optional
from doclore_api.models import ChatMessage, ChatSession, Chunk, Document, Project, Source
from doclore_api.persistence.repository import (
    ChatRepository,
    DocumentRepository,
    ProjectRepository,
    SourceRepository,
)


class _Snapshot:
    """Atomic JSON snapshot used to keep state across server restarts.

    A corrupt or unreadable snapshot is ignored (never crashes startup).
    """

    def __init__(self, path: Optional[str]) -> None:
        self.path = path

    def load(self) -> Any:
        if not self.path or not os.path.isfile(self.path):
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save(self, payload: Any) -> None:
        if not self.path:
            return
        try:
            directory = os.path.dirname(self.path) or "."
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp_path, self.path)  # atomic on Windows and POSIX
        except Exception:
            pass  # persistence is best-effort; in-memory state stays authoritative


def _safe_load(items: Any, factory: Callable[[Any], Any]) -> list[Any]:
    loaded = []
    for item in items or []:
        try:
            loaded.append(factory(item))
        except Exception:
            continue
    return loaded


class InMemoryProjectRepository(ProjectRepository):
    def __init__(self, snapshot_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._projects: dict[str, Project] = {}
        self._snapshot = _Snapshot(snapshot_path)
        for p in _safe_load(self._snapshot.load(), Project.model_validate):
            self._projects[p.id] = p

    def _persist(self) -> None:
        self._snapshot.save([p.model_dump(mode="json") for p in self._projects.values()])

    def create(self, project: Project) -> Project:
        with self._lock:
            self._projects[project.id] = project
            self._persist()
            return project

    def get(self, project_id: str) -> Optional[Project]:
        with self._lock:
            return self._projects.get(project_id)

    def list(self) -> list[Project]:
        with self._lock:
            return list(self._projects.values())

    def update(self, project: Project) -> Project:
        with self._lock:
            self._projects[project.id] = project
            self._persist()
            return project

    def delete(self, project_id: str) -> bool:
        with self._lock:
            if project_id in self._projects:
                del self._projects[project_id]
                self._persist()
                return True
            return False


class InMemorySourceRepository(SourceRepository):
    def __init__(self, snapshot_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._sources: dict[str, Source] = {}
        self._snapshot = _Snapshot(snapshot_path)
        for s in _safe_load(self._snapshot.load(), Source.model_validate):
            self._sources[s.id] = s

    def _persist(self) -> None:
        self._snapshot.save([s.model_dump(mode="json") for s in self._sources.values()])

    def create(self, source: Source) -> Source:
        with self._lock:
            self._sources[source.id] = source
            self._persist()
            return source

    def get(self, source_id: str) -> Optional[Source]:
        with self._lock:
            return self._sources.get(source_id)

    def list_by_project(self, project_id: str) -> list[Source]:
        with self._lock:
            return [s for s in self._sources.values() if s.project_id == project_id]

    def update(self, source: Source) -> Source:
        with self._lock:
            self._sources[source.id] = source
            self._persist()
            return source

    def delete(self, source_id: str) -> bool:
        with self._lock:
            if source_id in self._sources:
                del self._sources[source_id]
                self._persist()
                return True
            return False

    def delete_by_project(self, project_id: str) -> list[str]:
        """Remove all sources of a project; returns the removed source ids."""
        with self._lock:
            removed = [sid for sid, s in self._sources.items() if s.project_id == project_id]
            for sid in removed:
                del self._sources[sid]
            if removed:
                self._persist()
            return removed


class InMemoryDocumentRepository(DocumentRepository):
    def __init__(self, snapshot_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        # source_id -> list of Document
        self._documents_by_source: dict[str, list[Document]] = {}
        # document_id -> Document
        self._documents_by_id: dict[str, Document] = {}
        # chunk_id -> (Document, Chunk) for O(1) citation lookup
        self._chunk_index: dict[str, tuple[Document, Chunk]] = {}
        self._snapshot = _Snapshot(snapshot_path)
        data = self._snapshot.load()
        if isinstance(data, dict):
            for source_id, docs in data.items():
                loaded = _safe_load(docs, Document.model_validate)
                if loaded:
                    self._store(source_id, loaded)

    def _store(self, source_id: str, documents: list[Document]) -> None:
        self._documents_by_source[source_id] = list(documents)
        for doc in documents:
            self._documents_by_id[doc.id] = doc
            for chunk in doc.chunks:
                self._chunk_index[chunk.id] = (doc, chunk)

    def _drop(self, source_id: str) -> None:
        for doc in self._documents_by_source.pop(source_id, []):
            self._documents_by_id.pop(doc.id, None)
            for chunk in doc.chunks:
                self._chunk_index.pop(chunk.id, None)

    def _persist(self) -> None:
        self._snapshot.save(
            {
                sid: [d.model_dump(mode="json") for d in docs]
                for sid, docs in self._documents_by_source.items()
            }
        )

    def save_documents(self, source_id: str, documents: list[Document]) -> None:
        with self._lock:
            # Clean up old documents for this source if any, then store the new revision
            self._drop(source_id)
            self._store(source_id, documents)
            self._persist()

    def delete_by_source(self, source_id: str) -> None:
        with self._lock:
            self._drop(source_id)
            self._persist()

    def list_by_source(self, source_id: str) -> list[Document]:
        with self._lock:
            return list(self._documents_by_source.get(source_id, []))

    def get(self, document_id: str) -> Optional[Document]:
        with self._lock:
            return self._documents_by_id.get(document_id)

    def get_chunks_by_source(self, source_id: str) -> list[Chunk]:
        with self._lock:
            chunks: list[Chunk] = []
            for doc in self._documents_by_source.get(source_id, []):
                chunks.extend(doc.chunks)
            return chunks

    def get_chunk_with_document(self, chunk_id: str) -> Optional[tuple[Document, Chunk]]:
        with self._lock:
            return self._chunk_index.get(chunk_id)


class InMemoryChatRepository(ChatRepository):
    def __init__(self, snapshot_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, ChatSession] = {}
        self._snapshot = _Snapshot(snapshot_path)
        for s in _safe_load(self._snapshot.load(), ChatSession.model_validate):
            self._sessions[s.id] = s

    def _persist(self) -> None:
        self._snapshot.save([s.model_dump(mode="json") for s in self._sessions.values()])

    def persist(self) -> None:
        """Flush after in-place session edits (e.g. title changes)."""
        with self._lock:
            self._persist()

    def create_session(self, session: ChatSession) -> ChatSession:
        with self._lock:
            self._sessions[session.id] = session
            self._persist()
            return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions_by_project(self, project_id: str) -> list[ChatSession]:
        with self._lock:
            return [
                s for s in self._sessions.values()
                if s.project_id == project_id
            ]

    def add_message(self, session_id: str, message: ChatMessage) -> ChatMessage:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(f"Chat session '{session_id}' not found.")
            session.messages.append(message)
            self._persist()
            return message

    def update_session(self, session: ChatSession) -> ChatSession:
        with self._lock:
            self._sessions[session.id] = session
            self._persist()
            return session

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._persist()
                return True
            return False

    def delete_by_project(self, project_id: str) -> int:
        with self._lock:
            removed = [sid for sid, s in self._sessions.items() if s.project_id == project_id]
            for sid in removed:
                del self._sessions[sid]
            if removed:
                self._persist()
            return len(removed)
