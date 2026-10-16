# DocLore Architecture and Implementation Plan

**Status:** Implemented & Verified  
**Product:** Cross-source developer documentation and debugging engine  
**Required stack:** FastAPI, React, LangGraph

## Problem Statement

Technical knowledge in modern software engineering is fragmented across disconnected systems—ranging from OpenAPI specifications, GitHub repositories, and architecture diagrams to troubleshooting runbooks and internal coding standards. When developers need to understand a complex system, onboard onto a codebase, verify design patterns, or trace technical behavior, they must manually search through these isolated silos and mentally stitch together unstructured documentation with structured source code. Traditional search tools rely on simple keyword matching or basic vector lookup, which fail to bridge the gap between high-level architectural specs, repo-level implementation details, and operational standards. This knowledge fragmentation creates severe developer friction, slows down feature implementation, and increases operational overhead across engineering teams.

## Solution

DocLore is an intelligent developer documentation agent that serves as a unified context engine and knowledge interface across software documentation and source code repositories. Built on a multi-agent state graph using LangGraph, DocLore ingests API documentation, GitHub repositories, architecture documents, troubleshooting guides, and coding standards into a hybrid retrieval system that combines sparse BM25 keyword search with dense vector embeddings via Reciprocal Rank Fusion. 

Whether a developer asks for:
1. **High-level project overview** (`PROJECT_OVERVIEW`): system architecture, module boundaries, onboarding guidance.
2. **Specific API details** (`API_DETAILS`): OpenAPI schemas, routes, query parameters, authentication headers.
3. **Architectural design logic** (`ARCHITECTURAL_DESIGN`): topology diagrams, subsystem relationships, data flow.
4. **Coding standard compliance** (`CODING_STANDARDS`): style guides, naming rules, architectural conventions.
5. **Execution tracing & debugging** (`EXECUTION_TRACING`): runtime failure diagnosis, error root-cause isolation.

DocLore runs a systematic multi-step workflow: it interprets user intent, cross-references technical specs and standards, and uses AST-based code analysis to inspect actual repository source files. Synthesizing these multi-layered insights into a structured response, DocLore delivers accurate explanations, clear code/config examples, and direct citations to exact source files and documentation lines.

## Recommended architecture

Start with a **modular monolith**: one FastAPI application, one React application, and one LangGraph workflow running inside the backend. Keep modules deep behind small interfaces, and use adapters only where a real production/test seam exists. Do not split into networked services before deployment or scaling needs justify it.

```text
React web app
    |
    | HTTP / JSON
    v
FastAPI application
    |
    +-- DiagnosticEngine
    |      +-- LangGraph diagnostic workflow
    |      +-- API-spec analysis
    |      +-- hybrid retrieval
    |      +-- repository code analysis
    |      +-- evidence and citation validation
    |
    +-- Source ingestion and synchronization
           +-- source-specific adapters
           +-- parse, normalize, chunk
           +-- persist source records and search indexes

PostgreSQL: projects, sources, sync state, canonical documents/chunks
Qdrant: dense and sparse retrieval vectors
```

The browser talks only to FastAPI. The graph, model provider, ingestion logic, and search engines remain backend implementation details.

## Backend modules and interfaces

| Module | Interface | Responsibility |
| --- | --- | --- |
| `diagnostics` | `diagnose(request) -> DiagnosticReport` | The single entry point for a user diagnosis; owns workflow execution and returns a validated result. |
| `workflow` | Internal LangGraph state transition | Runs a bounded diagnostic sequence, tracks evidence and errors, and conditionally skips irrelevant analysis. |
| `sources` | `sync(source_id) -> SyncResult` | Coordinates source refresh, idempotency, status, and indexing. |
| `ingestion` | `ingest(source, revision) -> IngestResult` | Adapts source content into canonical documents and chunks with provenance. |
| `retrieval` | `search(query, scope, limit) -> list[Evidence]` | Runs dense and BM25 retrieval, combines ranked results with RRF, and returns source-grounded evidence. |
| `code_analysis` | `inspect(repository, revision, query) -> list[Evidence]` | Searches repository files and performs language-specific syntax analysis across Python (AST), TypeScript/JavaScript, Go, Rust, and configuration files with line provenance. |
| `evidence` | `validate(report, evidence) -> ValidatedReport` | Ensures every citation refers to evidence actually retrieved and preserves source locations through synthesis. |
| `persistence` | Internal repository interfaces | Stores projects, source configuration, ingestion state, and canonical document metadata. |

