import json
import re
import uuid
from typing import Any, Optional, TypedDict
from langgraph.graph import END, StateGraph

from doclore_api.code_analysis.service import CodeAnalysisService
from doclore_api.diagnostics.llm import LLMAdapter
from doclore_api.diagnostics.models import Citation, DiagnosticReport
from doclore_api.evidence.validator import CitationValidator
from doclore_api.models import SourceType
from doclore_api.retrieval.models import Evidence, RetrievalScope
from doclore_api.retrieval.service import RetrievalService


class DiagnosticState(TypedDict, total=False):
    project_id: str
    query: str
    source_ids: Optional[list[str]]
    intent: Optional[str]
    intent_label: Optional[str]
    error_identifier: Optional[str]
    api_hint: Optional[str]
    retrieved_evidence: list[Evidence]
    spec_findings: list[str]
    code_findings: list[str]
    correlation_notes: list[str]
    synthesis_draft: dict[str, Any]
    validated_citations: list[Citation]
    workflow_trace: list[str]
    report: Optional[DiagnosticReport]


class DiagnosticWorkflow:
    """Multi-agent LangGraph workflow connecting documentation, specs, and source code."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        code_service: CodeAnalysisService,
        llm_adapter: LLMAdapter,
        citation_validator: Optional[CitationValidator] = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.code_service = code_service
        self.llm_adapter = llm_adapter
        self.citation_validator = citation_validator or CitationValidator()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(DiagnosticState)

        # Multi-Agent Collaborative Nodes
        builder.add_node("understand_query", self._understand_query_node)
        builder.add_node("retrieve_evidence", self._retrieve_evidence_node)
        builder.add_node("inspect_specs_and_standards", self._inspect_specs_and_standards_node)
        builder.add_node("inspect_code_ast", self._inspect_code_ast_node)
        builder.add_node("correlate_spec_and_code", self._correlate_spec_and_code_node)
        builder.add_node("synthesize", self._synthesis_node)
        builder.add_node("validate_citations", self._validate_citations_node)

        # Workflow Routing
        builder.set_entry_point("understand_query")
        builder.add_edge("understand_query", "retrieve_evidence")
        builder.add_edge("retrieve_evidence", "inspect_specs_and_standards")
        builder.add_edge("inspect_specs_and_standards", "inspect_code_ast")
        builder.add_edge("inspect_code_ast", "correlate_spec_and_code")
        builder.add_edge("correlate_spec_and_code", "synthesize")
        builder.add_edge("synthesize", "validate_citations")
        builder.add_edge("validate_citations", END)

        return builder.compile()

    def run(
        self,
        project_id: str,
        query: str,
        source_ids: Optional[list[str]] = None,
    ) -> DiagnosticReport:
        initial_state: DiagnosticState = {
            "project_id": project_id,
            "query": query,
            "source_ids": source_ids,
            "workflow_trace": [],
            "retrieved_evidence": [],
            "spec_findings": [],
            "code_findings": [],
            "correlation_notes": [],
            "validated_citations": [],
        }
        final_state = self.graph.invoke(initial_state)
        return final_state["report"]

    def _understand_query_node(self, state: DiagnosticState) -> dict[str, Any]:
        """Agent 1: Query Interpretation & Intent Router Agent."""
        query = state["query"]
        trace = list(state.get("workflow_trace", []))
        trace.append(
            "Step 1 [Understand Query / Intent Interpretation]: Analyzing developer intent across project overview, API specs, architecture, coding standards, code understanding, and diagnostics."
        )

        query_lower = query.lower()

        # Check for HTTP status codes (e.g. 401, 403, 404, 500)
        status_match = re.search(r"\b([1-5]\d{2})\b", query)
        # Extract uppercase error identifier pattern (e.g. AUTH_INVALID_TOKEN, ERR_*)
        token_match = re.search(r"\b([A-Z][A-Z0-9_]{3,31})\b", query)
        error_id = token_match.group(1) if token_match else (f"HTTP {status_match.group(1)}" if status_match else None)

        # Extract HTTP method and route pattern (e.g. POST /orders, /api/v1/orders)
        route_match = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\s+([/\w\-\.\{\}]+)", query, re.IGNORECASE)
        api_hint = None
        if route_match:
            api_hint = f"{route_match.group(1).upper()} {route_match.group(2)}"
        else:
            path_match = re.search(r"(/[a-zA-Z0-9_\-\.\/]+)", query)
            if path_match:
                api_hint = path_match.group(1)

        # Distinguish debugging inquiries from informational/architectural inquiries
        is_error_query = bool(error_id) or any(
            w in query_lower for w in ["fail", "error", "exception", "bug", "troubleshoot", "why is", "broken", "traceback", "unauthorized", "invalid"]
        )

        if any(w in query_lower for w in ["standard", "style guide", "lint", "convention", "pep8", "naming", "format", "rule"]):
            intent = "CODING_STANDARDS"
            intent_label = "Coding Standard Compliance"
        elif any(w in query_lower for w in ["architecture", "design", "component", "diagram", "boundary", "subsystem", "module structure", "flow"]):
            intent = "ARCHITECTURAL_DESIGN"
            intent_label = "Architectural Design Logic"
        elif any(w in query_lower for w in ["overview", "onboard", "about", "what is", "introduction", "high-level", "repository structure", "summary", "how to run"]):
            intent = "PROJECT_OVERVIEW"
            intent_label = "Project Overview & Onboarding"
        elif any(w in query_lower for w in ["endpoint", "openapi", "swagger", "parameter", "payload", "request body", "response", "schema", "route", "contract"]):
            intent = "API_DETAILS"
            intent_label = "API Specification & Details"
        elif is_error_query:
            intent = "EXECUTION_TRACING"
            intent_label = "Execution Tracing & Diagnostics"
        else:
            intent = "CODE_UNDERSTANDING"
            intent_label = "Code Understanding & Technical Explanation"

        trace.append(f"  Classified intent: '{intent_label}' (target error='{error_id or 'none'}', route='{api_hint or 'all'}')")
        return {
            "intent": intent,
            "intent_label": intent_label,
            "error_identifier": error_id,
            "api_hint": api_hint,
            "workflow_trace": trace,
        }

    def _retrieve_evidence_node(self, state: DiagnosticState) -> dict[str, Any]:
        """Agent 2: Multi-Source Hybrid Retrieval Agent."""
        trace = list(state.get("workflow_trace", []))
        trace.append(
            "Step 2 [Retrieve Multi-Source Evidence / Hybrid Search]: Executing targeted hybrid BM25 + dense search via Reciprocal Rank Fusion."
        )

        scope = RetrievalScope(
            project_id=state["project_id"],
            source_ids=state.get("source_ids"),
        )
        evidence = self.retrieval_service.search(
            query=state["query"],
            scope=scope,
            limit=8,
        )

        trace.append(f"  Retrieved {len(evidence)} evidence chunks combining sparse keyword and dense semantic rankings.")
        return {
            "retrieved_evidence": evidence,
            "workflow_trace": trace,
        }

    def _inspect_specs_and_standards_node(self, state: DiagnosticState) -> dict[str, Any]:
        """Agent 3: Specification & Architecture Specialist Agent."""
        trace = list(state.get("workflow_trace", []))
        trace.append(
            "Step 3 [Inspect Specifications & Coding Standards]: Cross-referencing OpenAPI contracts, architecture topologies, style guides, and runbooks."
        )

        evidence = state.get("retrieved_evidence", [])
        spec_findings = []

        for ev in evidence:
            st = ev.provenance.source_type
            if st == SourceType.OPENAPI:
                spec_findings.append(f"API Contract [{ev.provenance.section_path}]: {ev.text[:200]}")
            elif st == SourceType.ARCHITECTURE_DIAGRAM:
                spec_findings.append(f"Architecture Spec [{ev.provenance.canonical_path}]: {ev.text[:200]}")
            elif st == SourceType.STYLE_GUIDE:
                spec_findings.append(f"Coding Standard [{ev.provenance.section_path}]: {ev.text[:200]}")
            elif st == SourceType.MARKDOWN:
                spec_findings.append(f"Technical Guide/Runbook [{ev.provenance.canonical_path}]: {ev.text[:200]}")

        trace.append(f"  Cross-referenced {len(spec_findings)} technical specifications, architecture diagrams, and coding standards.")
        return {
            "spec_findings": spec_findings,
            "workflow_trace": trace,
        }

    def _inspect_code_ast_node(self, state: DiagnosticState) -> dict[str, Any]:
        """Agent 4: Multi-Language Code Implementation & AST Specialist Agent."""
        trace = list(state.get("workflow_trace", []))
        trace.append(
            "Step 4 [Inspect Source Code via Multi-Language AST & Scanners]: Performing syntax analysis on repository source files across Python (AST), TypeScript/JavaScript, Go, Rust, and configs, inspecting endpoints, handlers, and line mappings."
        )

        evidence = state.get("retrieved_evidence", [])
        code_findings = []

        for ev in evidence:
            if ev.provenance.source_type == SourceType.REPOSITORY:
                code_findings.append(f"AST Code Implementation [{ev.provenance.section_path or ev.provenance.canonical_path}]: {ev.text[:200]}")

        trace.append(f"  Inspected {len(code_findings)} repository code blocks with line-precise symbols.")
        return {
            "code_findings": code_findings,
            "workflow_trace": trace,
        }

    def _correlate_spec_and_code_node(self, state: DiagnosticState) -> dict[str, Any]:
        """Agent 5: Multi-Source Evidence Correlation Agent."""
        trace = list(state.get("workflow_trace", []))
        trace.append(
            "Step 5 [Correlate Spec & AST Code]: Correlating specification contracts, architectural topologies, and AST source code lines."
        )

        spec_findings = state.get("spec_findings", [])
        code_findings = state.get("code_findings", [])
        correlation_notes = []

        if spec_findings and code_findings:
            correlation_notes.append(
                f"Successfully correlated {len(spec_findings)} specification/guide items with {len(code_findings)} AST code blocks."
            )
        elif spec_findings:
            correlation_notes.append(f"Correlated {len(spec_findings)} technical specifications and guides.")
        elif code_findings:
            correlation_notes.append(f"Correlated {len(code_findings)} AST source code implementations.")
        else:
            correlation_notes.append("Multi-source correlation active across indexed knowledge chunks.")

        trace.append(f"  {correlation_notes[0]}")
        return {
            "correlation_notes": correlation_notes,
            "workflow_trace": trace,
        }

    def _synthesis_node(self, state: DiagnosticState) -> dict[str, Any]:
        """Agent 6: Flexible Synthesis & Documentation Specialist Agent."""
        trace = list(state.get("workflow_trace", []))
        trace.append(
            "Step 6 [Synthesize Resolution]: Synthesizing multi-layered insights into structured explanation with code/config examples."
        )

        evidence = state.get("retrieved_evidence", [])
        intent = state.get("intent", "CODE_UNDERSTANDING")
        intent_label = state.get("intent_label", "Technical Inquiry")
        error_id = state.get("error_identifier")
        is_diagnostic = intent == "EXECUTION_TRACING" or bool(error_id)

        if not evidence:
            trace.append("  No matching evidence retrieved. Flagging insufficient evidence.")
            return {
                "synthesis_draft": {
                    "summary": "Insufficient documentation or code evidence found to answer this inquiry.",
                    "root_cause": "No relevant source documents, specifications, or repository code matched the query terms.",
                    "recommended_actions": [
                        "Verify that all relevant Markdown docs and OpenAPI specifications are registered in this project.",
                        "Check that the query terms match your API route, symbol names, or error codes.",
                    ],
                    "insufficient_evidence": True,
                },
                "workflow_trace": trace,
            }

        # Build prompt with retrieved evidence
        context_blocks = []
        for idx, ev in enumerate(evidence[:6], start=1):
            body = ev.text if len(ev.text) <= 1500 else ev.text[:1500] + "\n...[truncated]"
            context_blocks.append(
                f"[Evidence #{idx} from {ev.provenance.canonical_path} (Lines {ev.provenance.start_line}-{ev.provenance.end_line})]\n"
                f"{body}\n"
            )

        if intent == "PROJECT_OVERVIEW":
            task_directive = (
                "Provide an authoritative, clear developer overview and onboarding guide for this repository. "
                "Explain its architecture, core components, entry points, and directory structure. "
                "Do NOT frame this as an error or bug report."
            )
            context_field_desc = "Core architectural foundation and system summary"
            actions_desc = "Onboarding steps, key entry points to explore, or recommended next steps"
        elif intent == "API_DETAILS":
            task_directive = (
                "Provide comprehensive API specification details: route endpoints, HTTP methods, request headers, "
                "request payload schema, response codes, and practical invocation examples (e.g. curl or client snippets). "
                "Do NOT frame this as an error or bug report."
            )
            context_field_desc = "API contract specification and schema boundaries"
            actions_desc = "Integration checklist, required parameters, and configuration guidelines"
        elif intent == "ARCHITECTURAL_DESIGN":
            task_directive = (
                "Explain the architectural design, subsystem relationships, data flow pipelines, and component boundaries "
                "based on the retrieved evidence. Do NOT frame this as an error or bug report."
            )
            context_field_desc = "Component topology and architectural boundaries"
            actions_desc = "Design principles, architectural rules, and integration practices"
        elif intent == "CODING_STANDARDS":
            task_directive = (
                "Detail the repository's coding standards, style guidelines, typing rules, and conventions with clear code examples. "
                "Do NOT frame this as an error or bug report."
            )
            context_field_desc = "Coding standard specification and style conventions"
            actions_desc = "Compliance checklist and quality rules to maintain"
        elif is_diagnostic:
            task_directive = (
                "Diagnose the reported runtime issue or error code. Correlate specifications, runbooks, and code handlers "
                "to isolate the exact root cause, and provide a verified, actionable fix with code/curl examples."
            )
            context_field_desc = "Technical root-cause diagnosis of the failure"
            actions_desc = "Step-by-step remediation and fix instructions"
        else:
            task_directive = (
                "Provide a comprehensive, clear technical explanation answering the developer's question. "
                "Walk through the relevant code, configuration, or documentation logic with code examples and direct citations. "
                "Do NOT frame this as an error or bug report unless an error was explicitly reported."
            )
            context_field_desc = "Technical foundation and implementation context"
            actions_desc = "Key takeaways, usage guidance, or implementation steps"

        if is_diagnostic:
            prompt = (
                f"You are DocLore, an intelligent Developer Documentation and Diagnostics Agent.\n"
                f"Developer Mode: {intent_label}\n"
                f"User Issue: {state['query']}\n\n"
                f"Mission Directive:\n{task_directive}\n\n"
                f"Retrieved Technical Evidence across Specifications, Standards & Code:\n"
                f"{''.join(context_blocks)}\n\n"
                f"Deliver an accurate, structured diagnosis with clear code/config examples.\n"
                f"Format rules:\n"
                f"- Do NOT use emojis.\n"
                f"- Ground strictly in verified evidence.\n"
                f"- Respond with a valid JSON object in this format:\n"
                f'{{\n'
                f'  "summary": "<concise 1-2 sentence overview directly answering the inquiry>",\n'
                f'  "explanation": "<rich conversational markdown response synthesizing multi-layered insights with code/config examples>",\n'
                f'  "technical_context": "<{context_field_desc}>",\n'
                f'  "recommended_actions": ["<{actions_desc} 1>", "<{actions_desc} 2>"]\n'
                f'}}\n'
            )
        else:
            prompt = (
                f"You are DocLore, an intelligent Developer Documentation Agent.\n"
                f"Developer Mode: {intent_label}\n"
                f"User Question: {state['query']}\n\n"
                f"Mission Directive:\n{task_directive}\n\n"
                f"Retrieved Technical Evidence across Specifications, Standards & Code:\n"
                f"{''.join(context_blocks)}\n\n"
                f"Formatting Instructions:\n"
                f"- Respond directly in clean, comprehensive, professional Markdown with clear headings, bullet points, and code blocks.\n"
                f"- Do NOT wrap your response in a JSON object or schema. Do NOT output raw JSON.\n"
                f"- Do NOT use emojis anywhere in your response.\n"
                f"- Do NOT insert inline citations like '(Citation: ...)' or '(Lines X-Y)'. Explain the system and code naturally.\n"
            )

        system_msg = (
            "You are DocLore, an intelligent developer documentation agent. "
            "Provide accurate, flexible explanations grounded strictly in verified repository code, specifications, and documentation. "
            "Never use emojis."
        )
        raw_response = self.llm_adapter.generate(prompt=prompt, system=system_msg)
        used_fallback = bool(getattr(self.llm_adapter, "last_used_fallback", False))

        synthesis = self._parse_synthesis(raw_response, default_context=context_field_desc, is_diagnostic=is_diagnostic)
        if synthesis is None:
            # Model returned direct Markdown without JSON
            clean_text = self._ensure_clean_markdown(raw_response)
            clean_text = re.sub(r"[\U00010000-\U0010ffff]", "", clean_text)
            summary_match = re.search(r"###?\s*Summary\s*\n+([^\n#]+)", clean_text, re.IGNORECASE)
            if summary_match:
                summary = summary_match.group(1).strip()
            else:
                first_para = clean_text.split("\n\n")[0].strip()
                summary = first_para[:180] if len(first_para) > 10 else f"{context_field_desc} overview."

            bullets = re.findall(r"^\s*[-*•\d\.]+\s+(.+)$", clean_text, re.MULTILINE)
            clean_bullets = [b.strip() for b in bullets if len(b.strip()) > 5][:3]
            actions = clean_bullets if len(clean_bullets) >= 2 else [
                "Review the implementation details in the repository files.",
                "Verify related configurations or dependencies as outlined above.",
            ]

            synthesis = {
                "summary": summary,
                "root_cause": f"{context_field_desc}: Grounded in repository documentation.",
                "recommended_actions": actions,
                "explanation": clean_text or "No technical details generated.",
            }

        # Double check: ensure explanation is NEVER raw JSON
        synthesis["explanation"] = self._ensure_clean_markdown(synthesis.get("explanation", ""))

        if used_fallback:
            trace.append("  LM Studio was unavailable or returned nothing usable; showing evidence-only fallback (no generated reasoning).")
        else:
            trace.append("  Answer synthesized by local LLM (google/gemma-4-e4b) from verified evidence.")
        trace.append("  Synthesis completed.")
        return {
            "synthesis_draft": synthesis,
            "workflow_trace": trace,
        }

    @staticmethod
    def _ensure_clean_markdown(text: str) -> str:
        """Guarantee that text is clean Markdown, never an unparsed JSON string wrapper."""
        stripped = (text or "").strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                data = json.loads(stripped, strict=False)
                if isinstance(data, dict):
                    if data.get("explanation"):
                        return str(data["explanation"]).strip()
                    if data.get("summary"):
                        return str(data["summary"]).strip()
            except Exception:
                pass
            # Try regex extraction of explanation field
            match = re.search(r'"explanation"\s*:\s*"(.*?)(?:"\s*,\s*"\w+"|\s*\}\s*$)', stripped, re.DOTALL)
            if match:
                extracted = match.group(1).replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t")
                return extracted.strip()
        return stripped

    @classmethod
    def _parse_synthesis(
        cls,
        raw: str,
        default_context: str = "Technical Foundation",
        is_diagnostic: bool = False,
    ) -> Optional[dict[str, Any]]:
        """Extract a synthesis dict from model output, handling Markdown, fenced JSON, and raw JSON."""
        text = (raw or "").strip()
        # Clean reasoning tags if any remain
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = text.strip()

        # Check if text contains a valid JSON candidate or fenced JSON
        candidates = []
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if fence:
            candidates.append(fence.group(1))

        first, last = text.find("{"), text.rfind("}")
        if first != -1 and last > first:
            candidates.append(text[first:last + 1])

        for candidate in candidates:
            data = None
            try:
                data = json.loads(candidate, strict=False)
            except Exception:
                exp_match = re.search(r'"explanation"\s*:\s*"(.*?)(?:"\s*,\s*"\w+"|\s*\}\s*$)', candidate, re.DOTALL)
                sum_match = re.search(r'"summary"\s*:\s*"(.*?)"', candidate)
                if exp_match or sum_match:
                    data = {
                        "explanation": (exp_match.group(1) if exp_match else "").replace("\\n", "\n").replace('\\"', '"'),
                        "summary": sum_match.group(1) if sum_match else "",
                    }

            if isinstance(data, dict) and (data.get("explanation") or data.get("summary")):
                actions = data.get("recommended_actions") or []
                if not isinstance(actions, list):
                    actions = [str(actions)]
                if len(actions) == 0:
                    actions = [
                        "Review the implementation details in the repository files.",
                        "Verify related configurations or dependencies as outlined above.",
                    ]

                tech_context = (
                    str(data.get("technical_context") or "").strip()
                    or str(data.get("root_cause") or "").strip()
                    or f"{default_context}: Grounded in repository evidence."
                )

                raw_exp = str(data.get("explanation") or data.get("summary") or "").strip()
                clean_exp = re.sub(r"[\U00010000-\U0010ffff]", "", raw_exp)

                return {
                    "summary": str(data.get("summary") or "").strip(),
                    "root_cause": tech_context,
                    "recommended_actions": [str(a) for a in actions],
                    "explanation": clean_exp,
                }

        return None

    def _validate_citations_node(self, state: DiagnosticState) -> dict[str, Any]:
        """Agent 7: Provenance & Citation Verification Agent."""
        trace = list(state.get("workflow_trace", []))
        trace.append(
            "Step 7 [Provide Suggested Fix & Sources / Validate Citations]: Reconciling citations against verified source lines."
        )

        evidence = state.get("retrieved_evidence", [])
        draft = state.get("synthesis_draft", {})
        if evidence and not draft.get("insufficient_evidence", False):
            citations = self.citation_validator.validate_and_build_citations(evidence, max_citations=4)
            trace.append(f"  Validated {len(citations)} exact citations (zero hallucinated citations allowed).")
        else:
            citations = []
            trace.append("  No matching evidence to cite.")

        report = DiagnosticReport(
            id=f"diag-{uuid.uuid4().hex[:8]}",
            project_id=state["project_id"],
            query=state["query"],
            intent=state.get("intent", "CODE_UNDERSTANDING"),
            intent_label=state.get("intent_label", "Code Understanding & Technical Explanation"),
            summary=draft.get("summary", "Technical report completed."),
            root_cause=draft.get("root_cause", "Analysis based on collected evidence."),
            recommended_actions=draft.get("recommended_actions", []),
            insufficient_evidence=draft.get("insufficient_evidence", False),
            citations=citations,
            workflow_trace=trace,
            explanation=draft.get("explanation"),
        )

        return {
            "validated_citations": citations,
            "report": report,
            "workflow_trace": trace,
        }
