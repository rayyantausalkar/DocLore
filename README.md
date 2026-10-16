# DocLore

An intelligent developer documentation agent that serves as a unified context engine and knowledge interface across software documentation and source code repositories.

---

## Problem Statement

Technical knowledge in modern software engineering is fragmented across disconnected systems—ranging from OpenAPI specifications, GitHub repositories, and architecture diagrams to troubleshooting runbooks and internal coding standards. When developers need to understand a complex system, onboard onto a codebase, verify design patterns, or trace technical behavior, they must manually search through these isolated silos and mentally stitch together unstructured documentation with structured source code. Traditional search tools rely on simple keyword matching or basic vector lookup, which fail to bridge the gap between high-level architectural specs, repo-level implementation details, and operational standards. This knowledge fragmentation creates severe developer friction, slows down feature implementation, and increases operational overhead across engineering teams.

## Solution

DocLore is an intelligent developer documentation agent that bridges these disconnected silos. Built on a multi-agent state graph using LangGraph, DocLore ingests API documentation, GitHub repositories, architecture documents, troubleshooting guides, and coding standards into a hybrid retrieval system that combines sparse BM25 keyword search with dense vector embeddings via Reciprocal Rank Fusion (RRF).

Whether a developer asks for:
- **High-level project overview** (`PROJECT_OVERVIEW`): system architecture, module boundaries, onboarding guidance.
- **Specific API details** (`API_DETAILS`): OpenAPI schemas, routes, query parameters, authentication headers.
- **Architectural design logic** (`ARCHITECTURAL_DESIGN`): topology diagrams, subsystem relationships, data flow.
- **Coding standard compliance** (`CODING_STANDARDS`): style guides, naming rules, architectural conventions.
- **Execution tracing & debugging** (`EXECUTION_TRACING`): runtime failure diagnosis, error root-cause isolation.

DocLore executes a systematic multi-step workflow: it interprets user intent, cross-references technical specs and standards, and uses AST-based code analysis to inspect actual repository source files. Synthesizing these multi-layered insights into a structured response, DocLore delivers accurate explanations, clear code/config examples, and direct citations to exact source files and documentation lines.

---

## Repository Structure

The repository is structured as a modular monolith:

- `apps/api` — Python 3.10+ backend using FastAPI, LangGraph multi-agent workflow, Multi-Language Code Scanners & Python AST, BM25 + Dense Hybrid Retrieval with Reciprocal Rank Fusion (RRF), and LM Studio local LLM integration (`google/gemma-4-e4b`).
- `apps/web` — React 19 + TypeScript frontend built with Vite, featuring an interactive citation inspector, full project/chat CRUD, knowledge silo management, and streaming reasoning feedback.
- `docs/architecture.md` — Complete product architecture, state graph specification, and engineering design.
- `assets/brand` — Approved DocLore logo (`assets/brand/doclore-logo.png`) and palette reference (`assets/brand/doclore-color-palette.png`).

---

## Implemented Knowledge Silos & Ingestion Adapters

- **Repository Ingestion** — Multi-language source code analysis supporting Python (AST), TypeScript/JavaScript (Express/Next.js routes, functions, classes), Go (Gin/Echo handlers, structs, interfaces), Rust (functions, structs, enums, impls), and sliding-window chunking for YAML, JSON, TOML, SQL, Shell, Dockerfiles, and Makefiles with exact line provenance.
- **OpenAPI Specifications** — OpenAPI 3.x parser extracting route endpoints, HTTP methods, headers, schemas, and security parameters with line citations.
- **Markdown Documentation** — Hierarchical section parser chunking Markdown guides and runbooks by header tree (`#`, `##`, `###`).
- **Issue Logs & Postmortems** — Incident logs preserving symptoms, root cause, and verified resolution steps.
- **Engineering Style Guides** — Standards parser extracting linting rules, naming standards, and architectural conventions.
- **Architecture Diagrams** — Mermaid topology and sequence diagram parser indexing subsystem boundaries and data flows.

---

## Prerequisites

Before running DocLore, ensure you have the following installed on your system:

