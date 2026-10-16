import ast
import re
from typing import Any, Optional


def find_matching_brace_end(lines: list[str], start_line_idx: int) -> int:
    """Finds the 1-indexed end line by counting opening and closing braces."""
    balance = 0
    found_first_brace = False
    total_lines = len(lines)

    for idx in range(start_line_idx, min(start_line_idx + 250, total_lines)):
        line = lines[idx]
        # Strip string literals and line comments to avoid false brace counts
        clean_line = re.sub(r"//.*$|#.*$|/\*.*?\*/", "", line)
        clean_line = re.sub(r"(['\"]).*?\1", "", clean_line)

        for ch in clean_line:
            if ch == "{":
                balance += 1
                found_first_brace = True
            elif ch == "}":
                balance -= 1
                if found_first_brace and balance <= 0:
                    return idx + 1  # 1-indexed

    if found_first_brace and balance <= 0:
        return start_line_idx + 1

    # Fallback to reasonable block span if closing brace wasn't resolved cleanly
    return min(start_line_idx + 35, total_lines)


class PythonASTVisitor(ast.NodeVisitor):
    """Walks Python AST to discover routes, auth checks, functions, and classes with exact line ranges."""

    def __init__(self, source_lines: list[str], rel_path: str) -> None:
        self.source_lines = source_lines
        self.rel_path = rel_path
        self.extracted_items: list[dict[str, Any]] = []

    def _get_node_text(self, node: ast.AST) -> str:
        start_line = getattr(node, "lineno", 1) - 1
        end_line = getattr(node, "end_lineno", len(self.source_lines))
        return "\n".join(self.source_lines[start_line:end_line])

    def _get_decorators(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    val_id = dec.func.value.id if isinstance(dec.func.value, ast.Name) else "router"
                    decorators.append(f"{val_id}.{dec.func.attr}")
            elif isinstance(dec, ast.Attribute):
                val_id = dec.value.id if isinstance(dec.value, ast.Name) else "router"
                decorators.append(f"{val_id}.{dec.attr}")
        return decorators

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node, is_async=True)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node, is_async=False)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._process_class(node)
        self.generic_visit(node)

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        decorators = self._get_decorators(node)
        docstring = ast.get_docstring(node) or ""
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        code_text = self._get_node_text(node)

        route_meta: Optional[dict[str, str]] = None
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                attr_name = dec.func.attr.lower()
                if attr_name in {"get", "post", "put", "delete", "patch", "options", "head", "route"}:
                    http_method = attr_name.upper() if attr_name != "route" else "ANY"
                    path = ""
                    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                        path = dec.args[0].value
                    route_meta = {"method": http_method, "path": path}
                    break

        auth_dependencies = []
        for default in node.args.defaults + node.args.kw_defaults:
            if isinstance(default, ast.Call):
                func_name = ""
                if isinstance(default.func, ast.Name):
                    func_name = default.func.id
                if func_name in {"Depends", "Security"} and default.args:
                    arg0 = default.args[0]
                    if isinstance(arg0, ast.Name):
                        auth_dependencies.append(f"{func_name}({arg0.id})")

        item_type = "route" if route_meta else "function"
        if route_meta:
            section_path = f"{self.rel_path} > route:{route_meta['method']} {route_meta['path']}"
            summary = (
                f"# HTTP Endpoint: {route_meta['method']} {route_meta['path']}\n"
                f"Handler: {'async def' if is_async else 'def'} {node.name}\n"
            )
            if auth_dependencies:
                summary += f"Auth Dependencies: {', '.join(auth_dependencies)}\n"
            if docstring:
                summary += f"Docstring: {docstring}\n"
            full_text = f"{summary}\n```python\n{code_text}\n```"
        else:
            section_path = f"{self.rel_path} > func:{node.name}"
            summary = f"# Function: {'async def' if is_async else 'def'} {node.name}\n"
            if decorators:
                summary += f"Decorators: {', '.join(decorators)}\n"
            if docstring:
                summary += f"Docstring: {docstring}\n"
            full_text = f"{summary}\n```python\n{code_text}\n```"

        self.extracted_items.append({
            "type": item_type,
            "name": node.name,
            "section_path": section_path,
            "start_line": start_line,
            "end_line": end_line,
            "text": full_text,
        })

    def _process_class(self, node: ast.ClassDef) -> None:
        docstring = ast.get_docstring(node) or ""
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        code_text = self._get_node_text(node)
        base_classes = [b.id for b in node.bases if isinstance(b, ast.Name)]

        section_path = f"{self.rel_path} > class:{node.name}"
        summary = f"# Class: {node.name}"
        if base_classes:
            summary += f"({', '.join(base_classes)})"
        summary += "\n"
        if docstring:
            summary += f"Docstring: {docstring}\n"

        full_text = f"{summary}\n```python\n{code_text}\n```"
        self.extracted_items.append({
            "type": "class",
            "name": node.name,
            "section_path": section_path,
            "start_line": start_line,
            "end_line": end_line,
            "text": full_text,
        })


