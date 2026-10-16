import React, { useState } from 'react'

interface LandingPageProps {
  onEnterWorkspace: () => void
  onImportRepo: () => void
}

interface DemoScenario {
  id: string
  label: string
  intent: string
  query: string
  steps: Array<{
    prefix: string
    text: string
    type: 'prompt' | 'info' | 'success' | 'citation'
  }>
}

const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: 'tracing',
    label: 'Execution Tracing',
    intent: 'EXECUTION_TRACING',
    query: 'Why am I getting 401 AUTH_INVALID_TOKEN on POST /orders?',
    steps: [
      {
        prefix: '[1/6 Intent Interpretation]',
        text: 'Classified intent as EXECUTION_TRACING (Target: HTTP 401, Route: POST /orders)',
        type: 'info',
      },
      {
        prefix: '[2/6 Hybrid RRF Retrieval]',
        text: 'Queried Dense Vectors + BM25 Lexical across 5 silos — Fused RRF k=60',
        type: 'info',
      },
      {
        prefix: '[3/6 Spec Cross-Reference]',
        text: 'OpenAPI BearerAuth contract requires header Authorization: Bearer <token>',
        type: 'info',
      },
      {
        prefix: '[4/6 AST Code Analysis]',
        text: 'Inspected src/routes/orders.py:46 verify_bearer_token() via Python AST',
        type: 'info',
      },
      {
        prefix: '[5/6 Synthesized Resolution]',
        text: 'Root Cause: Missing Bearer prefix in Authorization header authorization payload',
        type: 'success',
      },
      {
        prefix: '[6/6 Validated Citations]',
        text: 'src/routes/orders.py:L46-L52 • specs/orders.yaml:L28-L38 • docs/auth-guide.md:L7-L16',
        type: 'citation',
      },
    ],
  },
  {
    id: 'overview',
    label: 'Project Overview',
    intent: 'PROJECT_OVERVIEW',
    query: 'Give me a high-level project overview, purpose, and codebase structure',
    steps: [
      {
        prefix: '[1/6 Intent Interpretation]',
        text: 'Classified intent as PROJECT_OVERVIEW (Entry point discovery & hierarchy analysis)',
        type: 'info',
      },
      {
        prefix: '[2/6 Hybrid RRF Retrieval]',
        text: 'Queried repository README, system diagrams, and architectural documentation',
        type: 'info',
      },
      {
        prefix: '[3/6 Spec Cross-Reference]',
        text: 'Identified core service boundaries across 4 subsystem modules',
        type: 'info',
      },
      {
        prefix: '[4/6 AST Code Analysis]',
        text: 'Mapped top-level directory routers in src/main.py and dependency injection graph',
        type: 'info',
      },
      {
        prefix: '[5/6 Synthesized Resolution]',
        text: 'Generated structured onboarding map with directory purposes and module dependencies',
        type: 'success',
      },
      {
        prefix: '[6/6 Verified Citations]',
        text: 'Omitted line citations for clean conversational architectural overview',
        type: 'citation',
      },
    ],
  },
  {
    id: 'api',
    label: 'API Details',
    intent: 'API_DETAILS',
    query: 'What route endpoints, parameters, and schema models are defined in the API specs?',
    steps: [
      {
        prefix: '[1/6 Intent Interpretation]',
        text: 'Classified intent as API_DETAILS (Target: OpenAPI 3.x schema inspection)',
        type: 'info',
      },
      {
        prefix: '[2/6 Hybrid RRF Retrieval]',
        text: 'Retrieved OpenAPI path operations, parameters, request bodies, and response codes',
        type: 'info',
      },
      {
        prefix: '[3/6 Spec Cross-Reference]',
        text: 'Indexed 18 route definitions, 5 Pydantic schema models, and 3 security schemes',
        type: 'info',
      },
      {
        prefix: '[4/6 AST Code Analysis]',
        text: 'Cross-referenced OpenAPI schemas against actual route function signatures in routes.py',
        type: 'info',
      },
      {
        prefix: '[5/6 Synthesized Resolution]',
        text: 'Cataloged complete endpoint inventory with required query parameters and JSON models',
        type: 'success',
      },
      {
        prefix: '[6/6 Validated Citations]',
        text: 'specs/openapi.json:L14-L86 • src/api/routes.py:L72-L138',
        type: 'citation',
      },
    ],
  },
  {
    id: 'arch',
    label: 'Architectural Design',
    intent: 'ARCHITECTURAL_DESIGN',
    query: 'Explain the architectural design, component boundaries, and request flow',
    steps: [
      {
        prefix: '[1/6 Intent Interpretation]',
        text: 'Classified intent as ARCHITECTURAL_DESIGN (Subsystem topology and data flow)',
        type: 'info',
      },
      {
        prefix: '[2/6 Hybrid RRF Retrieval]',
        text: 'Fused Mermaid architecture diagrams, subsystem readmes, and routing topologies',
        type: 'info',
      },
      {
        prefix: '[3/6 Spec Cross-Reference]',
        text: 'Extracted client -> API Gateway -> Service Worker -> Event Store flow sequence',
        type: 'info',
      },
      {
        prefix: '[4/6 AST Code Analysis]',
        text: 'Verified adapter boundaries and protocol inheritance across services',
        type: 'info',
      },
      {
        prefix: '[5/6 Synthesized Resolution]',
        text: 'Explained layer decoupling, state graph execution, and persistence guarantees',
        type: 'success',
      },
      {
        prefix: '[6/6 Validated Citations]',
        text: 'docs/architecture.mmd:L1-L24 • docs/system_design.md:L40-L75',
        type: 'citation',
      },
    ],
  },
  {
    id: 'standards',
    label: 'Coding Standards',
    intent: 'CODING_STANDARDS',
    query: 'What coding standards and style guide rules apply to this codebase?',
    steps: [
      {
        prefix: '[1/6 Intent Interpretation]',
        text: 'Classified intent as CODING_STANDARDS (Linting, typing, and naming rules)',
        type: 'info',
      },
      {
        prefix: '[2/6 Hybrid RRF Retrieval]',
        text: 'Queried engineering style guides, error-payload standards, and linter configurations',
        type: 'info',
      },
      {
        prefix: '[3/6 Spec Cross-Reference]',
        text: 'Correlated RFC 7807 problem details specification and PEP 484 type annotations',
        type: 'info',
      },
      {
        prefix: '[4/6 AST Code Analysis]',
        text: 'Scanned codebase AST for type hints and docstring conventions',
        type: 'info',
      },
      {
        prefix: '[5/6 Synthesized Resolution]',
        text: 'Outlined strict error handling conventions, typing requirements, and formatting rules',
        type: 'success',
      },
      {
        prefix: '[6/6 Validated Citations]',
        text: 'guides/style-guide.md:L12-L48 • pyproject.toml:L30-L55',
        type: 'citation',
      },
    ],
  },
]

