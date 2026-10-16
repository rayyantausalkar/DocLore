import hashlib
import json
import re
from typing import Any, Optional
import yaml
from yaml.loader import SafeLoader

from doclore_api.models import Chunk, Document, Provenance, Source, SourceType

# Global lookup for node line ranges without mutating dictionary keys
_NODE_LINE_MAP: dict[int, tuple[int, int]] = {}


class LineSafeLoader(SafeLoader):
    """YAML Loader that records line numbers without polluting mapping keys."""


def _construct_mapping(loader: LineSafeLoader, node: yaml.MappingNode) -> dict:
    loader.flatten_mapping(node)
    mapping = loader.construct_mapping(node)
    _NODE_LINE_MAP[id(mapping)] = (node.start_mark.line + 1, node.end_mark.line + 1)
    return mapping


LineSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


class OpenAPIAdapter:
    """Ingests OpenAPI 3.x and Swagger 2 specifications in YAML or JSON format.
    
    Extracts operations, security schemes, and model definitions into canonical
    searchable chunks with exact structural path and line range provenance.
    """

    PARSER_VERSION = "doclore-openapi-v1"

    @property
    def source_type(self) -> SourceType:
        return SourceType.OPENAPI

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
        spec, is_yaml = self._load_spec(text)

        doc_id = self._generate_id(source.id, canonical_path)
        title = spec.get("info", {}).get("title", canonical_path.split("/")[-1])

        chunks = self._extract_chunks(
            spec=spec,
            lines=lines,
            project_id=source.project_id,
            source_id=source.id,
            document_id=doc_id,
            canonical_path=canonical_path,
            revision=revision,
            is_yaml=is_yaml,
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

    def _load_spec(self, text: str) -> tuple[dict[str, Any], bool]:
        # Try JSON first
        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                return json.loads(text), False
            except Exception:
                pass

        # Try YAML with line tracking
        try:
            loaded = yaml.load(text, Loader=LineSafeLoader)
            if isinstance(loaded, dict):
                return loaded, True
        except Exception:
            pass

        # Fallback to standard safe_load
        loaded = yaml.safe_load(text)
        if isinstance(loaded, dict):
            return loaded, True
        raise ValueError("Invalid OpenAPI specification: unable to parse as YAML or JSON.")

    def _extract_chunks(
        self,
        spec: dict[str, Any],
        lines: list[str],
        project_id: str,
        source_id: str,
        document_id: str,
        canonical_path: str,
        revision: str,
        is_yaml: bool,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []

        # 1. Global / Info chunk
        info = spec.get("info", {})
        info_text = (
            f"# API Specification: {info.get('title', 'API')}\n"
            f"Version: {info.get('version', 'unspecified')}\n"
            f"{info.get('description', '').strip()}\n"
        )
        if "servers" in spec:
            servers_text = ", ".join(s.get("url", "") for s in spec.get("servers", []) if isinstance(s, dict))
            if servers_text:
                info_text += f"Servers: {servers_text}\n"

        info_chunk_id = f"chk-info-{document_id[:8]}"
        chunks.append(
            Chunk(
                id=info_chunk_id,
                document_id=document_id,
                text=info_text.strip(),
                provenance=Provenance(
                    project_id=project_id,
                    source_id=source_id,
                    document_id=document_id,
                    chunk_id=info_chunk_id,
                    source_type=SourceType.OPENAPI,
                    canonical_path=canonical_path,
                    source_revision=revision,
                    start_line=1,
                    end_line=min(20, len(lines)),
                    section_path="info",
                    parser_version=self.PARSER_VERSION,
                ),
            )
        )

        # 2. Security Schemes
        components = spec.get("components", {})
        security_schemes = components.get("securitySchemes", {}) or spec.get("securityDefinitions", {})
        if isinstance(security_schemes, dict):
            for scheme_name, scheme_obj in security_schemes.items():
                if not isinstance(scheme_obj, dict):
                    continue
                start_l, end_l = self._resolve_line_range(scheme_obj, lines, scheme_name)
                scheme_text = (
                    f"## Security Scheme: {scheme_name}\n"
                    f"Type: {scheme_obj.get('type')}\n"
                    f"Scheme: {scheme_obj.get('scheme', 'none')}\n"
                    f"BearerFormat: {scheme_obj.get('bearerFormat', 'none')}\n"
                    f"In: {scheme_obj.get('in', 'header')}\n"
                    f"Name: {scheme_obj.get('name', 'Authorization')}\n"
                    f"Description: {scheme_obj.get('description', '')}\n"
                )
                if "flows" in scheme_obj:
                    flows = scheme_obj.get("flows", {})
                    scheme_text += f"OAuth Flows: {json.dumps(flows)}\n"

                chunk_id = f"chk-sec-{scheme_name}"
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        text=scheme_text.strip(),
                        provenance=Provenance(
                            project_id=project_id,
                            source_id=source_id,
                            document_id=document_id,
                            chunk_id=chunk_id,
                            source_type=SourceType.OPENAPI,
                            canonical_path=canonical_path,
                            source_revision=revision,
                            start_line=start_l,
                            end_line=end_l,
                            section_path=f"components.securitySchemes.{scheme_name}",
                            parser_version=self.PARSER_VERSION,
                        ),
                    )
                )

        # 3. Path Operations
        paths = spec.get("paths", {})
        http_methods = {"get", "post", "put", "delete", "patch", "options", "head"}

        if isinstance(paths, dict):
            for path_pattern, path_item in paths.items():
                if not isinstance(path_item, dict):
                    continue

                for method in http_methods:
                    if method not in path_item or not isinstance(path_item[method], dict):
                        continue

                    operation = path_item[method]
                    start_l, end_l = self._resolve_line_range(operation, lines, path_pattern, method)

                    op_id = operation.get("operationId", f"{method}_{path_pattern}")
                    summary = operation.get("summary", "")
                    description = operation.get("description", "")
                    security = operation.get("security", spec.get("security", []))

                    op_lines = [
                        f"# Operation: {method.upper()} {path_pattern}",
                        f"Operation ID: {op_id}",
                    ]
                    if summary:
                        op_lines.append(f"Summary: {summary}")
                    if description:
                        op_lines.append(f"Description: {description}")
                    if security:
                        op_lines.append(f"Security Requirements: {json.dumps(security)}")

                    # Parameters
                    params = operation.get("parameters", [])
                    if params and isinstance(params, list):
                        op_lines.append("Parameters:")
                        for p in params:
                            if isinstance(p, dict):
                                req_str = "required" if p.get("required") else "optional"
                                p_in = p.get("in", "query")
                                p_name = p.get("name", "unknown")
                                p_desc = p.get("description", "")
                                op_lines.append(f"- {p_name} ({p_in}, {req_str}): {p_desc}")

                    # Request Body
                    req_body = operation.get("requestBody", {})
                    if isinstance(req_body, dict) and req_body:
                        op_lines.append("Request Body:")
                        content = req_body.get("content", {})
                        if isinstance(content, dict):
                            for mime_type, mime_spec in content.items():
                                if isinstance(mime_spec, dict):
                                    op_lines.append(f"- Content-Type: {mime_type}")
                                    schema = mime_spec.get("schema", {})
                                    if isinstance(schema, dict) and "$ref" in schema:
                                        op_lines.append(f"  Schema Reference: {schema['$ref']}")

                    # Responses
                    responses = operation.get("responses", {})
                    if isinstance(responses, dict) and responses:
                        op_lines.append("Responses:")
                        for status_code, resp_obj in responses.items():
                            if isinstance(resp_obj, dict):
                                resp_desc = resp_obj.get("description", "")
                                op_lines.append(f"- Status {status_code}: {resp_desc}")

                    op_text = "\n".join(op_lines)
                    chunk_id = f"chk-op-{method}-{self._slugify(path_pattern)}"

                    chunks.append(
                        Chunk(
                            id=chunk_id,
                            document_id=document_id,
                            text=op_text,
                            provenance=Provenance(
                                project_id=project_id,
                                source_id=source_id,
                                document_id=document_id,
                                chunk_id=chunk_id,
                                source_type=SourceType.OPENAPI,
                                canonical_path=canonical_path,
                                source_revision=revision,
                                start_line=start_l,
                                end_line=end_l,
                                section_path=f"paths.{path_pattern}.{method}",
                                parser_version=self.PARSER_VERSION,
                            ),
                        )
                    )

        # 4. Schemas / Models
        schemas = components.get("schemas", {}) or spec.get("definitions", {})
        if isinstance(schemas, dict):
            for schema_name, schema_obj in schemas.items():
                if not isinstance(schema_obj, dict):
                    continue
                start_l, end_l = self._resolve_line_range(schema_obj, lines, schema_name)
                schema_type = schema_obj.get("type", "object")
                properties = schema_obj.get("properties", {})
                required_props = schema_obj.get("required", [])

                schema_lines = [
                    f"## Model Schema: {schema_name}",
                    f"Type: {schema_type}",
                ]
                if required_props:
                    schema_lines.append(f"Required Fields: {', '.join(required_props)}")
                if properties and isinstance(properties, dict):
                    schema_lines.append("Properties:")
                    for prop_name, prop_meta in properties.items():
                        if isinstance(prop_meta, dict):
                            p_type = prop_meta.get("type", prop_meta.get("$ref", "any"))
                            p_desc = prop_meta.get("description", "")
                            schema_lines.append(f"- {prop_name} ({p_type}): {p_desc}")

                chunk_id = f"chk-schema-{schema_name}"
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        text="\n".join(schema_lines),
                        provenance=Provenance(
                            project_id=project_id,
                            source_id=source_id,
                            document_id=document_id,
                            chunk_id=chunk_id,
                            source_type=SourceType.OPENAPI,
                            canonical_path=canonical_path,
                            source_revision=revision,
                            start_line=start_l,
                            end_line=end_l,
                            section_path=f"components.schemas.{schema_name}",
                            parser_version=self.PARSER_VERSION,
                        ),
                    )
                )

        return chunks

    def _resolve_line_range(
        self,
        node: dict[str, Any],
        lines: list[str],
        primary_key: str,
        secondary_key: Optional[str] = None,
    ) -> tuple[int, int]:
        # Check node line lookup table
        node_id = id(node)
        if node_id in _NODE_LINE_MAP:
            s_line, e_line = _NODE_LINE_MAP[node_id]
            return s_line, max(s_line, e_line)

        # Fallback line scanning in text lines
        start_line = 1
        for idx, line in enumerate(lines, start=1):
            if primary_key in line:
                if secondary_key:
                    for sub_idx in range(idx, min(idx + 15, len(lines) + 1)):
                        if secondary_key.lower() in lines[sub_idx - 1].lower():
                            start_line = sub_idx
                            break
                    else:
                        start_line = idx
                else:
                    start_line = idx
                break

        end_line = min(start_line + 30, len(lines))
        return start_line, max(start_line, end_line)

    def _slugify(self, text: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:32]

    def _generate_id(self, source_id: str, path: str) -> str:
        digest = hashlib.sha256(f"{source_id}:{path}".encode("utf-8")).hexdigest()[:16]
        return f"doc-openapi-{digest}"
