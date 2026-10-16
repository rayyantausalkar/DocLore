import json
import os
import re
from typing import Optional, Protocol
import httpx


class LLMAdapter(Protocol):
    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        ...


class DeterministicDiagnosticLLMAdapter:
    """In-process deterministic LLM adapter for reliable unit testing and offline fallback."""

    use_canned_templates: bool = True

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        # Extract user query and mode line if present
        user_query = ""
        developer_mode = ""
        for line in prompt.splitlines():
            if line.startswith("User Question / Issue:"):
                user_query = line.replace("User Question / Issue:", "").strip()
            elif line.startswith("User Inquiry:"):
                user_query = line.replace("User Inquiry:", "").strip()
            elif line.startswith("Developer Mode:"):
                developer_mode = line.replace("Developer Mode:", "").strip()
            elif line.startswith("Developer Intent:"):
                developer_mode = line.replace("Developer Intent:", "").strip()

        query_lower = (user_query or prompt).lower()
        canned = self.use_canned_templates
        is_auth_error = canned and any(k in query_lower for k in ["401", "unauthorized", "auth_invalid_token", "bearer", "token", "forbidden", "403"])
        is_coding_standards = canned and any(k in query_lower for k in ["standard", "style guide", "lint", "convention", "pep8", "naming", "format"])
        is_architecture = canned and any(k in query_lower for k in ["architecture", "design", "component", "diagram", "boundary", "topology", "subsystem"])
        is_project_overview = canned and any(k in query_lower for k in ["overview", "onboard", "about", "what is", "structure", "introduction", "summary"])
        is_order_route = canned and ("order" in query_lower or "/orders" in query_lower)

        # Extract evidence snippets from prompt
        evidence_snippets = []
        current_header = ""
        current_body = []
        for line in prompt.splitlines():
            if line.startswith("[Evidence #"):
                if current_header and current_body:
                    evidence_snippets.append((current_header, "\n".join(current_body).strip()))
                current_header = line.strip()
                current_body = []
            elif current_header:
                if line.strip() and not line.startswith("Deliver an accurate") and not line.startswith("Respond with a valid"):
                    current_body.append(line)
        if current_header and current_body:
            evidence_snippets.append((current_header, "\n".join(current_body).strip()))

        if is_auth_error:
            summary = "API Authorization failure caused by missing or invalid Bearer token credentials."
            root_cause = (
                "The endpoint requires a valid JWT Bearer token in the 'Authorization' header "
                "as specified in the OpenAPI specification and verified by the auth dependency in the route handler."
            )
            actions = [
                "Attach an 'Authorization: Bearer <valid_jwt>' header to the HTTP request.",
                "Verify that the token includes the required permission scope (e.g., 'write:orders').",
                "If the token has expired, exchange your refresh token via the OAuth token endpoint.",
            ]
            explanation = (
                "### Issue Explanation\n\n"
                "The request failed with **HTTP 401 Unauthorized (`AUTH_INVALID_TOKEN`)**. "
                "The endpoint requires a valid JWT Bearer token in the `Authorization` header, "
                "which was missing or formatted incorrectly.\n\n"
                "### Evidence in Code & Specifications\n\n"
                "- **OpenAPI Specification**: Requires security scheme `BearerAuth` with scope `write:orders`.\n"
                "- **Route Handler**: `create_order` in `src/routes/orders.py` uses `verify_bearer_token`, which validates that the header begins with `Bearer `.\n\n"
                "### Suggested Fix\n\n"
                "Attach a valid Bearer token header to your request:\n\n"
                "```bash\n"
                "curl -X POST https://api.example.com/api/v1/orders \\\n"
                "  -H \"Authorization: Bearer <your_jwt_token>\" \\\n"
                "  -H \"Content-Type: application/json\" \\\n"
                "  -d '{\"items\": [{\"id\": 1, \"quantity\": 2}]}'\n"
                "```\n\n"
                "Ensure your token includes the required `write:orders` scope."
            )
        elif is_coding_standards:
            summary = "Internal coding standard and style compliance analysis."
            root_cause = "Verified repository code structure against active project coding conventions."
            actions = [
                "Adhere to type annotations on all public functions and handlers.",
                "Ensure naming conventions adhere to snake_case for functions and PascalCase for models.",
            ]
            explanation = (
                "### Coding Standard Compliance\n\n"
                "I analyzed the repository source code against the project's internal coding standards.\n\n"
                "#### Key Rules Verified:\n"
                "- **Explicit Typing**: All router endpoints and dependencies must declare return types.\n"
                "- **Naming Conventions**: Route handlers use `snake_case`, and schemas use `PascalCase`.\n"
                "- **Documentation**: Functions must include docstrings or OpenAPI summary decorators.\n\n"
                "#### Recommended Pattern:\n"
                "```python\n"
                "async def process_payload(payload: dict) -> dict:\n"
                "    \"\"\"Process validated payload adhering to coding standards.\"\"\"\n"
                "    return {\"status\": \"ok\", \"data\": payload}\n"
                "```"
            )
        elif is_architecture:
            summary = "Architectural design logic and component boundary overview."
            root_cause = "Correlated architecture documentation and diagram components with repository structure."
            actions = [
                "Maintain separation between API routing layers and domain service logic.",
                "Verify dependencies follow one-way data flow to avoid circular imports.",
            ]
            explanation = (
                "### Architectural Design Logic\n\n"
                "DocLore correlated the project's architecture documents, specifications, and repository source code.\n\n"
                "#### System Organization:\n"
                "- **API Gateway / Routing Layer**: Exposes versioned endpoints and handles authentication dependencies.\n"
                "- **Domain Services**: Encapsulates business logic, validation, and domain models.\n"
                "- **Data & Storage Adapters**: Integrates with persistent storage and search indexes behind clean repository interfaces.\n\n"
                "#### Component Flow:\n"
                "```text\n"
                "Client Request --> API Router --> Auth Dependency --> Service Logic --> Storage\n"
                "```"
            )
        elif is_project_overview:
            summary = "High-level project overview and repository onboarding guide."
            root_cause = "Indexed repository modules and technical documentation provide system context."
            actions = [
                "Explore the core route handlers and service definitions cited below.",
                "Review the OpenAPI specifications for active endpoints.",
            ]
            explanation = (
                "### Project Overview & Onboarding\n\n"
                "Welcome to the project! DocLore has indexed the codebase and documentation to give you a unified view of the system.\n\n"
                "#### Core Capabilities:\n"
                "- **Multi-Source Knowledge**: Combines OpenAPI specifications, GitHub repositories, architecture documents, and runbooks.\n"
                "- **AST Code Analysis**: Automatically parses function signatures, decorators, and line spans.\n"
                "- **Hybrid Retrieval**: Powered by sparse BM25 and dense vector search via Reciprocal Rank Fusion.\n\n"
                "Use the citation links below to explore key files directly in their original source context."
            )
        elif is_order_route:
            summary = "Order endpoint specification and implementation details."
            root_cause = "Required request parameters or schema fields are missing from the request payload."
            actions = [
                "Check the required fields in the request body schema against the OpenAPI contract.",
                "Ensure headers such as Authorization and X-Idempotency-Key are populated.",
            ]
            explanation = (
                "### Orders Endpoint Overview\n\n"
                "The **Orders Service** route is defined at `POST /api/v1/orders`.\n\n"
                "#### Key Requirements\n"
                "- **Authentication**: Secured via `BearerAuth` (JWT).\n"
                "- **Payload**: Requires valid order items according to the OpenAPI schema.\n"
                "- **Implementation**: The handler function `create_order` processes the order and returns an order confirmation object.\n\n"
                "#### Example Request\n"
                "```bash\n"
                "curl -X POST https://api.example.com/api/v1/orders \\\n"
                "  -H \"Authorization: Bearer <valid_token>\" \\\n"
                "  -H \"Content-Type: application/json\" \\\n"
                "  -d '{\"order_id\": \"ord_123\"}'\n"
                "```"
            )
        else:
            mode_label = developer_mode or "Technical Documentation"
            summary = f"Technical analysis grounded in indexed repository evidence for '{user_query or 'your inquiry'}'."
            root_cause = f"Technical Context: Grounded evidence retrieved from indexed technical specifications, runbooks, and code files."
            actions = [
                "Review the cited source lines below for specific implementation details.",
                "Inspect related module definitions or schemas in the citation inspector.",
            ]
            
            # Ground directly in the actual retrieved snippets
            evidence_sections = []
            for header, body in evidence_snippets[:3]:
                clean_body = body[:280].strip()
                evidence_sections.append(f"**From `{header.strip('[]')}`:**\n```\n{clean_body}\n```")

            explanation = (
                f"### {mode_label}: *\"{user_query or 'Inquiry'}\"*\n\n"
            )
            if not canned:
                explanation += (
                    "> Note: The local LLM is offline or operating in fallback mode; below are the most relevant "
                    "verified excerpts retrieved from your repository.\n\n"
                )
            explanation += (
                f"DocLore cross-referenced the question against the project's indexed documentation and repository files. "
                f"Here are the relevant technical findings:\n\n"
            )
            if evidence_sections:
                explanation += "\n\n".join(evidence_sections) + "\n\n"
            else:
                explanation += "Relevant documentation and code matches were located in the project's indexed sources.\n\n"

            explanation += (
                "#### Recommended Next Steps\n"
                "1. Inspect the exact cited line ranges below to view the verified context.\n"
                "2. Check if additional parameters or configurations are defined in the corresponding files."
            )

        response_dict = {
            "summary": summary,
            "root_cause": root_cause,
            "recommended_actions": actions,
            "explanation": explanation,
        }
        return json.dumps(response_dict)