export const LandingPage: React.FC<LandingPageProps> = ({
  onEnterWorkspace,
  onImportRepo,
}) => {
  const [activeScenarioId, setActiveScenarioId] = useState('tracing')
  const currentScenario = DEMO_SCENARIOS.find((s) => s.id === activeScenarioId) || DEMO_SCENARIOS[0]

  return (
    <div className="doclore-landing">
      {/* Navigation Bar */}
      <header className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-brand">
            <img
              src="/doclore-logo.png"
              alt="DocLore"
              className="landing-logo"
              width="36"
              height="36"
            />
            <span className="landing-brand-text">DocLore</span>
            <span className="landing-version-pill">v1.0 Hybrid Engine</span>
          </div>

          <nav className="landing-nav-links">
            <a href="#problem" className="landing-nav-link">Problem</a>
            <a href="#solution" className="landing-nav-link">Unified Engine</a>
            <a href="#pipeline" className="landing-nav-link">6-Step Workflow</a>
            <a href="#intents" className="landing-nav-link">5 Intent Modes</a>
          </nav>

          <div className="landing-nav-cta">
            <button
              type="button"
              className="btn-landing-secondary"
              onClick={onImportRepo}
            >
              Import Repository
            </button>
            <button
              type="button"
              className="btn-landing-primary"
              onClick={onEnterWorkspace}
            >
              Open Workspace &rarr;
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-backdrop" />
        <div className="landing-hero-container">
          <div className="hero-kicker">
            <span className="hero-kicker-dot" />
            <span>UNIFIED DEVELOPER DOCUMENTATION & CONTEXT AGENT</span>
          </div>

          <h1 className="hero-headline">
            Technical knowledge is fragmented.
            <br />
            <span className="hero-headline-accent">DocLore bridges the silos.</span>
          </h1>

          <p className="hero-description">
            OpenAPI specs, GitHub repositories, architecture diagrams, troubleshooting guides,
            and coding standards—unified into a single multi-agent state graph with hybrid
            RRF retrieval and AST-verified line citations.
          </p>

          <div className="hero-actions">
            <button
              type="button"
              className="btn-hero-primary"
              onClick={onEnterWorkspace}
            >
              Launch Documentation Workspace
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </button>
            <button
              type="button"
              className="btn-hero-secondary"
              onClick={onImportRepo}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75">
                <circle cx="5" cy="4" r="2" />
                <circle cx="5" cy="12" r="2" />
                <circle cx="12" cy="7" r="2" />
                <path d="M5 6v4M5 7c0-1.5 2-3 7-3" />
              </svg>
              Connect Public GitHub Repo
            </button>
          </div>

          {/* Interactive Live Workflow Preview Card */}
          <div className="hero-terminal-card">
            <div className="terminal-header">
              <div className="terminal-scenario-tabs">
                {DEMO_SCENARIOS.map((scenario) => (
                  <button
                    key={scenario.id}
                    type="button"
                    className={`scenario-tab-btn ${
                      scenario.id === activeScenarioId ? 'scenario-tab-btn--active' : ''
                    }`}
                    onClick={() => setActiveScenarioId(scenario.id)}
                  >
                    {scenario.label}
                  </button>
                ))}
              </div>
              <span className="terminal-badge">AST Verified</span>
            </div>

            <div className="terminal-body">
              <div className="terminal-line terminal-line--prompt">
                <span className="t-prompt">&gt;</span>
                <span className="t-cmd">doclore query &quot;{currentScenario.query}&quot;</span>
              </div>
              {currentScenario.steps.map((st, idx) => (
                <div key={idx} className={`terminal-line terminal-line--${st.type}`}>
                  <span className="t-prefix">{st.prefix}</span>
                  <span className="t-text">{st.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Problem & Solution Grid */}
      <section id="problem" className="landing-section">
        <div className="landing-section-header">
          <span className="section-eyebrow">THE FRAGMENTATION PROBLEM</span>
          <h2 className="section-title">Documentation and Code Live in Different Worlds</h2>
          <p className="section-subtext">
            Developers lose hours manually bridging high-level architectural specs, repo-level implementation details,
            and operational standards.
          </p>
        </div>

        <div className="problem-solution-grid">
          <div className="glass-card problem-card">
            <div className="card-top-icon card-top-icon--danger">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h3 className="card-heading">The Isolated Silos</h3>
            <ul className="problem-list">
              <li>
                <strong>Disconnected Repositories:</strong> Code is separated from OpenAPI specs and architecture topologies.
              </li>
              <li>
                <strong>Outdated Runbooks:</strong> Troubleshooting documentation diverges from actual implementation changes.
              </li>
              <li>
                <strong>Keyword / Vector Blindspots:</strong> Basic search fails to correlate code call sites with API schemas.
              </li>
              <li>
                <strong>Hallucinated Citations:</strong> Generic LLMs fabricate line numbers, paths, and configurations.
              </li>
            </ul>
          </div>

          <div className="glass-card solution-card">
            <div className="card-top-icon card-top-icon--success">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
            <h3 className="card-heading">The DocLore Engine</h3>
            <ul className="solution-list">
              <li>
                <strong>Unified Context Engine:</strong> Ingests all 5 knowledge silos into a coherent multi-agent graph.
              </li>
              <li>
                <strong>Hybrid RRF Retrieval:</strong> Dense vector embeddings combined with sparse BM25 keyword matching.
              </li>
              <li>
                <strong>AST-Based Code Analysis:</strong> Parses real function structures, decorators, and line numbers.
              </li>
              <li>
                <strong>Zero Hallucinations:</strong> Every citation is validated against exact preserved line ranges.
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* 5 Knowledge Silos Section */}
      <section id="solution" className="landing-section landing-section--darker">
        <div className="landing-section-header">
          <span className="section-eyebrow">UNIFIED INGESTION SYSTEM</span>
          <h2 className="section-title">5 Disconnected Silos, 1 Coherent Interface</h2>
          <p className="section-subtext">
            DocLore ingests technical data formats with line-preserving provenance.
          </p>
        </div>

        <div className="silos-cards-grid">
          <div className="silo-card">
            <div className="silo-tag">OpenAPI 3.x</div>
            <h4 className="silo-title">API Specifications</h4>
            <p className="silo-desc">
              Parses endpoints, query/body schemas, headers, status codes, and security schemes into structured search nodes.
            </p>
          </div>

          <div className="silo-card">
            <div className="silo-tag">GitHub / Git</div>
            <h4 className="silo-title">Source Repositories</h4>
            <p className="silo-desc">
              Clones repositories and runs Python AST parsing to locate function scopes, route decorators, and exact line ranges.
            </p>
          </div>

          <div className="silo-card">
            <div className="silo-tag">Mermaid / Specs</div>
            <h4 className="silo-title">Architecture Diagrams</h4>
            <p className="silo-desc">
              Extracts system topologies, component boundaries, and directional data flows to explain architectural design.
            </p>
          </div>

          <div className="silo-card">
            <div className="silo-tag">Markdown Runbooks</div>
            <h4 className="silo-title">Troubleshooting Guides</h4>
            <p className="silo-desc">
              Indexes incident guides, symptoms, known root causes, and diagnostic steps with heading-level context.
            </p>
          </div>

          <div className="silo-card silo-card--accent">
            <div className="silo-tag">Standards / Linters</div>
            <h4 className="silo-title">Internal Coding Standards</h4>
            <p className="silo-desc">
              Correlates internal style guidelines, PEP 8 rules, naming conventions, and typing policies against actual code.
            </p>
          </div>
        </div>
      </section>

      {/* 6-Step Workflow Section */}
      <section id="pipeline" className="landing-section">
        <div className="landing-section-header">
          <span className="section-eyebrow">MULTI-AGENT STATE GRAPH</span>
          <h2 className="section-title">The Systematic 6-Step Workflow</h2>
          <p className="section-subtext">
            Orchestrated via LangGraph with full traceability and validation at each step.
          </p>
        </div>

        <div className="workflow-timeline">
          <div className="timeline-node">
            <div className="node-number">01</div>
            <div className="node-content">
              <h4 className="node-title">Interpret Developer Intent</h4>
              <p className="node-desc">
                Classifies query into one of 5 technical modes, extracting error tokens, status codes, and route paths.
              </p>
            </div>
          </div>

          <div className="timeline-connector" />

          <div className="timeline-node">
            <div className="node-number">02</div>
            <div className="node-content">
              <h4 className="node-title">Retrieve Multi-Source Evidence</h4>
              <p className="node-desc">
                Runs hybrid BM25 lexical search and dense vector embeddings fused via Reciprocal Rank Fusion (RRF).
              </p>
            </div>
          </div>

          <div className="timeline-connector" />

          <div className="timeline-node">
            <div className="node-number">03</div>
            <div className="node-content">
              <h4 className="node-title">Inspect Specs &amp; Standards</h4>
              <p className="node-desc">
                Cross-references OpenAPI contracts, architecture topologies, and coding standards against the query.
              </p>
            </div>
          </div>

          <div className="timeline-connector" />

          <div className="timeline-node">
            <div className="node-number">04</div>
            <div className="node-content">
              <h4 className="node-title">Inspect Code via AST</h4>
              <p className="node-desc">
                Performs Python AST analysis to extract exact function signatures, decorators, handlers, and line spans.
              </p>
            </div>
          </div>

          <div className="timeline-connector" />

          <div className="timeline-node">
            <div className="node-number">05</div>
            <div className="node-content">
              <h4 className="node-title">Synthesize Resolution</h4>
              <p className="node-desc">
                Synthesizes multi-layered findings into clear technical explanations with actionable code/config examples.
              </p>
            </div>
          </div>

          <div className="timeline-connector" />

          <div className="timeline-node">
            <div className="node-number">06</div>
            <div className="node-content">
              <h4 className="node-title">Validate Line Citations</h4>
              <p className="node-desc">
                Reconciles all references against preserved source lines (zero hallucinated citations allowed).
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 5 Technical Documentation Intent Modes */}
      <section id="intents" className="landing-section landing-section--darker">
        <div className="landing-section-header">
          <span className="section-eyebrow">DEVELOPER EXPERIENCE MODES</span>
          <h2 className="section-title">Engineered for 5 Core Engineering Tasks</h2>
          <p className="section-subtext">
            Whether onboarding or diagnosing a critical production bug, DocLore adapts its workflow.
          </p>
        </div>

        <div className="intents-grid">
          <div className="intent-box">
            <div className="intent-box-header">
              <span className="intent-badge">PROJECT_OVERVIEW</span>
              <h4>Project Overview &amp; Onboarding</h4>
            </div>
            <p className="intent-box-p">
              Get high-level system summaries, module hierarchies, and repository entry points for rapid team onboarding.
            </p>
            <div className="intent-example">
              &quot;Give me a high-level project overview, purpose, and codebase structure&quot;
            </div>
          </div>

          <div className="intent-box">
            <div className="intent-box-header">
              <span className="intent-badge">API_DETAILS</span>
              <h4>API Specifications &amp; Schemas</h4>
            </div>
            <p className="intent-box-p">
              Inspect endpoint paths, required query/body schemas, response models, and security requirements.
            </p>
            <div className="intent-example">
              &quot;What route endpoints, parameters, and schema models are defined in the API specs?&quot;
            </div>
          </div>

          <div className="intent-box">
            <div className="intent-box-header">
              <span className="intent-badge">ARCHITECTURAL_DESIGN</span>
              <h4>Architectural Design Logic</h4>
            </div>
            <p className="intent-box-p">
              Understand component boundaries, subsystem communication protocols, and directional data flows.
            </p>
            <div className="intent-example">
              &quot;Explain the architectural design, component boundaries, and request flow&quot;
            </div>
          </div>

          <div className="intent-box">
            <div className="intent-box-header">
              <span className="intent-badge">CODING_STANDARDS</span>
              <h4>Coding Standard Compliance</h4>
            </div>
            <p className="intent-box-p">
              Check repository adherence to style guides, PEP 8 rules, naming conventions, and typing rules.
            </p>
            <div className="intent-example">
              &quot;What coding standards and style guide rules apply to this codebase?&quot;
            </div>
          </div>

          <div className="intent-box">
            <div className="intent-box-header">
              <span className="intent-badge">EXECUTION_TRACING</span>
              <h4>Execution Tracing &amp; Debugging</h4>
            </div>
            <p className="intent-box-p">
              Diagnose runtime failures, trace authorization errors (401/403), and correlate code with incident runbooks.
            </p>
            <div className="intent-example">
              &quot;Trace runtime execution and debug why requests fail with 401 Unauthorized&quot;
            </div>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section className="landing-cta-banner">
        <div className="cta-banner-content">
          <h2 className="cta-banner-title">Ready to unify your engineering documentation?</h2>
          <p className="cta-banner-desc">
            Connect your repository, attach OpenAPI contracts and runbooks, and query with verified line citations.
          </p>
          <div className="cta-banner-btns">
            <button
              type="button"
              className="btn-hero-primary"
              onClick={onEnterWorkspace}
            >
              Open DocLore Workspace &rarr;
            </button>
            <button
              type="button"
              className="btn-landing-secondary"
              onClick={onImportRepo}
            >
              Import GitHub Repository
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="footer-left">
            <img
              src="/doclore-logo.png"
              alt="DocLore"
              width="24"
              height="24"
            />
            <span className="footer-brand">DocLore</span>
            <span className="footer-tagline">&mdash; Developer Documentation &amp; Context Engine</span>
          </div>
          <div className="footer-right">
            <span>Built with FastAPI &bull; LangGraph &bull; React &bull; Python AST &bull; Hybrid RRF</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