class JavaScriptTypeScriptScanner:
    """Scans JavaScript and TypeScript source files for functions, classes, interfaces, and routes."""

    JS_ROUTE_PATTERN = re.compile(
        r"""(?:router|app|api|route)\.(get|post|put|delete|patch|all)\s*\(\s*["']([^"']+)["']""",
        re.IGNORECASE,
    )
    NEXT_ROUTE_PATTERN = re.compile(
        r"""export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)\s*\(""",
    )
    CLASS_PATTERN = re.compile(
        r"""^(?:export\s+)?(?:default\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?(?:\s+implements\s+[^{]+)?\s*\{?""",
    )
    INTERFACE_PATTERN = re.compile(
        r"""^(?:export\s+)?(?:interface|type)\s+(\w+)""",
    )
    FUNC_PATTERN = re.compile(
        r"""^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(""",
    )
    ARROW_FUNC_PATTERN = re.compile(
        r"""^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_]+)\s*=>""",
    )

    def scan(self, lines: list[str], rel_path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        total_lines = len(lines)

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "/*", "*")):
                continue

            # 1. Next.js / HTTP routes
            next_match = self.NEXT_ROUTE_PATTERN.search(stripped)
            if next_match:
                method = next_match.group(1).upper()
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "route",
                    "name": method,
                    "section_path": f"{rel_path} > route:{method} (Next.js)",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Route Handler: {method}\n```typescript\n{code_text}\n```",
                })
                continue

            route_match = self.JS_ROUTE_PATTERN.search(stripped)
            if route_match:
                method = route_match.group(1).upper()
                path = route_match.group(2)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "route",
                    "name": f"{method} {path}",
                    "section_path": f"{rel_path} > route:{method} {path}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# HTTP Endpoint: {method} {path}\n```typescript\n{code_text}\n```",
                })
                continue

            # 2. Classes
            class_match = self.CLASS_PATTERN.match(stripped)
            if class_match:
                class_name = class_match.group(1)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "class",
                    "name": class_name,
                    "section_path": f"{rel_path} > class:{class_name}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Class: {class_name}\n```typescript\n{code_text}\n```",
                })
                continue

            # 3. Interfaces / Types
            if stripped.startswith(("interface ", "export interface ", "type ", "export type ")):
                iface_match = self.INTERFACE_PATTERN.match(stripped)
                if iface_match:
                    name = iface_match.group(1)
                    end_line = find_matching_brace_end(lines, idx)
                    code_text = "\n".join(lines[idx:end_line])
                    items.append({
                        "type": "interface",
                        "name": name,
                        "section_path": f"{rel_path} > interface:{name}",
                        "start_line": idx + 1,
                        "end_line": end_line,
                        "text": f"# Interface / Type: {name}\n```typescript\n{code_text}\n```",
                    })
                    continue

            # 4. Functions
            func_match = self.FUNC_PATTERN.match(stripped)
            if func_match:
                func_name = func_match.group(1)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "function",
                    "name": func_name,
                    "section_path": f"{rel_path} > func:{func_name}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Function: {func_name}\n```typescript\n{code_text}\n```",
                })
                continue

            # 5. Arrow functions / Variable functions
            arrow_match = self.ARROW_FUNC_PATTERN.match(stripped)
            if arrow_match:
                func_name = arrow_match.group(1)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "function",
                    "name": func_name,
                    "section_path": f"{rel_path} > func:{func_name}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Function: {func_name}\n```typescript\n{code_text}\n```",
                })
                continue

        return items


class GoScanner:
    """Scans Go source files for functions, methods, structs, interfaces, and routes."""

    FUNC_PATTERN = re.compile(
        r"""^func\s+(?:\((?:[^)]+)\)\s+)?(\w+)\s*\(""",
    )
    TYPE_PATTERN = re.compile(
        r"""^type\s+(\w+)\s+(struct|interface)""",
    )
    ROUTE_PATTERN = re.compile(
        r"""(?:r|router|app|mux|api)\.(GET|POST|PUT|DELETE|PATCH|Handle|HandleFunc)\s*\(\s*["']([^"']+)["']""",
        re.IGNORECASE,
    )

    def scan(self, lines: list[str], rel_path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            # Routes
            route_match = self.ROUTE_PATTERN.search(stripped)
            if route_match:
                method = route_match.group(1).upper()
                path = route_match.group(2)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "route",
                    "name": f"{method} {path}",
                    "section_path": f"{rel_path} > route:{method} {path}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Go HTTP Route: {method} {path}\n```go\n{code_text}\n```",
                })
                continue

            # Types / Structs
            type_match = self.TYPE_PATTERN.match(stripped)
            if type_match:
                name, kind = type_match.group(1), type_match.group(2)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": kind,
                    "name": name,
                    "section_path": f"{rel_path} > {kind}:{name}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Go {kind.capitalize()}: {name}\n```go\n{code_text}\n```",
                })
                continue

            # Functions / Methods
            func_match = self.FUNC_PATTERN.match(stripped)
            if func_match:
                name = func_match.group(1)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "function",
                    "name": name,
                    "section_path": f"{rel_path} > func:{name}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Go Function: {name}\n```go\n{code_text}\n```",
                })
                continue

        return items