class EvidenceOnlyFallbackAdapter(DeterministicDiagnosticLLMAdapter):
    """Production offline fallback: quotes retrieved evidence only, never canned project content."""

    use_canned_templates = False


class LMStudioLLMAdapter:
    """Connects to LM Studio's OpenAI-compatible /v1/chat/completions endpoint (e.g. google/gemma-4-e4b)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        fallback: Optional[LLMAdapter] = None,
    ) -> None:
        self.base_url = base_url or os.getenv("DOCLORE_LLM_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
        self.model = model or os.getenv("DOCLORE_LLM_MODEL", "google/gemma-4-e4b")
        self.api_key = api_key or os.getenv("DOCLORE_LLM_API_KEY", "lm-studio")
        self.fallback = fallback or EvidenceOnlyFallbackAdapter()

    last_used_fallback: bool = False

    @staticmethod
    def _strip_reasoning(text: str) -> str:
        # Strip <think> tags (Qwen / DeepSeek)
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        # Strip <thought> tags (Gemma / other reasoning models)
        cleaned = re.sub(r"<thought>.*?</thought>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<thought>.*$", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        return cleaned.strip()

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        timeout_s = float(os.getenv("DOCLORE_LLM_TIMEOUT", "180"))
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_s, connect=2.0)) as client:
                res = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.1,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = self._strip_reasoning(choices[0]["message"].get("content") or "")
                        if content:
                            self.last_used_fallback = False
                            return content
                elif res.status_code == 400 and system:
                    # Some model templates in LM Studio (e.g. certain Gemma presets) reject a separate system role.
                    # Retry with system instructions prepended to user prompt.
                    merged_prompt = f"System Instructions:\n{system}\n\nUser Request:\n{prompt}"
                    retry_res = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": merged_prompt}],
                            "temperature": 0.1,
                        },
                    )
                    if retry_res.status_code == 200:
                        data = retry_res.json()
                        choices = data.get("choices", [])
                        if choices:
                            content = self._strip_reasoning(choices[0]["message"].get("content") or "")
                            if content:
                                self.last_used_fallback = False
                                return content
        except Exception:
            pass

        # Fall back to deterministic adapter if LM Studio is offline or returned nothing usable
        self.last_used_fallback = True
        return self.fallback.generate(prompt, system)
