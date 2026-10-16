from typing import Protocol
from doclore_api.models import Document, Source


class IngestionAdapter(Protocol):
    """Protocol for all source ingestion adapters."""

    @property
    def source_type(self) -> str:
        """The source type this adapter handles."""
        ...

    def parse(self, source: Source, content: str | bytes, canonical_path: str, revision: str) -> list[Document]:
        """Parse raw content into canonical Document instances with line-preserving Provenance."""
        ...
