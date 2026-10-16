import pytest
from doclore_api.models import Project, Source, SourceStatus, SourceType
from doclore_api.persistence.memory import (
    InMemoryDocumentRepository,
    InMemoryProjectRepository,
    InMemorySourceRepository,
)
from doclore_api.sources.service import (
    SourceNotFoundError,
    SourceService,
    UnsupportedSourceTypeError,
)


@pytest.fixture
def service() -> SourceService:
    proj_repo = InMemoryProjectRepository()
    src_repo = InMemorySourceRepository()
    doc_repo = InMemoryDocumentRepository()

    proj_repo.create(Project(id="proj-test", name="Test Project"))
    return SourceService(
        project_repo=proj_repo,
        source_repo=src_repo,
        document_repo=doc_repo,
    )


def test_sync_markdown_source_success(service: SourceService) -> None:
    source = Source(
        id="src-md-1",
        project_id="proj-test",
        name="Developer Setup",
        source_type=SourceType.MARKDOWN,
        config={
            "raw_content": "# Setup\n\nRun `npm install` and then `npm run dev`.",
            "canonical_path": "README.md",
        },
    )
    service.source_repo.create(source)

    result = service.sync("src-md-1")

    assert result.status == SourceStatus.SYNCED
    assert result.document_count == 1
    assert result.chunk_count >= 1
    assert not result.is_idempotent_skip

    # Verify source was updated in repo
    updated_source = service.source_repo.get("src-md-1")
    assert updated_source is not None
    assert updated_source.status == SourceStatus.SYNCED
    assert updated_source.current_revision == result.revision
    assert updated_source.last_synced_at is not None

    # Verify document and chunks saved in repo
    docs = service.document_repo.list_by_source("src-md-1")
    assert len(docs) == 1
    assert docs[0].title == "Setup"
    assert len(docs[0].chunks) >= 1


def test_sync_markdown_source_idempotent_skip(service: SourceService) -> None:
    source = Source(
        id="src-idemp",
        project_id="proj-test",
        name="Troubleshooting",
        source_type=SourceType.MARKDOWN,
        config={"raw_content": "# FAQ\n\nRestart the container."},
    )
    service.source_repo.create(source)

    first_result = service.sync("src-idemp")
    assert not first_result.is_idempotent_skip

    second_result = service.sync("src-idemp")
    assert second_result.is_idempotent_skip
    assert second_result.revision == first_result.revision


def test_sync_markdown_source_force_refresh(service: SourceService) -> None:
    source = Source(
        id="src-force",
        project_id="proj-test",
        name="Troubleshooting",
        source_type=SourceType.MARKDOWN,
        config={"raw_content": "# FAQ\n\nRestart the container."},
    )
    service.source_repo.create(source)
    service.sync("src-force")

    forced_result = service.sync("src-force", force=True)
    assert not forced_result.is_idempotent_skip


def test_sync_rejects_unsupported_source_type(service: SourceService) -> None:
    restricted_service = SourceService(
        project_repo=service.project_repo,
        source_repo=service.source_repo,
        document_repo=service.document_repo,
    )
    restricted_service.SUPPORTED_SOURCE_TYPES = {SourceType.MARKDOWN}

    source = Source(
        id="src-unsupported",
        project_id="proj-test",
        name="Custom Diagram",
        source_type=SourceType.ARCHITECTURE_DIAGRAM,
        config={"diagrams": []},
    )
    restricted_service.source_repo.create(source)

    with pytest.raises(UnsupportedSourceTypeError) as exc_info:
        restricted_service.sync("src-unsupported")

    assert "not supported yet" in str(exc_info.value)
    updated_source = restricted_service.source_repo.get("src-unsupported")
    assert updated_source is not None
    assert updated_source.status == SourceStatus.FAILED


def test_sync_missing_source_raises_error(service: SourceService) -> None:
    with pytest.raises(SourceNotFoundError):
        service.sync("non-existent-source")