The example `diagnostics` interface should hide the graph and retrieval details from both HTTP handlers and tests:

```python
async def diagnose(request: DiagnosticRequest) -> DiagnosticReport:
    ...
```

The request should identify the project, question, and optional source scope. The report should contain a concise diagnosis, recommended actions, uncertainty or missing evidence, and citations. Keep provider/model configuration out of each call; inject configured dependencies when constructing the module.

Use in-memory adapters for interface-level tests. Keep production adapters for PostgreSQL, Qdrant, and the selected model provider behind the same internal seams. Avoid exposing internal graph nodes, vector-store calls, or database-specific records through the HTTP interface.

## Developer Documentation Agent Workflow

DocLore uses LangGraph to orchestrate a systematic, observable multi-step workflow. Rather than treating documentation and debugging as separate tools, the unified context engine interprets user intent and executes a multi-stage evidence gathering and synthesis pipeline:

1. **Interpret user intent (`understand_query`)** — Analyzes the developer query across the 5 technical documentation intent modes:
   - `PROJECT_OVERVIEW`: High-level system overview, repository structure, onboarding.
   - `API_DETAILS`: OpenAPI specifications, routes, parameters, schema models, auth contracts.
   - `ARCHITECTURAL_DESIGN`: Component boundaries, data flow, architecture diagram correlation.
   - `CODING_STANDARDS`: Internal style guide rules, lint conventions, naming standards.
   - `EXECUTION_TRACING`: Runtime diagnostics, error debugging, and failure tracing.
   Extracts HTTP status codes (e.g. 401, 500), technical error tokens (e.g. `AUTH_INVALID_TOKEN`), HTTP operations (`POST /orders`), and target module paths.

2. **Retrieve multi-source evidence (`retrieve_evidence`)** — Runs hybrid search over all registered knowledge silos (OpenAPI specifications, architecture diagrams, style guides, troubleshooting runbooks, and source repositories) using sparse BM25 keyword matching and dense vector embeddings fused via Reciprocal Rank Fusion (RRF).

3. **Inspect technical specifications & standards (`inspect_spec_and_standards`)** — Correlates retrieved contracts:
   - Validates required parameters, headers, and security schemes against OpenAPI specs.
   - Inspects architecture diagram topology and subsystem boundaries.
   - Assesses compliance against internal style guide rules and lint conventions.

4. **Inspect repository code via multi-language scanners & AST (`inspect_code_ast`)** — Analyzes actual repository source files across Python (AST), TypeScript/JavaScript (Express/Next.js routes, classes, interfaces), Go (Gin/Echo endpoints, structs, functions), Rust (impl, structs, enums, functions), and configuration/deployment manifests with exact line numbers and symbol provenance.

5. **Synthesize resolution (`synthesize`)** — Synthesizes multi-layered insights into a structured response, delivering clear explanations, practical code/config examples, and actionable steps grounded in retrieved facts.

6. **Validate citations (`validate_citations`)** — Enforces zero hallucinated citations by validating every reference against exact file paths and line ranges (`L{start}–L{end}`) preserved from source extraction. Reports insufficient evidence when no matching sources exist rather than fabricating certainty.

## Evidence and provenance

Make provenance a first-class part of the canonical document/chunk model. At minimum retain:

- project, source, document, and chunk identifiers;
- source type and canonical path or URL;
- source revision or content hash;
- chunk text and the extraction/parser version;
- line range when available, plus section or structural path when useful;
- retrieval method and ranking metadata for diagnosis observability.

Resolve citations from stored provenance, not from model-generated paths or line numbers. For code and line-oriented text formats, preserve exact line ranges during extraction. For formats where a line range has no meaning, cite the stable document section or object path instead.

Index updates should be idempotent for the same source revision. Remove or supersede stale chunks when a source changes, without mixing evidence from different revisions in one citation.

