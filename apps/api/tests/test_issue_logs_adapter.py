from fastapi.testclient import TestClient
from doclore_api.ingestion.issue_logs import IssueLogsAdapter
from doclore_api.main import app
from doclore_api.models import Source, SourceType

SAMPLE_MARKDOWN_ISSUE = """# Issue #104: 401 Unauthorized on POST /orders in staging

**Status:** Resolved
**Severity:** High
**Component:** orders-service

## Symptoms
Client services report HTTP 401 Unauthorized when invoking POST /api/v1/orders with Bearer token.
The error detail was AUTH_INVALID_TOKEN: Missing Bearer token in header.

## Root Cause
The FastAPI route handler declared `auth: dict = Depends(verify_bearer_token)` as a standard parameter
instead of passing it to `@router.post(..., dependencies=[...])`.

## Resolution
Update the endpoint decorator to declare `dependencies=[Depends(verify_bearer_token)]`.
Ensure the Authorization header is passed across the ingress gateway.
"""

SAMPLE_JSON_ISSUES = """[
  {
    "id": "INCIDENT-204",
    "title": "Staging 401 token authentication failure",
    "status": "resolved",
    "symptoms": "Clients get 401 AUTH_INVALID_TOKEN when Bearer token lacks prefix.",
    "root_cause": "Token validator requires exact 'Bearer ' string prefix in header.",
    "resolution": "Update client library to format headers with Bearer prefix."
  }
]"""


def test_issue_logs_adapter_markdown_parsing() -> None:
    adapter = IssueLogsAdapter()
    source = Source(
        id="src-issues-test",
        project_id="proj-test",
        name="Bug Postmortems",
        source_type=SourceType.ISSUE_LOGS,
    )

    docs = adapter.parse(
        source=source,
        content=SAMPLE_MARKDOWN_ISSUE,
        canonical_path="issues/issue-104-auth-postmortem.md",
        revision="rev-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source_id == "src-issues-test"
    assert "Issue #104" in doc.title
    assert doc.raw_content == SAMPLE_MARKDOWN_ISSUE

    chunks = doc.chunks
    assert len(chunks) >= 3

    # Check that sections are extracted with 1-indexed line numbers
    symptoms_chunk = next(c for c in chunks if "Symptoms" in c.provenance.section_path)
    assert symptoms_chunk.provenance.start_line is not None
    assert symptoms_chunk.provenance.end_line is not None
    assert symptoms_chunk.provenance.start_line <= symptoms_chunk.provenance.end_line
    assert "401 Unauthorized" in symptoms_chunk.text

    cause_chunk = next(c for c in chunks if "Root Cause" in c.provenance.section_path)
    assert "FastAPI route handler" in cause_chunk.text

    resolution_chunk = next(c for c in chunks if "Resolution" in c.provenance.section_path)
    assert "dependencies=[Depends(verify_bearer_token)]" in resolution_chunk.text


def test_issue_logs_adapter_json_parsing() -> None:
    adapter = IssueLogsAdapter()
    source = Source(
        id="src-json-issues",
        project_id="proj-test",
        name="Jira Exports",
        source_type=SourceType.ISSUE_LOGS,
    )

    docs = adapter.parse(
        source=source,
        content=SAMPLE_JSON_ISSUES,
        canonical_path="issues/incidents.json",
        revision="rev-json-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert len(doc.chunks) == 2  # symptoms and resolution chunks

    symptoms_chunk = next(c for c in doc.chunks if "symptoms" in c.provenance.section_path)
    assert "INCIDENT-204" in symptoms_chunk.provenance.section_path
    assert "AUTH_INVALID_TOKEN" in symptoms_chunk.text


def test_issue_logs_sync_and_retrieval_integration() -> None:
    with TestClient(app) as client:
        # 1. Create project
        proj_res = client.post("/api/v1/projects", json={"name": "Postmortem Workspace"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        # 2. Register Issue Logs source
        src_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Incident Postmortems",
                "source_type": "issue_logs",
                "config": {
                    "raw_content": SAMPLE_MARKDOWN_ISSUE,
                    "canonical_path": "postmortems/issue-104.md",
                },
            },
        )
        assert src_res.status_code == 201
        source_id = src_res.json()["id"]

        # 3. Sync source
        sync_res = client.post(f"/api/v1/sources/{source_id}/sync")
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["status"] == "synced"
        assert sync_data["document_count"] == 1
        assert sync_data["chunk_count"] >= 3

        # 4. Search across issue logs
        search_res = client.post(
            f"/api/v1/projects/{project_id}/search",
            json={"query": "AUTH_INVALID_TOKEN root cause and resolution", "limit": 3},
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["total_results"] > 0
        top_match = search_data["results"][0]
        assert top_match["provenance"]["source_type"] == "issue_logs"
        assert top_match["provenance"]["start_line"] is not None

        # 5. Fetch citation context
        chunk_id = top_match["chunk_id"]
        ctx_res = client.get(f"/api/v1/citations/{chunk_id}/context")
        assert ctx_res.status_code == 200
        ctx_data = ctx_res.json()
        assert ctx_data["source_type"] == "issue_logs"
        assert any(l["is_highlighted"] for l in ctx_data["surrounding_lines"])
