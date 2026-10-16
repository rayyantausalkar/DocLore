# Agent guidance

Before planning or changing code, check the installed skills in `.agents/skills/` and use the relevant ones by default:

- For architecture, module boundaries, or non-trivial code-logic decisions, read and apply `codebase-design/SKILL.md`.
- For new or redesigned interfaces, visual design, and page or component layouts, read and apply `hallmark/SKILL.md`.
- For animations, transitions, interaction feedback, or micro-interactions, read and apply both `animate/SKILL.md` and `emil-design-eng/SKILL.md`.

Apply these skills proactively when their topic is in scope, without waiting for the user to name them. Do not load or apply unrelated skills for tasks that do not touch these areas.

## Project context

DocLore is a developer documentation and debugging engine that connects technical knowledge across API specifications, Markdown documentation, architecture diagrams, source repositories, issue logs, and internal style guides. It should help developers diagnose problems such as API authorization failures by correlating relevant specifications, troubleshooting guidance, and actual code, then return an actionable resolution with links to the exact source locations.

The planned stack is:

- Backend: Python with FastAPI.
- Frontend: React.
- Orchestration: LangGraph for the multi-step diagnostic workflow.
- Retrieval: combine dense vector retrieval and sparse BM25 keyword search using Reciprocal Rank Fusion.
- Code understanding: AST-based analysis of repository source files.

Keep these product goals and technology choices in mind when implementing features. Do not silently substitute a different stack or claim capabilities (such as supported ingestion sources or exact line citations) that the implementation does not provide.

## DocLore brand rules

The approved brand assets are:

- Logo: `assets/brand/doclore-logo.png`
- Color palette reference: `assets/brand/doclore-color-palette.png`

These assets and the palette below are the source of truth for all DocLore UI and visual-design work. Use the supplied logo as-is; do not redraw, replace, distort, or recolor it. Do not invent a new logo, visual identity, theme, or decorative style. Do not select random colors or substitute a skill's default/catalog palette. These brand rules take precedence over design-skill defaults.

Use only these palette colors:

- Industrial Yellow: `#F2C94C`
- Dark Olive: `#303321`
- Slate Grey: `#68747A`
- Light Beige: `#D9D8D2`
- Near Black: `#151718`

Do not add other hues, neutrals, gradients, or unapproved color tokens. Use the supplied palette reference when choosing among the approved colors. Keep new design decisions consistent with the provided logo and palette; if the brand assets do not settle a significant visual choice, ask rather than inventing a separate direction.
