from fastapi.testclient import TestClient
from doclore_api.main import app

SAMPLE_SPEC_YAML = """openapi: 3.0.3
info:
  title: Payments API
  version: 1.0.0
paths:
  /api/v1/payments:
    post:
      summary: Process transaction
      security:
        - BearerAuth: []
      responses:
        '401':
          description: Unauthorized
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
"""


def test_get_citation_context_endpoint() -> None:
    with TestClient(app) as client:
        # 1. Create project
        proj_res = client.post("/api/v1/projects", json={"name": "Payments Project"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        # 2. Register source
        src_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Payments Spec",
                "source_type": "openapi",
                "config": {
                    "raw_content": SAMPLE_SPEC_YAML,
                    "canonical_path": "specs/payments.yaml",
                },
            },
        )
        assert src_res.status_code == 201
        source_id = src_res.json()["id"]

        # 3. Sync source
        sync_res = client.post(f"/api/v1/sources/{source_id}/sync")
        assert sync_res.status_code == 200

        # 4. Get documents and find a chunk
        docs_res = client.get(f"/api/v1/sources/{source_id}/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        assert len(docs) > 0
        chunk = docs[0]["chunks"][0]
        chunk_id = chunk["id"]

        # 5. Fetch citation context
        context_res = client.get(f"/api/v1/citations/{chunk_id}/context")
        assert context_res.status_code == 200
        data = context_res.json()

        assert data["chunk_id"] == chunk_id
        assert data["canonical_path"] == "specs/payments.yaml"
        assert data["source_type"] == "openapi"
        assert len(data["surrounding_lines"]) > 0

        # Verify surrounding lines include line numbers and highlight flags
        has_highlight = any(line["is_highlighted"] for line in data["surrounding_lines"])
        if data["start_line"] is not None:
            assert has_highlight is True

        for line in data["surrounding_lines"]:
            assert "line_number" in line
            assert "content" in line
            assert "is_highlighted" in line


def test_get_citation_context_not_found() -> None:
    with TestClient(app) as client:
        res = client.get("/api/v1/citations/non-existent-chunk-999/context")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()
