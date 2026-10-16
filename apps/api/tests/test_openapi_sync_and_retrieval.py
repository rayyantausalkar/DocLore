from doclore_api.models import Project, Source, SourceStatus, SourceType
from doclore_api.persistence.memory import (
    InMemoryDocumentRepository,
    InMemoryProjectRepository,
    InMemorySourceRepository,
)
from doclore_api.retrieval.models import RetrievalScope
from doclore_api.retrieval.service import RetrievalService
from doclore_api.sources.service import SourceService

OPENAPI_SPEC_SAMPLE = """openapi: 3.0.3
info:
  title: Payment & Invoicing Service
  version: 2.1.0
paths:
  /api/v1/invoices/{id}/pay:
    post:
      summary: Process payment for invoice
      operationId: payInvoice
      security:
        - OAuth2Bearer:
            - payments:write
      parameters:
        - name: id
          in: path
          required: true
          description: Unique invoice UUID
          schema:
            type: string
        - name: X-Payment-Nonce
          in: header
          required: true
          description: Client-generated nonce to prevent double charging
      responses:
        '200':
          description: Payment successful
        '401':
          description: Expired or missing OAuth2 bearer token
        '403':
          description: Missing scope payments:write
components:
  securitySchemes:
    OAuth2Bearer:
      type: http
      scheme: bearer
      bearerFormat: JWT
"""


def test_openapi_source_sync_and_hybrid_search() -> None:
    proj_repo = InMemoryProjectRepository()
    src_repo = InMemorySourceRepository()
    doc_repo = InMemoryDocumentRepository()

    proj_repo.create(Project(id="proj-api-test", name="Invoicing API Project"))

    source_service = SourceService(
        project_repo=proj_repo,
        source_repo=src_repo,
        document_repo=doc_repo,
    )
    retrieval_service = RetrievalService(
        source_repo=src_repo,
        document_repo=doc_repo,
    )

    # 1. Register OpenAPI source
    source = Source(
        id="src-invoicing-spec",
        project_id="proj-api-test",
        name="Invoicing OpenAPI Spec",
        source_type=SourceType.OPENAPI,
        config={
            "raw_content": OPENAPI_SPEC_SAMPLE,
            "canonical_path": "specs/invoicing.yaml",
        },
    )
    src_repo.create(source)

    # 2. Sync OpenAPI source
    sync_result = source_service.sync("src-invoicing-spec")
    assert sync_result.status == SourceStatus.SYNCED
    assert sync_result.document_count == 1
    assert sync_result.chunk_count >= 2

    # 3. Verify documents in repository
    docs = doc_repo.list_by_source("src-invoicing-spec")
    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "Payment & Invoicing Service"

    # 4. Search for header / parameter
    scope = RetrievalScope(project_id="proj-api-test")
    res_nonce = retrieval_service.search("X-Payment-Nonce", scope=scope, limit=3)
    assert len(res_nonce) > 0
    top_hit = res_nonce[0]
    assert "X-Payment-Nonce" in top_hit.text
    assert top_hit.provenance.source_type == SourceType.OPENAPI
    assert "paths./api/v1/invoices/{id}/pay.post" in top_hit.provenance.section_path

    # 5. Search for security scope and status code
    res_auth = retrieval_service.search("payments:write 401 OAuth2Bearer", scope=scope, limit=3)
    assert len(res_auth) > 0
    top_auth = res_auth[0]
    assert "payments:write" in top_auth.text
    assert top_auth.provenance.canonical_path == "specs/invoicing.yaml"
    assert top_auth.provenance.start_line is not None
