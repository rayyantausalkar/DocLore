from fastapi.testclient import TestClient
from doclore_api.ingestion.style_guide import StyleGuideAdapter
from doclore_api.main import app
from doclore_api.models import Source, SourceType

SAMPLE_MARKDOWN_GUIDE = """# Engineering API Style Guide & Security Standards

All internal and external microservices must adhere strictly to these architectural standards.

## Rule [SEC-001]: Bearer Token Authorization Requirements
Every route handling customer data or mutation operations must enforce OAuth2 Bearer authentication.
The Authorization header must begin with the exact string prefix `Bearer `.
Missing, malformed, or expired tokens must immediately yield HTTP 401 Unauthorized with code `AUTH_INVALID_TOKEN`.

## Rule [API-002]: Error Response Payload Envelope
All error responses from HTTP 400 through 599 must conform to the standard RFC 7807 Problem Details:
```json
{
  "detail": "Descriptive human-readable resolution message",
  "status_code": 401
}
```

## Rule [DEP-003]: Endpoint Sunset & Deprecation Policy
Deprecated endpoints must emit the `Sunset` HTTP response header with an RFC 1123 date stamp.
"""

SAMPLE_JSON_GUIDE = """[
  {
    "id": "SEC-001",
    "name": "Bearer Token Header Enforcement",
    "category": "security",
    "requirement": "Endpoints requiring authorization must declare Depends(verify_bearer_token).",
    "rationale": "Prevents accidental unauthenticated access across microservices.",
    "remediation": "Add dependencies=[Depends(verify_bearer_token)] to route decorator."
  }
]"""


def test_style_guide_adapter_markdown_parsing() -> None:
    adapter = StyleGuideAdapter()
    source = Source(
        id="src-guide-test",
        project_id="proj-test",
        name="API Standards",
        source_type=SourceType.STYLE_GUIDE,
    )

    docs = adapter.parse(
        source=source,
        content=SAMPLE_MARKDOWN_GUIDE,
        canonical_path="guides/api-security-style-guide.md",
        revision="rev-style-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source_id == "src-guide-test"
    assert "Engineering API Style Guide" in doc.title
    assert doc.raw_content == SAMPLE_MARKDOWN_GUIDE

    chunks = doc.chunks
    assert len(chunks) >= 3

    # Check SEC-001 rule chunk
    sec_chunk = next(c for c in chunks if "SEC-001" in c.provenance.section_path)
    assert sec_chunk.provenance.start_line is not None
    assert sec_chunk.provenance.end_line is not None
    assert sec_chunk.provenance.start_line <= sec_chunk.provenance.end_line
    assert "AUTH_INVALID_TOKEN" in sec_chunk.text
    assert sec_chunk.provenance.source_type == SourceType.STYLE_GUIDE

    # Check API-002 rule chunk
    api_chunk = next(c for c in chunks if "API-002" in c.provenance.section_path)
    assert "RFC 7807" in api_chunk.text


def test_style_guide_adapter_json_parsing() -> None:
    adapter = StyleGuideAdapter()
    source = Source(
        id="src-json-guide",
        project_id="proj-test",
        name="Security Policy JSON",
        source_type=SourceType.STYLE_GUIDE,
    )

    docs = adapter.parse(
        source=source,
        content=SAMPLE_JSON_GUIDE,
        canonical_path="standards/sec-policies.json",
        revision="rev-json-style-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert len(doc.chunks) == 1
    chunk = doc.chunks[0]
    assert "SEC-001" in chunk.id
    assert "Depends(verify_bearer_token)" in chunk.text
    assert chunk.provenance.source_type == SourceType.STYLE_GUIDE


def test_style_guide_sync_and_retrieval_integration() -> None:
    with TestClient(app) as client:
        # 1. Create project
        proj_res = client.post("/api/v1/projects", json={"name": "Style Guide Workspace"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        # 2. Register Style Guide source
        src_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Internal Style Guide",
                "source_type": "style_guide",
                "config": {
                    "raw_content": SAMPLE_MARKDOWN_GUIDE,
                    "canonical_path": "standards/api-style-guide.md",
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

        # 4. Search across style guide
        search_res = client.post(
            f"/api/v1/projects/{project_id}/search",
            json={"query": "SEC-001 Bearer Token Authorization Requirements", "limit": 3},
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["total_results"] > 0
        top_match = search_data["results"][0]
        assert top_match["provenance"]["source_type"] == "style_guide"
        assert top_match["provenance"]["start_line"] is not None

        # 5. Fetch citation context
        chunk_id = top_match["chunk_id"]
        ctx_res = client.get(f"/api/v1/citations/{chunk_id}/context")
        assert ctx_res.status_code == 200
        ctx_data = ctx_res.json()
        assert ctx_data["source_type"] == "style_guide"
        assert any(l["is_highlighted"] for l in ctx_data["surrounding_lines"])
