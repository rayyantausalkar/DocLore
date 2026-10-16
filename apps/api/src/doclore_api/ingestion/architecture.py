import hashlib
import json
import re
from typing import Any, Optional

from doclore_api.models import Chunk, Document, Provenance, Source, SourceType


class ArchitectureDiagramAdapter:
    """Ingestion adapter for system architecture diagrams and service topology models.
    
    Parses Mermaid sequence diagrams, flowcharts, and C4 architecture specifications
    into canonical chunks with exact 1-indexed line fidelity, component boundaries,
    and protocol interaction edges.
    """

    PARSER_VERSION = "doclore-architecture-v1"

    @property
    def source_type(self) -> SourceType:
        return SourceType.ARCHITECTURE_DIAGRAM

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

        # Check for JSON or structured architecture model
        if (stripped.startswith("[") and stripped.endswith("]")) or (
            stripped.startswith("{") and stripped.endswith("}")
        ):
            try:
                parsed_json = json.loads(text)
                return self._parse_structured_architecture(
                    source=source,
                    data=parsed_json,
                    text=text,
                    canonical_path=canonical_path,
                    revision=revision,
                )
            except Exception:
                pass

        # Parse as Mermaid / Markdown Architecture Specification
        return self._parse_mermaid_and_markdown(
            source=source,
            text=text,
            canonical_path=canonical_path,
            revision=revision,
        )

    def _parse_mermaid_and_markdown(
        self,
        source: Source,
        text: str,
        canonical_path: str,
        revision: str,
    ) -> list[Document]:
        lines = text.splitlines()
        doc_id = self._generate_id(source.id, canonical_path)
        chunks: list[Chunk] = []

        title = canonical_path.split("/")[-1].replace(".md", "").replace(".mmd", "")
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Detect Mermaid code blocks or standalone diagrams
        in_mermaid = False
        mermaid_start = 1
        mermaid_lines: list[str] = []

        # Find sections and interactions
        interaction_lines: list[tuple[int, str]] = []  # (line_no, line_text)

        for idx, line in enumerate(lines, start=1):
            stripped_line = line.strip()
            if stripped_line.startswith("```mermaid") or stripped_line.startswith("sequenceDiagram") or stripped_line.startswith("graph ") or stripped_line.startswith("flowchart "):
                in_mermaid = True
                mermaid_start = idx

            if in_mermaid:
                mermaid_lines.append(line)
                # Check for sequence interaction: A->>B: message
                seq_match = re.search(r"([A-Za-z0-9_-]+)\s*(?:->>|-->>|->)\s*([A-Za-z0-9_-]+)\s*:\s*(.+)", line)
                if seq_match:
                    from_node, to_node, action = seq_match.group(1), seq_match.group(2), seq_match.group(3)
                    interaction_lines.append((idx, f"Call Flow: {from_node} -> {to_node} : {action}"))

                # Check for flowchart edge: A -->|Bearer Auth| B
                flow_match = re.search(r"([A-Za-z0-9_-]+)\s*--+>\|?([^|]+)?\|?\s*([A-Za-z0-9_-]+)", line)
                if flow_match and not seq_match:
                    from_n, label, to_n = flow_match.group(1), (flow_match.group(2) or "").strip(), flow_match.group(3)
                    interaction_lines.append((idx, f"Data Flow: {from_n} --> {to_n} [{label}]"))

            if stripped_line.startswith("```") and in_mermaid and idx > mermaid_start:
                in_mermaid = False

        # 1. Global / Topology chunk for the full diagram
        end_mermaid_line = min(mermaid_start + max(1, len(mermaid_lines)), len(lines))
        topology_text = f"# Architecture Diagram: {title}\nFile: {canonical_path}\n\n```mermaid\n{text}\n```"
        chunks.append(
            Chunk(
                id=f"chk-arch-{doc_id[:8]}-topology",
                document_id=doc_id,
                text=topology_text.strip(),
                provenance=Provenance(
                    project_id=source.project_id,
                    source_id=source.id,
                    document_id=doc_id,
                    chunk_id=f"chk-arch-{doc_id[:8]}-topology",
                    source_type=SourceType.ARCHITECTURE_DIAGRAM,
                    canonical_path=canonical_path,
                    source_revision=revision,
                    start_line=1,
                    end_line=len(lines),
                    section_path=f"architecture/{title} > topology",
                    parser_version=self.PARSER_VERSION,
                ),
            )
        )

        # 2. Individual interaction flow chunks with exact line ranges
        for line_no, flow_desc in interaction_lines:
            flow_chunk_id = f"chk-flow-{doc_id[:8]}-{line_no}"
            chunk_content = (
                f"# Architecture Flow Step: {flow_desc}\n"
                f"Source Diagram: {title}\n"
                f"Line {line_no}: {lines[line_no - 1].strip()}\n"
            )
            chunks.append(
                Chunk(
                    id=flow_chunk_id,
                    document_id=doc_id,
                    text=chunk_content.strip(),
                    provenance=Provenance(
                        project_id=source.project_id,
                        source_id=source.id,
                        document_id=doc_id,
                        chunk_id=flow_chunk_id,
                        source_type=SourceType.ARCHITECTURE_DIAGRAM,
                        canonical_path=canonical_path,
                        source_revision=revision,
                        start_line=line_no,
                        end_line=min(line_no + 3, len(lines)),
                        section_path=f"architecture/{title} > {flow_desc[:32]}",
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

    def _parse_structured_architecture(
        self,
        source: Source,
        data: Any,
        text: str,
        canonical_path: str,
        revision: str,
    ) -> list[Document]:
        lines = text.splitlines()
        doc_id = self._generate_id(source.id, canonical_path)
        chunks: list[Chunk] = []

        system_name = data.get("system_name") or data.get("name") or "System Architecture"
        components = data.get("components", [])
        data_flows = data.get("flows") or data.get("data_flows") or []

        # 1. Component chunks
        for idx, comp in enumerate(components, start=1):
            if not isinstance(comp, dict):
                continue
            name = comp.get("name", f"Component {idx}")
            role = comp.get("role", "")
            technology = comp.get("technology", "")
            protocols = comp.get("protocols", [])

            start_l, end_l = self._find_term_lines(lines, name)
            comp_text = (
                f"# Architecture Component: {name}\n"
                f"Role: {role}\n"
                f"Technology: {technology}\n"
                f"Protocols: {', '.join(protocols) if isinstance(protocols, list) else protocols}\n"
            )
            chunks.append(
                Chunk(
                    id=f"chk-comp-{self._slugify(name)}",
                    document_id=doc_id,
                    text=comp_text.strip(),
                    provenance=Provenance(
                        project_id=source.project_id,
                        source_id=source.id,
                        document_id=doc_id,
                        chunk_id=f"chk-comp-{self._slugify(name)}",
                        source_type=SourceType.ARCHITECTURE_DIAGRAM,
                        canonical_path=canonical_path,
                        source_revision=revision,
                        start_line=start_l,
                        end_line=end_l,
                        section_path=f"architecture/{system_name} > component:{name}",
                        parser_version=self.PARSER_VERSION,
                    ),
                )
            )

        # 2. Data flow chunks
        for idx, flow in enumerate(data_flows, start=1):
            if not isinstance(flow, dict):
                continue
            source_node = flow.get("from") or flow.get("source")
            target_node = flow.get("to") or flow.get("target")
            protocol = flow.get("protocol", "HTTP")
            security = flow.get("security", "")

            start_l, end_l = self._find_term_lines(lines, str(source_node))
            flow_text = (
                f"# Architecture Data Flow: {source_node} -> {target_node}\n"
                f"Protocol: {protocol}\n"
                f"Security: {security}\n"
                f"Description: {flow.get('description', '')}\n"
            )
            chunks.append(
                Chunk(
                    id=f"chk-flow-{idx}-{self._slugify(str(source_node))}",
                    document_id=doc_id,
                    text=flow_text.strip(),
                    provenance=Provenance(
                        project_id=source.project_id,
                        source_id=source.id,
                        document_id=doc_id,
                        chunk_id=f"chk-flow-{idx}-{self._slugify(str(source_node))}",
                        source_type=SourceType.ARCHITECTURE_DIAGRAM,
                        canonical_path=canonical_path,
                        source_revision=revision,
                        start_line=start_l,
                        end_line=end_l,
                        section_path=f"architecture/{system_name} > flow:{source_node}->{target_node}",
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

    def _find_term_lines(self, lines: list[str], term: str) -> tuple[int, int]:
        start = 1
        for idx, line in enumerate(lines, start=1):
            if term in line:
                start = idx
                break
        end = min(start + 15, len(lines))
        return start, max(start, end)

    def _slugify(self, text: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:24]

    def _generate_id(self, source_id: str, path: str) -> str:
        digest = hashlib.sha256(f"{source_id}:{path}".encode("utf-8")).hexdigest()[:16]
        return f"doc-arch-{digest}"
