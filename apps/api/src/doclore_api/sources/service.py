from datetime import datetime, timezone
import hashlib
import os
import tempfile
from typing import Optional
from doclore_api.ingestion.architecture import ArchitectureDiagramAdapter
from doclore_api.ingestion.github import GitHubRepoManager
from doclore_api.ingestion.issue_logs import IssueLogsAdapter
from doclore_api.ingestion.markdown import MarkdownAdapter
from doclore_api.ingestion.openapi import OpenAPIAdapter
from doclore_api.ingestion.repository import (
    DEFAULT_IGNORE_DIRS,
    DEFAULT_IGNORE_FILES,
    DEFAULT_REPOSITORY_EXTENSIONS,
    EXACT_FILENAME_MATCHES,
    MAX_FILE_SIZE_BYTES,
    RepositoryAdapter,
)
from doclore_api.ingestion.style_guide import StyleGuideAdapter
from doclore_api.models import Document, Source, SourceStatus, SourceType, SyncResult
from doclore_api.persistence.repository import (
    DocumentRepository,
    ProjectRepository,
    SourceRepository,
)


class UnsupportedSourceTypeError(Exception):
    pass


class SourceNotFoundError(Exception):
    pass


class SourceService:
    """Coordinates source registration, synchronization, and document indexing."""

    SUPPORTED_SOURCE_TYPES = {
        SourceType.MARKDOWN,
        SourceType.OPENAPI,
        SourceType.REPOSITORY,
        SourceType.ISSUE_LOGS,
        SourceType.STYLE_GUIDE,
        SourceType.ARCHITECTURE_DIAGRAM,
    }

    def __init__(
        self,
        project_repo: ProjectRepository,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        markdown_adapter: Optional[MarkdownAdapter] = None,
        openapi_adapter: Optional[OpenAPIAdapter] = None,
        repository_adapter: Optional[RepositoryAdapter] = None,
        issue_logs_adapter: Optional[IssueLogsAdapter] = None,
        style_guide_adapter: Optional[StyleGuideAdapter] = None,
        architecture_adapter: Optional[ArchitectureDiagramAdapter] = None,
        github_repo_manager: Optional[GitHubRepoManager] = None,
    ) -> None:
        self.project_repo = project_repo
        self.source_repo = source_repo
        self.document_repo = document_repo
        self.markdown_adapter = markdown_adapter or MarkdownAdapter()
        self.openapi_adapter = openapi_adapter or OpenAPIAdapter()
        self.repository_adapter = repository_adapter or RepositoryAdapter()
        self.issue_logs_adapter = issue_logs_adapter or IssueLogsAdapter()
        self.style_guide_adapter = style_guide_adapter or StyleGuideAdapter()
        self.architecture_adapter = architecture_adapter or ArchitectureDiagramAdapter()
        self.github_repo_manager = github_repo_manager or GitHubRepoManager()

    def _extract_content_payloads(self, source: Source) -> list[tuple[str, str]]:
        """Extracts (canonical_path, content_text) pairs from source config."""
        config = source.config
        payloads: list[tuple[str, str]] = []

        if any(k in config for k in ("file_path", "files", "repo_path")) and not (
            os.getenv("DOCLORE_ALLOW_LOCAL_REPOS", "").lower() in {"1", "true", "yes"}
        ):
            raise ValueError(
                "Reading files from the server's filesystem is disabled. "
                "Provide 'raw_content' or a GitHub URL instead."
            )

        if "raw_content" in config:
            raw_text = config["raw_content"]
            canonical_path = config.get("canonical_path", f"{source.name}.md")
            payloads.append((canonical_path, raw_text))

        elif "file_path" in config:
            file_path = config["file_path"]
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Source file not found at: {file_path}")
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                payloads.append((file_path, f.read()))

        elif "files" in config:
            for file_entry in config["files"]:
                file_path = file_entry["path"]
                content = file_entry.get("content")
                if content is None and os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                if content is not None:
                    payloads.append((file_path, content))

        elif "repo_path" in config:
            repo_path = config["repo_path"]
            if not os.path.isdir(repo_path):
                raise FileNotFoundError(f"Repository directory not found at: {repo_path}")
            
            allowed_extensions = tuple(config.get("file_extensions") or DEFAULT_REPOSITORY_EXTENSIONS)
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".git")]
                for file_name in files:
                    if file_name in DEFAULT_IGNORE_FILES or file_name.endswith((".min.js", ".min.css", ".map")):
                        continue
                    
                    has_matching_ext = any(file_name.lower().endswith(ext) for ext in allowed_extensions)
                    is_exact_match = file_name in EXACT_FILENAME_MATCHES
                    if not (has_matching_ext or is_exact_match):
                        continue

                    full_p = os.path.join(root, file_name)
                    try:
                        stat = os.stat(full_p)
                        if stat.st_size > MAX_FILE_SIZE_BYTES or stat.st_size == 0:
                            continue
                        
                        with open(full_p, "rb") as bf:
                            header = bf.read(8000)
                            if b"\x00" in header:
                                continue
                        
                        with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                            rel_p = os.path.relpath(full_p, repo_path).replace("\\", "/")
                            payloads.append((rel_p, f.read()))
                    except (OSError, PermissionError):
                        continue

        elif "github_url" in config:
            github_url = config["github_url"]
            branch = config.get("branch")
            subpath = config.get("subpath")
            file_extensions = config.get("file_extensions")
            storage_base = config.get("storage_dir") or os.path.join(tempfile.gettempdir(), "doclore_github_repos")
            target_dir = os.path.join(storage_base, source.id)
            commit_hash, git_payloads = self.github_repo_manager.sync_and_extract_files(
                github_url=github_url,
                target_dir=target_dir,
                branch=branch,
                subpath=subpath,
                file_extensions=tuple(file_extensions) if file_extensions else None,
            )
            source.config["commit_hash"] = commit_hash
            payloads.extend(git_payloads)

        elif "raw_files" in config:
            for file_entry in config["raw_files"]:
                payloads.append((file_entry["path"], file_entry["content"]))

        else:
            raise ValueError(
                "Source config must contain 'github_url', 'raw_content', 'file_path', 'files', 'repo_path', or 'raw_files'."
            )

        return payloads

    def _compute_revision(self, payloads: list[tuple[str, str]]) -> str:
        hasher = hashlib.sha256()
        for path, content in sorted(payloads, key=lambda x: x[0]):
            hasher.update(path.encode("utf-8"))
            hasher.update(b"\x00")
            hasher.update(content.encode("utf-8"))
            hasher.update(b"\x00")
        return hasher.hexdigest()[:16]

    def sync(self, source_id: str, force: bool = False) -> SyncResult:
        source = self.source_repo.get(source_id)
        if not source:
            raise SourceNotFoundError(f"Source with id '{source_id}' was not found.")

        if source.source_type not in self.SUPPORTED_SOURCE_TYPES:
            err_msg = (
                f"Source type '{source.source_type.value}' is not supported yet. "
                f"Currently supported: {[st.value for st in self.SUPPORTED_SOURCE_TYPES]}"
            )
            source.status = SourceStatus.FAILED
            source.error_message = err_msg
            self.source_repo.update(source)
            raise UnsupportedSourceTypeError(err_msg)

        try:
            payloads = self._extract_content_payloads(source)
            revision = self._compute_revision(payloads)

            # Idempotency check: if unchanged and previously synced, skip re-parsing
            if (
                not force
                and source.status == SourceStatus.SYNCED
                and source.current_revision == revision
            ):
                existing_docs = self.document_repo.list_by_source(source_id)
                total_chunks = sum(len(d.chunks) for d in existing_docs)
                return SyncResult(
                    source_id=source_id,
                    status=SourceStatus.SYNCED,
                    revision=revision,
                    document_count=len(existing_docs),
                    chunk_count=total_chunks,
                    is_idempotent_skip=True,
                )

            source.status = SourceStatus.SYNCING
            self.source_repo.update(source)

            documents: list[Document] = []
            for canonical_path, content in payloads:
                if source.source_type == SourceType.OPENAPI:
                    docs = self.openapi_adapter.parse(
                        source=source,
                        content=content,
                        canonical_path=canonical_path,
                        revision=revision,
                    )
                elif source.source_type == SourceType.REPOSITORY:
                    docs = self.repository_adapter.parse(
                        source=source,
                        content=content,
                        canonical_path=canonical_path,
                        revision=revision,
                    )
                elif source.source_type == SourceType.ISSUE_LOGS:
                    docs = self.issue_logs_adapter.parse(
                        source=source,
                        content=content,
                        canonical_path=canonical_path,
                        revision=revision,
                    )
                elif source.source_type == SourceType.STYLE_GUIDE:
                    docs = self.style_guide_adapter.parse(
                        source=source,
                        content=content,
                        canonical_path=canonical_path,
                        revision=revision,
                    )
                elif source.source_type == SourceType.ARCHITECTURE_DIAGRAM:
                    docs = self.architecture_adapter.parse(
                        source=source,
                        content=content,
                        canonical_path=canonical_path,
                        revision=revision,
                    )
                else:
                    docs = self.markdown_adapter.parse(
                        source=source,
                        content=content,
                        canonical_path=canonical_path,
                        revision=revision,
                    )
                documents.extend(docs)

            # Atomically save all documents/chunks for this source revision
            self.document_repo.save_documents(source_id, documents)

            # Update source record to SYNCED
            source.status = SourceStatus.SYNCED
            source.current_revision = revision
            source.last_synced_at = datetime.now(timezone.utc)
            source.error_message = None
            self.source_repo.update(source)

            total_chunks = sum(len(d.chunks) for d in documents)
            return SyncResult(
                source_id=source_id,
                status=SourceStatus.SYNCED,
                revision=revision,
                document_count=len(documents),
                chunk_count=total_chunks,
                is_idempotent_skip=False,
            )

        except Exception as exc:
            source.status = SourceStatus.FAILED
            source.error_message = str(exc)
            self.source_repo.update(source)
            raise
