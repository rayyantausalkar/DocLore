import hashlib
import json
import re
from typing import Any, Optional
import yaml

from doclore_api.models import Chunk, Document, Provenance, Source, SourceType


class IssueLogsAdapter:
    """Ingestion adapter for historical bug logs, incident reports, and postmortems.
    
    Extracts issue symptoms, identified root causes, and resolutions with
    exact 1-indexed line fidelity and structural paths.
    """

    PARSER_VERSION = "doclore-issue-logs-v1"

    @property
    def source_type(self) -> SourceType:
        return SourceType.ISSUE_LOGS

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

        stripped = text.strip()
        if not stripped:
            doc_id = self._generate_id(source.id, canonical_path)
            return [
                Document(
                    id=doc_id,
                    source_id=source.id,
                    title=canonical_path.split("/")[-1],
                    canonical_path=canonical_path,
                    revision=revision,
                    chunks=[],
                    raw_content=text,
                )
            ]

        # Check if content is JSON or structured YAML
        if (stripped.startswith("[") and stripped.endswith("]")) or (
            stripped.startswith("{") and stripped.endswith("}")
        ):
            try:
                parsed_json = json.loads(text)
                return self._parse_structured_issues(
                    source=source,
                    data=parsed_json,
                    text=text,
                    canonical_path=canonical_path,
                    revision=revision,
                )
            except Exception:
                pass

        # Parse as Markdown Issue Log / Postmortem
        return self._parse_markdown_issues(
            source=source,
            text=text,
            canonical_path=canonical_path,
            revision=revision,
        )

    def _parse_markdown_issues(
        self,
        source: Source,
        text: str,
        canonical_path: str,
        revision: str,
    ) -> list[Document]:
        lines = text.splitlines()
        doc_id = self._generate_id(source.id, canonical_path)
        chunks: list[Chunk] = []

        # Find document title
        title = canonical_path.split("/")[-1].replace(".md", "")
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Extract issue ID if present (e.g. Issue #104 or [ISSUE-104])
        issue_id_match = re.search(r"(?:Issue\s*#?|\[)([A-Za-z0-9_-]+)\]?", title, re.IGNORECASE)
        issue_ref = issue_id_match.group(1) if issue_id_match else "ISSUE"

        # Split into sections based on headings (## Symptoms, ## Root Cause, ## Resolution)
        section_starts: list[tuple[int, str, int]] = []  # (line_number, heading_text, level)
        for idx, line in enumerate(lines, start=1):
            match = re.match(r"^(#{1,4})\s+(.+)$", line)
            if match:
                level = len(match.group(1))
                heading = match.group(2).strip()
                section_starts.append((idx, heading, level))

        if not section_starts:
            # Entire file is one chunk
            chunks.append(
                Chunk(
                    id=f"chk-issue-{doc_id[:8]}-1",
                    document_id=doc_id,
                    text=text.strip(),
                    provenance=Provenance(
                        project_id=source.project_id,
                        source_id=source.id,
                        document_id=doc_id,
                        chunk_id=f"chk-issue-{doc_id[:8]}-1",
                        source_type=SourceType.ISSUE_LOGS,
                        canonical_path=canonical_path,
                        source_revision=revision,
                        start_line=1,
                        end_line=len(lines),
                        section_path=f"issues/{issue_ref}",
                        parser_version=self.PARSER_VERSION,
                    ),
                )
            )
        else:
            for i, (start_line, heading, level) in enumerate(section_starts):
                end_line = (
                    section_starts[i + 1][0] - 1
                    if i + 1 < len(section_starts)
                    else len(lines)
                )
                chunk_lines = lines[start_line - 1 : end_line]
                chunk_text = "\n".join(chunk_lines).strip()

                if not chunk_text:
                    continue

                slug = self._slugify(heading)
                chunk_id = f"chk-issue-{doc_id[:8]}-{start_line}-{slug}"
                section_path = f"issues/{issue_ref} > {heading}"

                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=doc_id,
                        text=chunk_text,
                        provenance=Provenance(
                            project_id=source.project_id,
                            source_id=source.id,
                            document_id=doc_id,
                            chunk_id=chunk_id,
                            source_type=SourceType.ISSUE_LOGS,
                            canonical_path=canonical_path,
                            source_revision=revision,
                            start_line=start_line,
                            end_line=end_line,
                            section_path=section_path,
                            parser_version=self.PARSER_VERSION,
                        ),
                    )
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

    def _parse_structured_issues(
        self,
        source: Source,
        data: Any,
        text: str,
        canonical_path: str,
        revision: str,
    ) -> list[Document]:
        lines = text.splitlines()
        doc_id = self._generate_id(source.id, canonical_path)
        items = data if isinstance(data, list) else [data]
        chunks: list[Chunk] = []

        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue

            issue_id = str(item.get("id") or item.get("issue_id") or f"ISSUE-{idx}")
            title = item.get("title", f"Incident Report {issue_id}")
            symptoms = item.get("symptoms", "")
            root_cause = item.get("root_cause", "")
            resolution = item.get("resolution", "")
            status = item.get("status", "resolved")
            affected = item.get("affected_endpoints") or item.get("components") or []

            # Find approximate line location in JSON text
            start_line, end_line = self._find_item_lines(lines, issue_id, title)

            # 1. Symptoms chunk
            symptoms_text = (
                f"# Issue Log: {issue_id} - {title}\n"
                f"Status: {status}\n"
                f"Affected: {', '.join(affected) if isinstance(affected, list) else affected}\n\n"
                f"## Symptoms\n{symptoms}\n"
            )
            chunks.append(
                Chunk(
                    id=f"chk-issue-{issue_id}-symptoms",
                    document_id=doc_id,
                    text=symptoms_text.strip(),
                    provenance=Provenance(
                        project_id=source.project_id,
                        source_id=source.id,
                        document_id=doc_id,
                        chunk_id=f"chk-issue-{issue_id}-symptoms",
                        source_type=SourceType.ISSUE_LOGS,
                        canonical_path=canonical_path,
                        source_revision=revision,
                        start_line=start_line,
                        end_line=end_line,
                        section_path=f"issues/{issue_id} > symptoms",
                        parser_version=self.PARSER_VERSION,
                    ),
                )
            )

            # 2. Root cause & Resolution chunk
            resolution_text = (
                f"# Issue Log: {issue_id} Resolution\n"
                f"Title: {title}\n\n"
                f"## Root Cause\n{root_cause}\n\n"
                f"## Verified Resolution\n{resolution}\n"
            )
            chunks.append(
                Chunk(
                    id=f"chk-issue-{issue_id}-resolution",
                    document_id=doc_id,
                    text=resolution_text.strip(),
                    provenance=Provenance(
                        project_id=source.project_id,
                        source_id=source.id,
                        document_id=doc_id,
                        chunk_id=f"chk-issue-{issue_id}-resolution",
                        source_type=SourceType.ISSUE_LOGS,
                        canonical_path=canonical_path,
                        source_revision=revision,
                        start_line=start_line,
                        end_line=end_line,
                        section_path=f"issues/{issue_id} > resolution",
                        parser_version=self.PARSER_VERSION,
                    ),
                )
            )

        title = canonical_path.split("/")[-1].replace(".json", "")
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

    def _find_item_lines(self, lines: list[str], identifier: str, fallback_term: str) -> tuple[int, int]:
        start = 1
        for idx, line in enumerate(lines, start=1):
            if identifier in line or fallback_term in line:
                start = idx
                break
        end = min(start + 25, len(lines))
        return start, max(start, end)

    def _slugify(self, text: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:24]

    def _generate_id(self, source_id: str, path: str) -> str:
        digest = hashlib.sha256(f"{source_id}:{path}".encode("utf-8")).hexdigest()[:16]
        return f"doc-issue-{digest}"
