from doclore_api.ingestion.repository import RepositoryAdapter
from doclore_api.models import Source, SourceType

SAMPLE_FASTAPI_CODE = """from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1")


class CreateOrderRequest(BaseModel):
    customer_id: str
    amount_cents: int


async def verify_bearer_token(token: str = "") -> dict:
    if not token.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AUTH_INVALID_TOKEN",
        )
    return {"sub": "user-123", "scope": "write:orders"}


@router.post("/orders", status_code=201)
async def create_order(
    payload: CreateOrderRequest,
    auth: dict = Depends(verify_bearer_token),
) -> dict:
    \"\"\"Process customer order after verifying bearer token.\"\"\"
    return {"order_id": "ord-999", "status": "confirmed"}
"""


def test_python_ast_adapter_extracts_routes_and_symbols() -> None:
    source = Source(
        id="src-code-1",
        project_id="proj-code-test",
        name="Orders Service Code",
        source_type=SourceType.REPOSITORY,
    )

    adapter = RepositoryAdapter()
    docs = adapter.parse(
        source=source,
        content=SAMPLE_FASTAPI_CODE,
        canonical_path="src/routes/orders.py",
        revision="rev-git-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "orders.py"
    assert doc.canonical_path == "src/routes/orders.py"

    chunks = doc.chunks
    assert len(chunks) >= 3

    # 1. Verify Route chunk
    route_chunks = [c for c in chunks if "route:POST /orders" in c.provenance.section_path]
    assert len(route_chunks) == 1
    route_chunk = route_chunks[0]
    assert "HTTP Endpoint: POST /orders" in route_chunk.text
    assert "create_order" in route_chunk.text
    assert "Depends(verify_bearer_token)" in route_chunk.text
    assert route_chunk.provenance.start_line == 22
    assert route_chunk.provenance.end_line >= 27
    assert route_chunk.provenance.source_type == SourceType.REPOSITORY

    # 2. Verify Auth Function chunk
    auth_chunks = [c for c in chunks if "func:verify_bearer_token" in c.provenance.section_path]
    assert len(auth_chunks) == 1
    auth_chunk = auth_chunks[0]
    assert "AUTH_INVALID_TOKEN" in auth_chunk.text
    assert auth_chunk.provenance.start_line == 12

    # 3. Verify Class chunk
    class_chunks = [c for c in chunks if "class:CreateOrderRequest" in c.provenance.section_path]
    assert len(class_chunks) == 1
    class_chunk = class_chunks[0]
    assert "CreateOrderRequest(BaseModel)" in class_chunk.text
    assert class_chunk.provenance.start_line == 7


def test_python_ast_adapter_handles_syntax_errors_gracefully() -> None:
    source = Source(
        id="src-broken",
        project_id="proj-1",
        name="Broken Code",
        source_type=SourceType.REPOSITORY,
    )
    adapter = RepositoryAdapter()
    docs = adapter.parse(
        source=source,
        content="def broken_syntax(:\n    pass invalid",
        canonical_path="src/broken.py",
        revision="rev-0",
    )
    assert len(docs) == 1
    # Fallback chunk covers the full file
    assert len(docs[0].chunks) == 1
    assert docs[0].chunks[0].provenance.section_path == "src/broken.py > module"
