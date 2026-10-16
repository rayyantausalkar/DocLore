import hashlib
import json
import re
from typing import Any, Optional
import yaml

from doclore_api.models import Chunk, Document, Provenance, Source, SourceType


class StyleGuideAdapter:
    """Ingestion adapter for internal engineering style guides and conventions.
    
    Parses API guidelines, security requirements, and architectural standards
    into canonical chunks with exact 1-indexed line fidelity and rule identifiers.
    """

    PARSER_VERSION = "doclore-style-guide-v1"

    @property
    def source_type(self) -> SourceType:
        return SourceType.STYLE_GUIDE

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

        # Check for JSON or structured rule format
        if (stripped.startswith("[") and stripped.endswith("]")) or (
            stripped.startswith("{") and stripped.endswith("}")
        ):
            try:
                parsed_json = json.loads(text)
                return self._parse_structured_rules(
                    source=source,
                    data=parsed_json,
                    text=text,
                    canonical_path=canonical_path,
                    revision=revision,
                )
            except Exception:
                pass

        # Parse as Markdown Style Guide
        return self._parse_markdown_rules(
            source=source,
            text=text,
            canonical_path=canonical_path,
            revision=revision,
        )

    def _parse_markdown_rules(
        self,
        source: Source,
        text: str,
        canonical_path: str,
        revision: str,
    ) -> list[Document]:
        lines = text.splitlines()
        doc_id = self._generate_id(source.id, canonical_path)
        chunks: list[Chunk] = []

        title = canonical_path.split("/")[-1].replace(".md", "")
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Scan for rule sections: ## Rule [SEC-01] or ## [API-02] or ## Section Name
        section_starts: list[tuple[int, str, int, Optional[str]]] = []  # (line_no, heading, level, rule_id)
        for idx, line in enumerate(lines, start=1):
            match = re.match(r"^(#{1,4})\s+(.+)$", line)
            if match:
                level = len(match.group(1))
                heading = match.group(2).strip()
                # Check for bracketed rule identifier like [SEC-01] or [API-002]
                rule_match = re.search(r"\[([A-Z0-9_-]{3,15})\]", heading)
                rule_id = rule_match.group(1) if rule_match else None
                section_starts.append((idx, heading, level, rule_id))

        if not section_starts:
            chunks.append(
                Chunk(
                    id=f"chk-style-{doc_id[:8]}-1",
                    document_id=doc_id,
                    text=text.strip(),
                    provenance=Provenance(
                        project_id=source.project_id,
                        source_id=source.id,
                        document_id=doc_id,
                        chunk_id=f"chk-style-{doc_id[:8]}-1",
                        source_type=SourceType.STYLE_GUIDE,
                        canonical_path=canonical_path,
                        source_revision=revision,
                        start_line=1,
                        end_line=len(lines),
                        section_path="style_guide/general",
                        parser_version=self.PARSER_VERSION,
                    ),
                )
            )
        else:
            for i, (start_line, heading, level, rule_id) in enumerate(section_starts):
                end_line = (
                    section_starts[i + 1][0] - 1
                    if i + 1 < len(section_starts)
                    else len(lines)
                )
                chunk_lines = lines[start_line - 1 : end_line]
                chunk_text = "\n".join(chunk_lines).strip()

                if not chunk_text:
                    continue

                rule_tag = rule_id or self._slugify(heading)
                chunk_id = f"chk-rule-{doc_id[:8]}-{start_line}-{rule_tag.lower()}"
                section_path = f"style_guide > {heading}"

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
                            source_type=SourceType.STYLE_GUIDE,
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

    def _parse_structured_rules(
        self,
        source: Source,
        data: Any,
        text: str,
        canonical_path: str,
        revision: str,
    ) -> list[Document]:
        lines = text.splitlines()
        doc_id = self._generate_id(source.id, canonical_path)
        items = data if isinstance(data, list) else data.get("rules", [data])
        chunks: list[Chunk] = []

        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue

            rule_id = str(item.get("id") or item.get("rule_id") or f"RULE-{idx}")
            name = item.get("name", f"Guideline {rule_id}")
            category = item.get("category", "general")
            requirement = item.get("requirement", "")
            rationale = item.get("rationale", "")
            remediation = item.get("remediation", "")

            start_line, end_line = self._find_rule_lines(lines, rule_id, name)

            rule_text = (
                f"# Engineering Style Rule: [{rule_id}] {name}\n"
                f"Category: {category}\n\n"
                f"## Requirement\n{requirement}\n\n"
            )
            if rationale:
                rule_text += f"## Rationale\n{rationale}\n\n"
            if remediation:
                rule_text += f"## Remediation\n{remediation}\n"

            chunks.append(
                Chunk(
                    id=f"chk-rule-{rule_id}",
                    document_id=doc_id,
                    text=rule_text.strip(),
                    provenance=Provenance(
                        project_id=source.project_id,
                        source_id=source.id,
                        document_id=doc_id,
                        chunk_id=f"chk-rule-{rule_id}",
                        source_type=SourceType.STYLE_GUIDE,
                        canonical_path=canonical_path,
                        source_revision=revision,
                        start_line=start_line,
                        end_line=end_line,
                        section_path=f"style_guide/{category} > [{rule_id}] {name}",
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

    def _find_rule_lines(self, lines: list[str], identifier: str, fallback_term: str) -> tuple[int, int]:
        start = 1
        for idx, line in enumerate(lines, start=1):
            if identifier in line or fallback_term in line:
                start = idx
                break
        end = min(start + 20, len(lines))
        return start, max(start, end)

    def _slugify(self, text: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:24]

    def _generate_id(self, source_id: str, path: str) -> str:
        digest = hashlib.sha256(f"{source_id}:{path}".encode("utf-8")).hexdigest()[:16]
        return f"doc-style-{digest}"
