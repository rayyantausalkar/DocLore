from doclore_api.models import Chunk, Provenance, SourceType
from doclore_api.retrieval.bm25 import BM25Index


def _create_chunk(cid: str, text: str) -> Chunk:
    return Chunk(
        id=cid,
        document_id="doc-1",
        text=text,
        provenance=Provenance(
            project_id="proj-1",
            source_id="src-1",
            document_id="doc-1",
            chunk_id=cid,
            source_type=SourceType.MARKDOWN,
            canonical_path="guide.md",
            source_revision="rev-1",
            start_line=1,
            end_line=5,
        ),
    )


def test_bm25_matches_exact_technical_identifiers() -> None:
    chunks = [
        _create_chunk("chk-auth-err", "When credentials expire, the API returns AUTH_INVALID_TOKEN with code 401."),
        _create_chunk("chk-rate-err", "Rate limit exceeded returns 429 Too Many Requests with Retry-After header."),
        _create_chunk("chk-db-cfg", "Set DATABASE_URL to postgresql://user:pass@localhost:5432/doclore."),
    ]

    index = BM25Index()
    index.index_chunks(chunks)

    # 1. Search for exact identifier
    res1 = index.search("AUTH_INVALID_TOKEN")
    assert len(res1) > 0
    assert res1[0][0] == "chk-auth-err"

    # 2. Search for status code
    res2 = index.search("429")
    assert len(res2) > 0
    assert res2[0][0] == "chk-rate-err"

    # 3. Search for header name
    res3 = index.search("Retry-After")
    assert len(res3) > 0
    assert res3[0][0] == "chk-rate-err"


def test_bm25_returns_empty_when_no_terms_match() -> None:
    chunks = [
        _create_chunk("chk-1", "Only python code and fastapi setup instructions here."),
    ]
    index = BM25Index()
    index.index_chunks(chunks)

    res = index.search("kubernetes ingress controller")
    assert res == []
