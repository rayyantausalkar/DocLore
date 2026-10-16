from doclore_api.code_analysis.service import CodeAnalysisService
from doclore_api.models import Project, Source, SourceStatus, SourceType
from doclore_api.persistence.memory import (
    InMemoryDocumentRepository,
    InMemoryProjectRepository,
    InMemorySourceRepository,
)
from doclore_api.retrieval.models import RetrievalScope
from doclore_api.retrieval.service import RetrievalService
from doclore_api.sources.service import SourceService

SAMPLE_ORDERS_PY = """from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1")


class CreateOrderRequest(BaseModel):
    customer_id: str
    amount_cents: int


async def verify_bearer_token(authorization: str = "") -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AUTH_INVALID_TOKEN",
        )
    return {"user_id": "u-123", "scope": "write:orders"}


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderRequest,
    auth: dict = Depends(verify_bearer_token),
) -> dict:
    \"\"\"Creates a customer order after validating bearer authorization token.\"\"\"
    return {"order_id": "ord-888", "status": "created"}
"""

SAMPLE_AUTH_GUIDE_MD = """# Authorization Troubleshooting Guide

If you receive an HTTP 401 Unauthorized with code `AUTH_INVALID_TOKEN`:
Ensure the Authorization header is set with a valid Bearer token.
"""

SAMPLE_OPENAPI_SPEC = """openapi: 3.0.3
info:
  title: Orders API
  version: 1.0.0
paths:
  /api/v1/orders:
    post:
      summary: Create order
      operationId: createOrder
      responses:
        '401':
          description: AUTH_INVALID_TOKEN
"""


def test_cross_source_correlation_docs_spec_code() -> None:
    proj_repo = InMemoryProjectRepository()
    src_repo = InMemorySourceRepository()
    doc_repo = InMemoryDocumentRepository()

    proj_repo.create(Project(id="proj-e2e", name="E2E Orders Project"))

    source_service = SourceService(
        project_repo=proj_repo,
        source_repo=src_repo,
        document_repo=doc_repo,
    )
    retrieval_service = RetrievalService(
        source_repo=src_repo,
        document_repo=doc_repo,
    )
    code_service = CodeAnalysisService(retrieval_service=retrieval_service)

    # 1. Register Markdown docs
    src_repo.create(
        Source(
            id="src-doc",
            project_id="proj-e2e",
            name="Auth Troubleshooting",
            source_type=SourceType.MARKDOWN,
            config={"raw_content": SAMPLE_AUTH_GUIDE_MD, "canonical_path": "docs/troubleshooting.md"},
        )
    )
    source_service.sync("src-doc")

    # 2. Register OpenAPI spec
    src_repo.create(
        Source(
            id="src-spec",
            project_id="proj-e2e",
            name="Orders Spec",
            source_type=SourceType.OPENAPI,
            config={"raw_content": SAMPLE_OPENAPI_SPEC, "canonical_path": "specs/orders.yaml"},
        )
    )
    source_service.sync("src-spec")

    # 3. Register Repository Code
    src_repo.create(
        Source(
            id="src-code",
            project_id="proj-e2e",
            name="Backend Code",
            source_type=SourceType.REPOSITORY,
            config={
                "raw_files": [
                    {"path": "src/routes/orders.py", "content": SAMPLE_ORDERS_PY},
                ]
            },
        )
    )
    res_code_sync = source_service.sync("src-code")
    assert res_code_sync.status == SourceStatus.SYNCED
    assert res_code_sync.chunk_count >= 2

    # 4. Inspect route using CodeAnalysisService
    route_evidence = code_service.inspect_route("proj-e2e", method="POST", path="/orders")
    assert route_evidence is not None
    assert "create_order" in route_evidence.text
    assert route_evidence.provenance.source_type == SourceType.REPOSITORY
    assert route_evidence.provenance.canonical_path == "src/routes/orders.py"
    assert route_evidence.provenance.start_line is not None

    # 5. Hybrid Search across all 3 source types for "AUTH_INVALID_TOKEN"
    scope = RetrievalScope(project_id="proj-e2e")
    results = retrieval_service.search("AUTH_INVALID_TOKEN", scope=scope, limit=10)

    retrieved_source_types = {hit.provenance.source_type for hit in results}
    # All 3 source types (markdown, openapi, repository) contain and retrieve AUTH_INVALID_TOKEN!
    assert SourceType.MARKDOWN in retrieved_source_types
    assert SourceType.OPENAPI in retrieved_source_types
    assert SourceType.REPOSITORY in retrieved_source_types
