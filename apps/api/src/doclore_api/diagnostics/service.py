from doclore_api.code_analysis.service import CodeAnalysisService
from doclore_api.diagnostics.llm import LLMAdapter, LMStudioLLMAdapter
from doclore_api.diagnostics.models import DiagnosticRequest, DiagnosticReport
from doclore_api.persistence.repository import ProjectRepository
from doclore_api.retrieval.service import RetrievalService
from doclore_api.workflow.graph import DiagnosticWorkflow


class ProjectNotFoundError(Exception):
    pass


class DiagnosticEngine:
    """The single public entry point for diagnosing technical issues across docs, specs, and code."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        retrieval_service: RetrievalService,
        code_service: CodeAnalysisService,
        llm_adapter: LLMAdapter | None = None,
    ) -> None:
        self.project_repo = project_repo
        self.retrieval_service = retrieval_service
        self.code_service = code_service
        self.llm_adapter = llm_adapter or LMStudioLLMAdapter()
        self.workflow = DiagnosticWorkflow(
            retrieval_service=self.retrieval_service,
            code_service=self.code_service,
            llm_adapter=self.llm_adapter,
        )

    def diagnose(self, request: DiagnosticRequest) -> DiagnosticReport:
        project = self.project_repo.get(request.project_id)
        if not project:
            raise ProjectNotFoundError(f"Project '{request.project_id}' was not found.")

        return self.workflow.run(
            project_id=request.project_id,
            query=request.query,
            source_ids=request.source_ids,
        )

    def run(self, project_id: str, query: str, source_ids: list[str] | None = None) -> DiagnosticReport:
        return self.diagnose(DiagnosticRequest(project_id=project_id, query=query, source_ids=source_ids))

