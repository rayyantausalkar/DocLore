from typing import Optional, Protocol
from doclore_api.models import ChatMessage, ChatSession, Chunk, Document, Project, Source



class ProjectRepository(Protocol):
    def create(self, project: Project) -> Project:
        ...

    def get(self, project_id: str) -> Optional[Project]:
        ...

    def list(self) -> list[Project]:
        ...

    def update(self, project: Project) -> Project:
        ...

    def delete(self, project_id: str) -> bool:
        ...


class SourceRepository(Protocol):
    def create(self, source: Source) -> Source:
        ...

    def get(self, source_id: str) -> Optional[Source]:
        ...

    def list_by_project(self, project_id: str) -> list[Source]:
        ...

    def update(self, source: Source) -> Source:
        ...

    def delete(self, source_id: str) -> bool:
        ...

    def delete_by_project(self, project_id: str) -> list[str]:
        ...


class DocumentRepository(Protocol):
    def save_documents(self, source_id: str, documents: list[Document]) -> None:
        """Atomically replace canonical documents and chunks for a source revision."""
        ...

    def delete_by_source(self, source_id: str) -> None:
        ...

    def list_by_source(self, source_id: str) -> list[Document]:
        ...

    def get(self, document_id: str) -> Optional[Document]:
        ...

    def get_chunks_by_source(self, source_id: str) -> list[Chunk]:
        ...

    def get_chunk_with_document(self, chunk_id: str) -> Optional[tuple[Document, Chunk]]:
        ...


class ChatRepository(Protocol):
    def create_session(self, session: ChatSession) -> ChatSession:
        ...

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        ...

    def list_sessions_by_project(self, project_id: str) -> list[ChatSession]:
        ...

    def add_message(self, session_id: str, message: ChatMessage) -> ChatMessage:
        ...

    def update_session(self, session: ChatSession) -> ChatSession:
        ...

    def delete_session(self, session_id: str) -> bool:
        ...

