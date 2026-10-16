import hashlib
import re
from typing import Optional
from doclore_api.models import Chunk, Document, Provenance, Source, SourceType


class MarkdownAdapter:
    """Line-preserving Markdown ingestion adapter.
    
    Parses Markdown files into canonical documents and chunks with exact
    1-indexed line numbers and hierarchical section paths.
    """

    PARSER_VERSION = "doclore-markdown-v1"

    @property
    def source_type(self) -> SourceType:
        return SourceType.MARKDOWN

    def parse(
        self,
        source: Source,
        content: str | bytes,
        canonical_path: str,
        revision: str,
    ) -> list[Document]:
        if isinstance(content, bytes):
            text = content.decode("utf-8", errors="replace")
        else:
            text = content

        lines = text.splitlines()
        if not lines:
            # Handle empty document gracefully
            doc_id = self._generate_id(source.id, canonical_path)
            return [
                Document(
                    id=doc_id,
                    source_id=source.id,
                    title=canonical_path.split("/")[-1].split("\\")[-1],
                    canonical_path=canonical_path,
                    revision=revision,
                    chunks=[],
                )
            ]

        doc_id = self._generate_id(source.id, canonical_path)
        title = self._extract_title(lines, fallback=canonical_path.split("/")[-1].split("\\")[-1])
        chunks = self._chunk_lines(
            project_id=source.project_id,
            source_id=source.id,
            document_id=doc_id,
            canonical_path=canonical_path,
            revision=revision,
            lines=lines,
        )

        return [
            Document(
                id=doc_id,
                source_id=source.id,
                title=title,
                canonical_path=canonical_path,
                revision=revision,
                chunks=chunks,
                raw_content=text,
            )
        ]

    def _extract_title(self, lines: list[str], fallback: str) -> str:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return fallback

    def _chunk_lines(
        self,
        project_id: str,
        source_id: str,
        document_id: str,
        canonical_path: str,
        revision: str,
        lines: list[str],
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        heading_stack: list[tuple[int, str]] = []  # (level, text)
        
        current_chunk_lines: list[str] = []
        chunk_start_line: Optional[int] = None
        in_code_block = False
        code_fence = ""

        def current_section_path() -> str:
            return " > ".join(title for _, title in heading_stack) if heading_stack else "Document"

        def flush_current_chunk(end_line: int):
            nonlocal current_chunk_lines, chunk_start_line
            if not current_chunk_lines or chunk_start_line is None:
                current_chunk_lines = []
                chunk_start_line = None
                return
            
            chunk_text = "\n".join(current_chunk_lines).strip()
            if chunk_text:
                chunk_id = self._generate_chunk_id(document_id, chunk_start_line, end_line)
                provenance = Provenance(
                    project_id=project_id,
                    source_id=source_id,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    source_type=SourceType.MARKDOWN,
                    canonical_path=canonical_path,
                    source_revision=revision,
                    start_line=chunk_start_line,
                    end_line=end_line,
                    section_path=current_section_path(),
                    parser_version=self.PARSER_VERSION,
                )
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        text=chunk_text,
                        provenance=provenance,
                    )
                )
            current_chunk_lines = []
            chunk_start_line = None

        header_regex = re.compile(r"^(#{1,6})\s+(.*)$")

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Check for code fence start/end
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fence_marker = stripped[:3]
                if not in_code_block:
                    in_code_block = True
                    code_fence = fence_marker
                elif stripped.startswith(code_fence):
                    in_code_block = False
                    code_fence = ""

            # Heading detected outside code blocks
            if not in_code_block:
                header_match = header_regex.match(stripped)
                if header_match:
                    # Flush previous content before new heading
                    if current_chunk_lines and chunk_start_line is not None:
                        flush_current_chunk(idx - 1)

                    level = len(header_match.group(1))
                    heading_text = header_match.group(2).strip()

                    # Pop headings at or deeper than current level
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()
                    heading_stack.append((level, heading_text))

                    # Start chunk at this heading
                    chunk_start_line = idx
                    current_chunk_lines.append(line)
                    continue

            # Blank line outside code block can be a boundary if chunk is already substantive
            if not in_code_block and stripped == "":
                # If we have accumulated substantial text (> 500 chars), flush at paragraph break
                current_len = sum(len(l) for l in current_chunk_lines)
                if current_len > 400 and current_chunk_lines:
                    flush_current_chunk(idx - 1)
                elif current_chunk_lines:
                    current_chunk_lines.append(line)
                continue

            # Regular content line
            if chunk_start_line is None:
                chunk_start_line = idx
            current_chunk_lines.append(line)

        # Flush any remaining lines at EOF
        if current_chunk_lines and chunk_start_line is not None:
            flush_current_chunk(len(lines))

        return chunks

    def _generate_id(self, source_id: str, path: str) -> str:
        digest = hashlib.sha256(f"{source_id}:{path}".encode("utf-8")).hexdigest()[:16]
        return f"doc-{digest}"

    def _generate_chunk_id(self, doc_id: str, start: int, end: int) -> str:
        digest = hashlib.sha256(f"{doc_id}:{start}:{end}".encode("utf-8")).hexdigest()[:16]
        return f"chk-{start}-{end}-{digest[:8]}"