## Retrieval and storage

### Initial recommendation

- PostgreSQL is the canonical store for projects, source definitions, sync runs, and document/chunk metadata.
- Qdrant stores dense vectors and BM25 sparse vectors for each searchable chunk.
- The `retrieval` module fetches dense and sparse ranked lists and combines them using explicit Reciprocal Rank Fusion. Keep this logic independent of Qdrant so tests can assert ranking behavior with deterministic lists.
- Apply project/source filters before combining results, and retain per-branch ranks for debugging.

This keeps BM25 as a real sparse retrieval path and avoids describing ordinary database full-text ranking as BM25. Qdrant plus PostgreSQL is still a two-store operational choice; confirm it before implementation.

### Retrieval acceptance checks

- Exact identifiers, HTTP status codes, header names, file paths, and symbols must survive parsing and rank well.
- Semantic queries should still find conceptually relevant material when wording differs.
- RRF behavior must be covered by deterministic tests, including duplicate results and ties.
- Every result must include resolvable provenance.
- A small golden query set should check expected evidence retrieval before answer-quality tuning.

## Ingestion boundaries

Represent each input mechanism as an ingestion adapter that emits the same canonical document/chunk format. Keep parsing separate from indexing so formats can be added without changing the diagnostic workflow.

All source categories in the product brief are in scope. Deliver them feature by feature through the same ingestion interface rather than attempting every connector in the first release. Recommended order for the first vertical slices:

1. Markdown files;
2. OpenAPI documents;
3. a local or uploaded Python repository snapshot.
4. issue logs;
5. internal style guides;
6. architecture diagrams.

This order establishes text, API-structure, and code evidence before adding the remaining source formats. Reorder it if product priorities demand. Implement each category as an adapter with its own parsing, sync, provenance, and failure behavior. Do not imply a source is supported until that adapter is implemented and verified.

## HTTP and frontend shape

Start with a small versioned HTTP surface:

- `POST /api/v1/diagnoses` — submit a question and receive a diagnostic report;
- `GET /api/v1/projects/{project_id}/sources` — list configured sources and sync status;
- `POST /api/v1/projects/{project_id}/sources` — register a supported source;
- `POST /api/v1/sources/{source_id}/sync` — start or request a source refresh;
- `GET /api/v1/diagnoses/{diagnosis_id}` — retrieve a persisted diagnosis if diagnosis history is enabled.

Keep diagnosis streaming and background job semantics out of the first release unless the desired latency or ingestion size requires them. If synchronization becomes long-running, return a job identifier and expose job status rather than keeping an HTTP request open.

The React UI should focus first on a question input, project/source scope, diagnosis summary, next steps, and inspectable citations. Render evidence locations from the API response; do not reconstruct source locations in the browser. Use the approved DocLore logo and palette from `AGENTS.md` and `assets/brand/`; do not let a UI theme default replace them.

## Suggested repository layout

```text
apps/
  api/
    pyproject.toml
    src/doclore/
      api/                  # FastAPI routing and HTTP schemas
      diagnostics/          # Public diagnosis interface and report model
      workflow/             # LangGraph implementation and internal state
      sources/              # Source records and synchronization
      ingestion/            # Format adapters, extraction, normalization
      retrieval/             # Dense + BM25 + RRF implementation
      code_analysis/        # Repository scanning and language adapters
      evidence/              # Provenance and citation validation
      persistence/           # PostgreSQL and Qdrant adapters
    tests/
  web/
    src/
      features/              # Search/diagnosis/source UI
      shared/                # Shared UI and HTTP utilities
    tests/
docs/
  architecture.md
assets/
  brand/
```

Keep the initial implementation in this repository layout unless an existing framework or deployment requirement suggests a better fit. Avoid creating separate packages for every row in the module table before there is implementation pressure to do so.

## Implementation plan

### Phase 0 — Confirm operational decisions

- All source categories listed in the product brief are in scope; implement and release them incrementally, one supported adapter at a time.
- Select the chat/analysis model and embedding model/provider, including whether local inference is required.
- Confirm whether this is initially a single-user local tool or a multi-user hosted application; this determines authentication, tenant isolation, and source-access controls.
- Confirm PostgreSQL + Qdrant or choose a different BM25/vector storage approach.

