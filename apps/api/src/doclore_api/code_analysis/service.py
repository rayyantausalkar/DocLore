from typing import Optional
from doclore_api.models import SourceType
from doclore_api.retrieval.models import Evidence, RetrievalScope
from doclore_api.retrieval.service import RetrievalService


class CodeAnalysisService:
    """Performs targeted code understanding, route inspection, and AST symbol analysis."""

    def __init__(self, retrieval_service: RetrievalService) -> None:
        self.retrieval_service = retrieval_service

    def inspect(self, project_id: str, query: str, limit: int = 5) -> list[Evidence]:
        """Inspect repository source code evidence matching a query or symbol."""
        scope = RetrievalScope(
            project_id=project_id,
            source_types=[SourceType.REPOSITORY],
        )
        return self.retrieval_service.search(query=query, scope=scope, limit=limit)

    def inspect_route(self, project_id: str, method: str, path: str) -> Optional[Evidence]:
        """Find the exact source code handler implementing a specific HTTP endpoint."""
        query = f"route:{method.upper()} {path}"
        results = self.inspect(project_id=project_id, query=query, limit=3)
        for hit in results:
            if hit.provenance.section_path and f"route:{method.upper()}" in hit.provenance.section_path:
                return hit
        return results[0] if results else None
