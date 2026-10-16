import pytest
from doclore_api.models import Project, Source, SourceType
from doclore_api.persistence.memory import (
    InMemoryDocumentRepository,
    InMemoryProjectRepository,
    InMemorySourceRepository,
)
from doclore_api.retrieval.models import RetrievalScope
from doclore_api.retrieval.service import RetrievalService
from doclore_api.sources.service import SourceService


@pytest.fixture
def seeded_environment():
    proj_repo = InMemoryProjectRepository()
    src_repo = InMemorySourceRepository()
    doc_repo = InMemoryDocumentRepository()

    # Create project 1
    proj_repo.create(Project(id="proj-golden", name="Golden Project"))
    # Create project 2 for isolation testing
    proj_repo.create(Project(id="proj-other", name="Other Project"))

    source_service = SourceService(
        project_repo=proj_repo,
        source_repo=src_repo,
        document_repo=doc_repo,
    )
    retrieval_service = RetrievalService(
        source_repo=src_repo,
        document_repo=doc_repo,
    )

    # Ingest golden source into proj-golden
    auth_doc_content = """# Auth & Permissions Specification

## Bearer Token Authentication

Client applications must send an HTTP Authorization header in the format:

```http
Authorization: Bearer <access_token>
```

Tokens are validated against the internal RSA public key.

## Error Codes

### AUTH_INVALID_TOKEN

When a bearer token is malformed, expired, or signed by an untrusted key,
the server responds with HTTP 401 Unauthorized and errorCode `AUTH_INVALID_TOKEN`.

### AUTH_FORBIDDEN_SCOPE

If the token is valid but lacks the required permission scope (e.g. `write:diagnostics`),
the server returns HTTP 403 Forbidden with `AUTH_FORBIDDEN_SCOPE`.
"""

    src_repo.create(
        Source(
            id="src-golden-auth",
            project_id="proj-golden",
            name="Auth Spec",
            source_type=SourceType.MARKDOWN,
            config={
                "raw_content": auth_doc_content,
                "canonical_path": "docs/specs/auth.md",
            },
        )
    )
    source_service.sync("src-golden-auth")

    # Ingest database guide into proj-golden
    db_doc_content = """# Database Configuration

Connect to PostgreSQL using the connection string:
```bash
postgresql://postgres:password@localhost:5432/doclore
```
Run migrations with `alembic upgrade head`.
"""
    src_repo.create(
        Source(
            id="src-golden-db",
            project_id="proj-golden",
            name="DB Config",
            source_type=SourceType.MARKDOWN,
            config={
                "raw_content": db_doc_content,
                "canonical_path": "docs/db.md",
            },
        )
    )
    source_service.sync("src-golden-db")

    # Ingest secret chunk into proj-other
    src_repo.create(
        Source(
            id="src-other-secret",
            project_id="proj-other",
            name="Confidential",
            source_type=SourceType.MARKDOWN,
            config={
                "raw_content": "# Secret\n\nSECRET_KEY_PROJ_OTHER=xyz987",
                "canonical_path": "secret.md",
            },
        )
    )
    source_service.sync("src-other-secret")

    return {
        "retrieval_service": retrieval_service,
        "proj_id": "proj-golden",
    }


def test_golden_query_exact_identifier_match(seeded_environment) -> None:
    service: RetrievalService = seeded_environment["retrieval_service"]
    proj_id: str = seeded_environment["proj_id"]

    scope = RetrievalScope(project_id=proj_id)
    # Golden Query 1: Exact error code
    results = service.search(query="AUTH_INVALID_TOKEN", scope=scope, limit=3)

    assert len(results) > 0
    top_hit = results[0]
    assert "AUTH_INVALID_TOKEN" in top_hit.text
    assert top_hit.provenance.canonical_path == "docs/specs/auth.md"
    assert top_hit.provenance.start_line is not None
    assert top_hit.provenance.end_line is not None
    assert top_hit.sparse_rank == 1


def test_golden_query_http_status_and_header(seeded_environment) -> None:
    service: RetrievalService = seeded_environment["retrieval_service"]
    proj_id: str = seeded_environment["proj_id"]

    scope = RetrievalScope(project_id=proj_id)
    # Golden Query 2: HTTP status + Authorization header
    results = service.search(query="401 unauthorized Authorization: Bearer", scope=scope, limit=3)

    assert len(results) > 0
    top_hit = results[0]
    assert "Bearer" in top_hit.text or "401" in top_hit.text
    assert top_hit.rrf_score > 0.0


def test_golden_query_scope_isolation(seeded_environment) -> None:
    service: RetrievalService = seeded_environment["retrieval_service"]
    proj_id: str = seeded_environment["proj_id"]

    scope = RetrievalScope(project_id=proj_id)
    # Search for a term that only exists in proj-other
    results = service.search(query="SECRET_KEY_PROJ_OTHER", scope=scope, limit=5)

    # Must NOT find chunks from proj-other!
    for hit in results:
        assert hit.provenance.project_id == proj_id
        assert "SECRET_KEY_PROJ_OTHER" not in hit.text