**Exit:** decisions are recorded; no credentials are committed; source access and retention expectations are known.

### Phase 1 — Runnable foundation

- Create a FastAPI backend and React + TypeScript frontend.
- Add environment-based configuration, health checks, local development instructions, and lint/type/test commands.
- Establish project and source identifiers and stable request/response schemas.
- Add migrations and local PostgreSQL/Qdrant development setup if those stores are confirmed.

**Exit:** both apps start locally, health checks pass, and a typed frontend request can reach the API.

### Phase 2 — One end-to-end ingestion slice

- Implement the first source adapters in the agreed feature order; the recommendation is Markdown, then OpenAPI, then Python repositories.
- Normalize content into canonical documents and provenance-preserving chunks.
- Persist source revisions and sync status; make repeated syncs idempotent.
- Add Python repository extraction as the next adapter.

**Exit:** a user can register each implemented source type, sync it, and inspect indexed documents with correct provenance. The UI and API clearly distinguish supported source types from planned ones.

### Phase 3 — Hybrid retrieval

- Generate dense and BM25 sparse representations for chunks.
- Implement filtered retrieval and RRF behind the `retrieval.search` interface.
- Build deterministic retrieval tests and a small golden set of exact-term and semantic queries.

**Exit:** the golden set retrieves the expected source evidence and every result resolves to its source location.

### Phase 4 — Diagnostic workflow

- Add the bounded LangGraph workflow and typed state.
- Implement API-spec inspection and Python AST analysis as conditional branches.
- Add model-provider adapter, evidence-grounded synthesis, citation validation, and explicit partial/failure outcomes.

**Exit:** an end-to-end API test diagnoses a seeded issue from multiple evidence types and cites only retrieved sources.

### Phase 5 — React diagnosis experience

- Build project/source selection, query submission, diagnosis, action list, and citation inspection.
- Apply the supplied DocLore logo and approved palette.
- Include loading, empty, error, partial-evidence, and success states.

**Exit:** a developer can complete the seeded diagnostic workflow through the UI and follow citations to their evidence.

### Phase 6 — Reliability and expansion

- Add ingestion limits, retry policy, cancellation, structured logs, and workflow tracing.
- Measure latency, retrieval quality, citation validity, and model usage against the golden set.
- Add issue-log, style-guide, and architecture-diagram adapters as separate features, validating the extraction and citation approach for each format.
- Add authentication, tenant isolation, access controls, and deployment hardening before exposing private repositories to a hosted multi-user service.

**Exit:** every source category from the product brief has an implemented and tested adapter, supported-source status is explicit, quality checks are repeatable, and deployment/security controls match the confirmed operating model.

## Testing strategy

- **Module interface tests:** call `diagnose`, `search`, and ingestion interfaces with in-memory adapters and assert observable outcomes.
- **Algorithm tests:** cover RRF ranking, chunk provenance, citation validation, and parser edge cases without external services.
- **Integration tests:** use disposable PostgreSQL and Qdrant instances to verify migrations, indexing, filtering, and deletion/update behavior.
- **Workflow tests:** inject deterministic model and retrieval adapters; exercise successful, partial, timeout, and unavailable-source paths.
- **End-to-end tests:** seed a small repository and docs set with a known API authorization mismatch; assert report shape, cited source identities, and exact line ranges.
- **Frontend tests:** cover query submission, loading/error/empty/partial states, citation rendering, and keyboard accessibility.
- **Evaluation set:** retain representative questions and expected evidence; track retrieval recall and citation validity before optimizing prose.

## Decisions still requiring confirmation

1. **Model providers:** choose the answer-generation and embedding providers, or require local inference.
2. **Operating model:** local single-user first, or hosted multi-user from the start.
3. **Search infrastructure:** recommended PostgreSQL + Qdrant with dense and BM25 sparse vectors, and application-level RRF.
4. **Repository ingestion mode:** uploaded/archive snapshot first, local filesystem path, or direct Git provider connection.
5. **Feature order:** the listed order is a recommendation, not a restriction; choose which source adapter to implement first.
