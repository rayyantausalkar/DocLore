from fastapi.testclient import TestClient

from doclore_api.main import app

SAMPLE_TROUBLESHOOTING_MD = """# Authorization Troubleshooting Guide

## Bearer Token Authentication

All API endpoints require an Authorization header with a valid bearer token:

```http
Authorization: Bearer <valid_jwt>
```

If the header is missing or does not start with `Bearer `, the server returns
HTTP 401 Unauthorized with code `AUTH_INVALID_TOKEN`.
"""

SAMPLE_ORDERS_SPEC_YAML = """openapi: 3.0.3
info:
  title: Orders Service
  version: 1.0.0
paths:
  /api/v1/orders:
    post:
      summary: Create customer order
      security:
        - BearerAuth:
            - write:orders
      responses:
        '401':
          description: AUTH_INVALID_TOKEN Missing or malformed bearer token
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
"""

SAMPLE_ORDERS_CODE_PY = """from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1")


async def verify_bearer_token(authorization: str = "") -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AUTH_INVALID_TOKEN: Missing Bearer token in header",
        )
    return {"user_id": "u-456", "scope": "write:orders"}


@router.post("/orders")
async def create_order(auth: dict = Depends(verify_bearer_token)) -> dict:
    return {"order_id": "ord-123", "status": "confirmed"}
"""


def test_diagnostic_engine_end_to_end_workflow() -> None:
    with TestClient(app) as client:
        # 1. Create project
        proj_res = client.post("/api/v1/projects", json={"name": "Diagnostic Demo Project"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        # 2. Register and sync Markdown Guide
        doc_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Auth Guide",
                "source_type": "markdown",
                "config": {
                    "raw_content": SAMPLE_TROUBLESHOOTING_MD,
                    "canonical_path": "docs/auth-guide.md",
                },
            },
        )
        assert doc_res.status_code == 201
        client.post(f"/api/v1/sources/{doc_res.json()['id']}/sync")

        # 3. Register and sync OpenAPI Spec
        spec_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Orders Spec",
                "source_type": "openapi",
                "config": {
                    "raw_content": SAMPLE_ORDERS_SPEC_YAML,
                    "canonical_path": "specs/orders.yaml",
                },
            },
        )
        assert spec_res.status_code == 201
        client.post(f"/api/v1/sources/{spec_res.json()['id']}/sync")

        # 4. Register and sync Python Code
        code_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Orders Code",
                "source_type": "repository",
                "config": {
                    "raw_files": [
                        {"path": "src/routes/orders.py", "content": SAMPLE_ORDERS_CODE_PY},
                    ],
                },
            },
        )
        assert code_res.status_code == 201
        client.post(f"/api/v1/sources/{code_res.json()['id']}/sync")

        # 5. Run diagnostic request
        diag_res = client.post(
            "/api/v1/diagnoses",
            json={
                "project_id": project_id,
                "query": "Why is calling POST /api/v1/orders failing with 401 AUTH_INVALID_TOKEN?",
            },
        )
        assert diag_res.status_code == 200
        report = diag_res.json()

        # Check Report fields
        assert report["project_id"] == project_id
        assert "AUTH_INVALID_TOKEN" in report["query"]
        assert len(report["summary"]) > 0
        assert len(report["root_cause"]) > 0
        assert len(report["recommended_actions"]) >= 2
        assert not report["insufficient_evidence"]

        # Check Workflow Trace contains all LangGraph nodes
        trace = report["workflow_trace"]
        assert any("Understand Query" in t for t in trace)
        assert any("Retrieve Multi-Source Evidence" in t for t in trace)
        assert any("Correlate Spec & AST Code" in t for t in trace)
        assert any("Synthesize Resolution" in t for t in trace)
        assert any("Validate Citations" in t for t in trace)

        # Check Citations: strictly grounded with valid line ranges
        citations = report["citations"]
        assert len(citations) > 0
        for cite in citations:
            assert cite["start_line"] is not None
            assert cite["end_line"] is not None
            assert cite["start_line"] <= cite["end_line"]
            assert len(cite["snippet"]) > 0
            assert cite["source_type"] in ["markdown", "openapi", "repository"]


def test_diagnostic_engine_insufficient_evidence_handling() -> None:
    with TestClient(app) as client:
        proj_res = client.post("/api/v1/projects", json={"name": "Empty Project"})
        project_id = proj_res.json()["id"]

        diag_res = client.post(
            "/api/v1/diagnoses",
            json={
                "project_id": project_id,
                "query": "Why did the kubernetes ingress controller timeout?",
            },
        )
        assert diag_res.status_code == 200
        report = diag_res.json()

        assert report["insufficient_evidence"] is True
        assert len(report["citations"]) == 0
        assert "Insufficient" in report["summary"]
