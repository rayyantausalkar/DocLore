import ast
import hashlib
import os
from typing import Any, Optional

from doclore_api.ingestion.code_parsers import (
    GoScanner,
    JavaScriptTypeScriptScanner,
    MarkdownSectionScanner,
    PythonASTVisitor,
    RustScanner,
    universal_line_window_chunk,
)
from doclore_api.models import Chunk, Document, Provenance, Source, SourceType


DEFAULT_REPOSITORY_EXTENSIONS: tuple[str, ...] = (
    # Python
    ".py",
    # JavaScript & TypeScript
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    # Systems & Compiled
    ".go", ".rs", ".java", ".kt", ".scala", ".cs",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    # Web & Style
    ".html", ".css", ".scss", ".sass", ".less", ".vue", ".svelte",
    # Shell & Database
    ".sh", ".bash", ".zsh", ".ps1", ".sql",
    # Configs & Schemas
    ".json", ".yaml", ".yml", ".toml", ".ini", ".env.example", ".xml",
    # Documentation & Text
    ".md", ".markdown", ".rst", ".txt",
)

EXACT_FILENAME_MATCHES: set[str] = {
    "Dockerfile",
    "Makefile",
    "Procfile",
    "Gemfile",
    "Rakefile",
    "CMakeLists.txt",
}

DEFAULT_IGNORE_DIRS: set[str] = {
    ".git", ".github", ".venv", "venv", "env", "__pycache__", "node_modules",
    ".pytest_cache", "dist", "build", ".next", ".turbo", "coverage",
    ".idea", ".vscode", "target", "bin", "obj", ".gradle", ".cargo", "vendor",
    "__snapshots__", ".mypy_cache", ".ruff_cache", ".tox",
}

DEFAULT_IGNORE_FILES: set[str] = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock",
    "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock",
}

MAX_FILE_SIZE_BYTES = 1024 * 1024  # 1 MB


def get_file_language(canonical_path: str) -> str:
    lower_path = canonical_path.lower()
    filename = os.path.basename(lower_path)

    if filename == "dockerfile":
        return "dockerfile"
    if filename == "makefile":
        return "makefile"

    ext_map = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".kt": "kotlin",
        ".cs": "csharp",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".vue": "vue",
        ".svelte": "svelte",
        ".sql": "sql",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".markdown": "markdown",
        ".rst": "rst",
        ".txt": "text",
    }

    for ext, lang in ext_map.items():
        if lower_path.endswith(ext):
            return lang
    return "text"


class RepositoryAdapter:
    """Ingests source code repositories across all programming languages, configurations, and documentation.
    
    Uses AST analysis for Python, structural scanners for TypeScript, JavaScript, Go, Rust,
    and line-preserving sliding chunkers for configurations, schemas, and documents.
    """

    PARSER_VERSION = "doclore-multi-lang-v2"

    def __init__(self) -> None:
        self.js_ts_scanner = JavaScriptTypeScriptScanner()
        self.go_scanner = GoScanner()
        self.rust_scanner = RustScanner()
        self.markdown_scanner = MarkdownSectionScanner()

    @property
    def source_type(self) -> SourceType:
        return SourceType.REPOSITORY

    def parse(
        self,
        source: Source,
        content: str | bytes,
        canonical_path: str,
        revision: str,
    ) -> list[Document]:
        if isinstance(content, bytes):
            code_text = content.decode("utf-8", errors="replace")
        else:
            code_text = content

        lines = code_text.splitlines()
        if not lines:
            return []

        doc_id = self._generate_id(source.id, canonical_path)
        lang = get_file_language(canonical_path)
        extracted_items: list[dict[str, Any]] = []

        # 1. Python AST
        if lang == "python":
            try:
                tree = ast.parse(code_text, filename=canonical_path)
                visitor = PythonASTVisitor(source_lines=lines, rel_path=canonical_path)
                visitor.visit(tree)
                extracted_items = visitor.extracted_items
            except Exception:
                # If AST fails due to syntax error or template syntax, fall back
                pass

        # 2. JavaScript / TypeScript
        elif lang in {"javascript", "typescript", "vue", "svelte"}:
            extracted_items = self.js_ts_scanner.scan(lines=lines, rel_path=canonical_path)

        # 3. Go
        elif lang == "go":
            extracted_items = self.go_scanner.scan(lines=lines, rel_path=canonical_path)

        # 4. Rust
        elif lang == "rust":
            extracted_items = self.rust_scanner.scan(lines=lines, rel_path=canonical_path)

        # 5. Markdown / Docs
        elif lang in {"markdown", "rst"}:
            extracted_items = self.markdown_scanner.scan(lines=lines, rel_path=canonical_path)

        # 6. Fallback or universal line-window chunking
        if not extracted_items:
            if lang == "python":
                extracted_items = [
                    {
                        "name": "module",
                        "section_path": f"{canonical_path} > module",
                        "kind": "module",
                        "start_line": 1,
                        "end_line": len(lines),
                        "text": code_text,
                        "metadata": {"fallback": True},
                    }
                ]
            else:
                extracted_items = universal_line_window_chunk(
                    lines=lines,
                    rel_path=canonical_path,
                    lang=lang,
                    window_size=60,
                    overlap=10,
                )

        chunks: list[Chunk] = []
        for idx, item in enumerate(extracted_items, start=1):
            chunk_id = f"chk-code-{self._slugify(canonical_path)}-{idx}"
            provenance = Provenance(
                project_id=source.project_id,
                source_id=source.id,
                document_id=doc_id,
                chunk_id=chunk_id,
                source_type=SourceType.REPOSITORY,
                canonical_path=canonical_path,
                source_revision=revision,
                start_line=item["start_line"],
                end_line=item["end_line"],
                section_path=item["section_path"],
                parser_version=self.PARSER_VERSION,
            )
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=doc_id,
                    text=item["text"],
                    provenance=provenance,
                )
            )

        title = canonical_path.split("/")[-1].split("\\")[-1]
        return [
            Document(
                id=doc_id,
                source_id=source.id,
                title=title,
                canonical_path=canonical_path,
                revision=revision,
                chunks=chunks,
                raw_content=code_text,
            )
        ]

    def _slugify(self, text: str) -> str:
        import re
        return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:24]

    def _generate_id(self, source_id: str, path: str) -> str:
        digest = hashlib.sha256(f"{source_id}:{path}".encode("utf-8")).hexdigest()[:16]
        return f"doc-repo-{digest}"
