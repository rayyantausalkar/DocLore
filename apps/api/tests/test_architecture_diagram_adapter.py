from fastapi.testclient import TestClient
from doclore_api.ingestion.architecture import ArchitectureDiagramAdapter
from doclore_api.main import app
from doclore_api.models import Source, SourceType

SAMPLE_MERMAID_SEQUENCE = """# Order Processing & Auth Sequence Architecture

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant IngressGateway as Ingress Gateway
    participant AuthService as Auth Service
    participant OrdersService as Orders Service

    Client->>IngressGateway: POST /api/v1/orders (Authorization: Bearer <jwt>)
    IngressGateway->>AuthService: Validate Bearer token
    AuthService-->>IngressGateway: 200 OK (Token claims: user_456, write:orders)
    IngressGateway->>OrdersService: Forward request with validated auth context
    OrdersService-->>Client: 201 Created (order_id: ord_777)
```
"""

SAMPLE_MERMAID_FLOWCHART = """# Orders Service Component Map

```mermaid
flowchart LR
    Client[Web & Mobile Client] -->|Bearer Auth / HTTPS| Gateway[Ingress Gateway]
    Gateway -->|Forward Auth Headers| OrdersAPI[FastAPI Orders Backend]
    OrdersAPI -->|Depends verify_bearer_token| SecurityModule[Auth Dependency]
```
"""

SAMPLE_JSON_TOPOLOGY = """{
  "system_name": "Orders Ecosystem",
  "components": [
    {
      "name": "Orders Backend",
      "role": "Order ingestion and processing",
      "technology": "FastAPI",
      "protocols": ["HTTPS", "BearerAuth"]
    }
  ],
  "flows": [
    {
      "from": "Client",
      "to": "Orders Backend",
      "protocol": "HTTPS",
      "security": "BearerAuth",
      "description": "Authenticated client order creation"
    }
  ]
}"""


def test_architecture_adapter_mermaid_sequence_parsing() -> None:
    adapter = ArchitectureDiagramAdapter()
    source = Source(
        id="src-arch-test",
        project_id="proj-test",
        name="Order Auth Sequence",
        source_type=SourceType.ARCHITECTURE_DIAGRAM,
    )

    docs = adapter.parse(
        source=source,
        content=SAMPLE_MERMAID_SEQUENCE,
        canonical_path="architecture/order-sequence.mmd",
        revision="rev-arch-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source_id == "src-arch-test"
    assert "Order Processing & Auth Sequence Architecture" in doc.title
    assert doc.raw_content == SAMPLE_MERMAID_SEQUENCE

    chunks = doc.chunks
    assert len(chunks) >= 2  # topology chunk + interaction call chunks

    # 1. Topology chunk
    topo_chunk = next(c for c in chunks if "topology" in c.provenance.section_path)
    assert topo_chunk.provenance.start_line == 1
    assert "sequenceDiagram" in topo_chunk.text

    # 2. Call interaction flow chunks
    auth_call_chunk = next(c for c in chunks if "AuthService" in c.text)
    assert auth_call_chunk.provenance.start_line is not None
    assert auth_call_chunk.provenance.end_line is not None
    assert auth_call_chunk.provenance.start_line <= auth_call_chunk.provenance.end_line
    assert auth_call_chunk.provenance.source_type == SourceType.ARCHITECTURE_DIAGRAM


def test_architecture_adapter_mermaid_flowchart_parsing() -> None:
    adapter = ArchitectureDiagramAdapter()
    source = Source(
        id="src-flow-test",
        project_id="proj-test",
        name="Orders Flowchart",
        source_type=SourceType.ARCHITECTURE_DIAGRAM,
    )

    docs = adapter.parse(
        source=source,
        content=SAMPLE_MERMAID_FLOWCHART,
        canonical_path="architecture/orders-flow.md",
        revision="rev-flow-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    chunks = doc.chunks
    assert len(chunks) >= 2

    # Verify flow edge chunk
    edge_chunk = next(c for c in chunks if "Bearer Auth" in c.text)
    assert "Gateway" in edge_chunk.text
    assert edge_chunk.provenance.start_line is not None


def test_architecture_adapter_json_topology_parsing() -> None:
    adapter = ArchitectureDiagramAdapter()
    source = Source(
        id="src-json-arch",
        project_id="proj-test",
        name="Ecosystem Model",
        source_type=SourceType.ARCHITECTURE_DIAGRAM,
    )

    docs = adapter.parse(
        source=source,
        content=SAMPLE_JSON_TOPOLOGY,
        canonical_path="architecture/topology.json",
        revision="rev-json-arch-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert len(doc.chunks) == 2  # 1 component + 1 flow chunk

    comp_chunk = next(c for c in doc.chunks if "Orders Backend" in c.text)
    assert "FastAPI" in comp_chunk.text


def test_architecture_diagram_sync_and_retrieval_integration() -> None:
    with TestClient(app) as client:
        # 1. Create project
        proj_res = client.post("/api/v1/projects", json={"name": "Architecture Workspace"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        # 2. Register Architecture Diagram source
        src_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Auth Flow Diagram",
                "source_type": "architecture_diagram",
                "config": {
                    "raw_content": SAMPLE_MERMAID_SEQUENCE,
                    "canonical_path": "architecture/auth-sequence.mmd",
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
        assert sync_data["chunk_count"] >= 2

        # 4. Search across architecture diagrams
        search_res = client.post(
            f"/api/v1/projects/{project_id}/search",
            json={"query": "IngressGateway AuthService Validate Bearer token", "limit": 3},
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["total_results"] > 0
        top_match = search_data["results"][0]
        assert top_match["provenance"]["source_type"] == "architecture_diagram"
        assert top_match["provenance"]["start_line"] is not None

        # 5. Fetch citation context
        chunk_id = top_match["chunk_id"]
        ctx_res = client.get(f"/api/v1/citations/{chunk_id}/context")
        assert ctx_res.status_code == 200
        ctx_data = ctx_res.json()
        assert ctx_data["source_type"] == "architecture_diagram"
        assert any(l["is_highlighted"] for l in ctx_data["surrounding_lines"])
