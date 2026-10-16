from doclore_api.ingestion.markdown import MarkdownAdapter
from doclore_api.models import Source, SourceStatus, SourceType


def test_markdown_adapter_extracts_title_and_line_ranges() -> None:
    source = Source(
        id="src-test-1",
        project_id="proj-1",
        name="Auth Guide",
        source_type=SourceType.MARKDOWN,
    )

    markdown_sample = """# Authentication Guide

DocLore provides comprehensive developer documentation debugging.

## Bearer Token Setup

To authenticate your requests, attach the header:

```bash
Authorization: Bearer <token>
```

### Common Errors

If you receive an HTTP 401 Unauthorized status, verify your scope:
- read:logs
- write:diagnostics

## Refreshing Tokens

Tokens expire after 1 hour. Call the `/oauth/token` endpoint to refresh.
"""

    adapter = MarkdownAdapter()
    docs = adapter.parse(
        source=source,
        content=markdown_sample,
        canonical_path="docs/auth.md",
        revision="rev-abc123",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "Authentication Guide"
    assert doc.canonical_path == "docs/auth.md"
    assert doc.revision == "rev-abc123"

    assert len(doc.chunks) > 0

    # Verify each chunk has strictly valid 1-indexed line ranges and provenance
    for chunk in doc.chunks:
        assert chunk.provenance.project_id == "proj-1"
        assert chunk.provenance.source_id == "src-test-1"
        assert chunk.provenance.document_id == doc.id
        assert chunk.provenance.source_type == SourceType.MARKDOWN
        assert chunk.provenance.canonical_path == "docs/auth.md"
        assert chunk.provenance.source_revision == "rev-abc123"
        assert chunk.provenance.start_line is not None
        assert chunk.provenance.end_line is not None
        assert 1 <= chunk.provenance.start_line <= chunk.provenance.end_line

    # Check section hierarchy in the chunks
    section_paths = [c.provenance.section_path for c in doc.chunks]
    assert any("Authentication Guide" in sp for sp in section_paths)
    assert any("Bearer Token Setup" in sp for sp in section_paths)
    assert any("Common Errors" in sp for sp in section_paths)
    assert any("Refreshing Tokens" in sp for sp in section_paths)


def test_markdown_adapter_handles_empty_content() -> None:
    source = Source(
        id="src-empty",
        project_id="proj-1",
        name="Empty Doc",
        source_type=SourceType.MARKDOWN,
    )
    adapter = MarkdownAdapter()
    docs = adapter.parse(
        source=source,
        content="",
        canonical_path="docs/empty.md",
        revision="rev-0",
    )

    assert len(docs) == 1
    assert docs[0].title == "empty.md"
    assert docs[0].chunks == []