class RustScanner:
    """Scans Rust source files for functions, structs, enums, and impl blocks."""

    FN_PATTERN = re.compile(
        r"""^(?:pub(?:\([^)]+\))?\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]+>)?\s*\(""",
    )
    TYPE_PATTERN = re.compile(
        r"""^(?:pub(?:\([^)]+\))?\s+)?(struct|enum|trait)\s+(\w+)""",
    )
    IMPL_PATTERN = re.compile(
        r"""^impl(?:<[^>]+>)?\s+(?:(?:\w+)\s+for\s+)?(\w+)""",
    )

    def scan(self, lines: list[str], rel_path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            # Impl
            impl_match = self.IMPL_PATTERN.match(stripped)
            if impl_match:
                name = impl_match.group(1)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "impl",
                    "name": name,
                    "section_path": f"{rel_path} > impl:{name}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Rust Impl: {name}\n```rust\n{code_text}\n```",
                })
                continue

            # Struct / Enum / Trait
            type_match = self.TYPE_PATTERN.match(stripped)
            if type_match:
                kind, name = type_match.group(1), type_match.group(2)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": kind,
                    "name": name,
                    "section_path": f"{rel_path} > {kind}:{name}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Rust {kind.capitalize()}: {name}\n```rust\n{code_text}\n```",
                })
                continue

            # Functions
            fn_match = self.FN_PATTERN.match(stripped)
            if fn_match:
                name = fn_match.group(1)
                end_line = find_matching_brace_end(lines, idx)
                code_text = "\n".join(lines[idx:end_line])
                items.append({
                    "type": "function",
                    "name": name,
                    "section_path": f"{rel_path} > func:{name}",
                    "start_line": idx + 1,
                    "end_line": end_line,
                    "text": f"# Rust Function: {name}\n```rust\n{code_text}\n```",
                })
                continue

        return items


class MarkdownSectionScanner:
    """Chunks documentation files (.md, .markdown, .rst) by headings with line preservation."""

    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")

    def scan(self, lines: list[str], rel_path: str) -> list[dict[str, Any]]:
        headings: list[tuple[int, int, str]] = []  # (line_idx_0, level, title)
        for idx, line in enumerate(lines):
            match = self.HEADING_PATTERN.match(line)
            if match:
                headings.append((idx, len(match.group(1)), match.group(2).strip()))

        if not headings:
            return []

        items: list[dict[str, Any]] = []
        total_lines = len(lines)

        for i, (start_idx, level, title) in enumerate(headings):
            end_idx = headings[i + 1][0] if i + 1 < len(headings) else total_lines
            content = "\n".join(lines[start_idx:end_idx]).strip()
            if not content:
                continue

            items.append({
                "type": "heading",
                "name": title,
                "section_path": f"{rel_path} > {'#' * level} {title}",
                "start_line": start_idx + 1,
                "end_line": end_idx,
                "text": content,
            })

        return items


def universal_line_window_chunk(
    lines: list[str],
    rel_path: str,
    lang: str = "text",
    window_size: int = 60,
    overlap: int = 10,
) -> list[dict[str, Any]]:
    """Chunks arbitrary text or code into overlapping line windows with exact start and end lines."""
    total_lines = len(lines)
    if total_lines == 0:
        return []

    if total_lines <= window_size:
        return [
            {
                "type": "file",
                "name": rel_path.split("/")[-1],
                "section_path": f"{rel_path} > lines 1-{total_lines}",
                "start_line": 1,
                "end_line": total_lines,
                "text": f"# File: {rel_path}\n\n```{lang}\n" + "\n".join(lines) + "\n```",
            }
        ]

    chunks: list[dict[str, Any]] = []
    step = max(1, window_size - overlap)
    chunk_idx = 1

    for start_idx in range(0, total_lines, step):
        end_idx = min(start_idx + window_size, total_lines)
        if start_idx >= end_idx:
            break

        snippet = "\n".join(lines[start_idx:end_idx])
        start_line = start_idx + 1
        end_line = end_idx

        chunks.append({
            "type": "window",
            "name": f"{rel_path}:{start_line}-{end_line}",
            "section_path": f"{rel_path} > lines {start_line}-{end_line}",
            "start_line": start_line,
            "end_line": end_line,
            "text": f"# File: {rel_path} (Lines {start_line}-{end_line})\n\n```{lang}\n{snippet}\n```",
        })
        chunk_idx += 1

        if end_idx >= total_lines:
            break

    return chunks