1. **Python 3.10 or newer** — [python.org](https://www.python.org/)
2. **uv** (Extremely fast Python package and project manager) — [docs.astral.sh/uv](https://docs.astral.sh/uv/)
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. **Node.js 20 or newer** (with `npm`) — [nodejs.org](https://nodejs.org/)
4. **Git** — [git-scm.com](https://git-scm.com/)
5. **LM Studio** (for local LLM inference and embeddings) — [lmstudio.ai](https://lmstudio.ai/)

---

## LM Studio Installation & Setup Guide

DocLore uses **LM Studio** to run local models privately without external API costs or data leakage. It connects via LM Studio's OpenAI-compatible HTTP endpoints.

### 1. Download & Install LM Studio
- Download LM Studio for your OS from [lmstudio.ai](https://lmstudio.ai/).
- Run the installer and launch LM Studio.

### 2. Download the Required Models
Open the **Discover / Search** tab (magnifying glass icon on the left) inside LM Studio:

1. **Primary LLM Model (Generation & Synthesis)**:
   - Search for: `google/gemma-4-e4b` (or `gemma-2-9b-it`, `gemma-2-2b-it`).
   - Select the recommended quantization (e.g. `Q4_K_M` or `Q5_K_M`).
   - Click **Download**.

2. **Embedding Model (Dense Semantic Vector Search)**:
   - Search for: `text-embedding-nomic-embed-text-v1.5` (or `bge-small-en-v1.5`).
   - Click **Download**.

### 3. Start the Local Inference Server
1. Navigate to the **Developer / Local Server** tab (the `<->` double-arrow icon on the left).
2. At the top of the window, select your downloaded LLM model (`google/gemma-4-e4b`) from the model dropdown and load it into memory.
3. In the right-hand server settings panel:
   - **Port**: Set to `1234` (default).
   - **Cross-Origin-Resource-Sharing (CORS)**: Toggle **ON**.
   - **GPU Offload**: Adjust sliders to maximize GPU layers if you have an NVIDIA/Apple Silicon GPU.
4. Click **Start Server**.
5. The status indicator should turn green and display: `Server running on http://localhost:1234`.

### 4. Verify LM Studio Server
In a terminal, verify that the local server is responding:

```powershell
curl http://127.0.0.1:1234/v1/models
```

> **Note on Offline Fallback:** If LM Studio is not running, DocLore will automatically fall back to its in-process deterministic embedding engine and evidence-only synthesis adapter, allowing you to develop and run all 58 tests completely offline.

---

## Configuration & Environment Variables

DocLore works out-of-the-box with sensible defaults. To customize endpoints, create a `.env` file in `apps/api` or set environment variables:

| Variable | Default Value | Description |
| --- | --- | --- |
| `DOCLORE_LLM_BASE_URL` | `http://127.0.0.1:1234/v1` | LM Studio OpenAI-compatible endpoint URL |
| `DOCLORE_LLM_MODEL` | `google/gemma-4-e4b` | Identifier of loaded LLM model in LM Studio |
| `DOCLORE_EMBEDDING_MODEL` | `text-embedding-nomic-embed-text-v1.5` | Identifier of embedding model for dense vector search |
| `DOCLORE_LLM_API_KEY` | `lm-studio` | API key (LM Studio accepts any string) |
| `DOCLORE_LLM_TIMEOUT` | `180` | Request timeout in seconds for deep LLM synthesis |
| `DOCLORE_DATA_DIR` | `apps/api/.doclore_data` | Directory for JSON snapshot persistence |

---

## Step-by-Step Guide to Run DocLore

### Step 1: Start LM Studio
Launch LM Studio, load `google/gemma-4-e4b`, and click **Start Server** on port `1234`.

### Step 2: Start the FastAPI Backend
Open a terminal and run:

```powershell
# Navigate to the backend directory
cd apps/api

# Sync Python virtual environment and dependencies
uv sync --dev

# Start the FastAPI development server with hot-reload
uv run uvicorn doclore_api.main:app --reload --port 8000
```

- The API server will start at: `http://127.0.0.1:8000`
- Interactive Swagger UI documentation: `http://127.0.0.1:8000/docs`
- Health check endpoint: `http://127.0.0.1:8000/api/v1/health`

### Step 3: Start the React Web Application
Open a second terminal and run:

```powershell
# Navigate to the web frontend directory
cd apps/web

# Install frontend dependencies
npm install

# Start Vite development server
npm run dev
```

- The frontend will be available at: `http://localhost:5173`
- Direct workspace view: `http://localhost:5173/app`

*(Vite automatically proxies `/api` calls to the FastAPI backend at `http://127.0.0.1:8000`).*

---

## Checks & Verification

### Run Backend Automated Tests
All 58 tests verify multi-language repository scanning, Python AST extraction, OpenAPI parsing, BM25 indexing, dense vector search, Reciprocal Rank Fusion, and LangGraph workflow nodes:

```powershell
cd apps/api
uv run pytest
```

### Run Frontend Linting & Production Build
Ensure zero TypeScript errors and adherence to code standards:

```powershell
cd apps/web

# Fast linter check
npm run lint

# Production bundle build
npm run build
```
