# Brainstorm: Watchlist Template Creation — Improvements & Extensions

## Your Role

You are a **product designer and systems thinker** with deep experience in:
- Content management and publishing pipelines (CMS, newsletter tools, static site generators)
- Template/markup authoring UX (Jinja2, Handlebars, Liquid, MDX)
- LLM-augmented content workflows (AI-assisted writing, automated synthesis, editorial pipelines)

Your goal is to generate **concrete, prioritized improvement ideas** for the template creation subsystem described below. Ideas should range from quick UX wins to ambitious new capabilities. For each idea, explain the user problem it solves, sketch the UX, and flag implementation considerations.

---

## System Under Review

### What This Is

A **Watchlists** module within a research assistant platform. Users configure information sources (RSS feeds, news sites, forums), set up automated polling schedules, and use **Jinja2 templates** to transform collected items into derivative content: daily briefings, newsletters, analytical reports, and audio newscasts.

The template system is the **final mile** — it determines how raw data becomes something a human wants to read or listen to.

### Current Template Capabilities

#### Authoring Modes
- **Basic Mode**: Recipe-based builder. User picks a recipe (Briefing, Newsletter, MECE Analysis), toggles checkboxes (include links, executive summary, timestamps, tags), and the system generates a Jinja2 template automatically via `buildTemplateFromRecipe()`.
- **Advanced Mode**: Full Jinja2 code editor with syntax validation, version history, quick-insert snippet palette, variable reference docs, and a visual composer pane.
- Users can start in Basic and escalate to Advanced; a warning fires if they downgrade with unsaved advanced context.

#### Pre-Built Recipes (3 currently)
| Recipe | Format | Description |
|--------|--------|-------------|
| `briefing_md` | Markdown | Daily digest with optional executive summary |
| `newsletter_html` | HTML | Email-friendly indexed format |
| `mece_md` | Markdown | Categorized analysis grouped by tags |

Each recipe supports toggleable options: `includeExecutiveSummary`, `includeLinks`, `includePublishedAt`, `includeTags`.

#### Template Variables Available at Render Time
Templates receive a context object with:
- `title` — Monitor/job name
- `generated_at` — Render timestamp
- `items[]` — Array of collected articles, each with:
  - `title`, `url`, `summary`, `llm_summary`, `content`, `author`
  - `published_at`, `tags[]`, `source_name`, `source_url`
  - `word_count`, `reading_time_estimate`

#### Backend Pipeline
1. Monitor job runs on schedule → scrapes/fetches items
2. Items filtered by job's filter rules (keyword, regex, date, author)
3. Template loaded by name + version
4. Jinja2 rendered in a `SandboxedEnvironment` against the item context
5. Output persisted as file, optionally ingested to Media DB
6. Delivery: email, chatbook export, file download, or audio (multi-voice TTS)

#### Existing Compose/Flow-Check Endpoints
The backend already has two AI-powered endpoints (partially wired to UI):
- `POST /templates/compose/section` — Generates draft content for a named section given items + instructions
- `POST /templates/compose/flow-check` — Checks section transitions, flags duplicates, suggests revision for cohesion

#### Version Control
- Templates are versioned automatically on save
- Users can load any historical version
- Metadata tracks `composer_ast`, `composer_sync_hash`, and `composer_sync_status`

#### Storage
- File-based: `Config_Files/templates/watchlists/{name}.{md|html}` + `{name}.meta.json`
- Four built-in templates seeded on first startup

---

### The Seed Idea: Inline Prompts

A user suggested the ability to define **per-section LLM prompts within a template**, so that different parts of a newsletter can use different generation strategies, and then a final pass ensures all sections "flow correctly" together.

Example mental model:
```
Template: "Weekly Tech Digest"
├── Section 1: "Executive Summary"
│   └── inline_prompt: "Write a 3-sentence executive summary of the most important developments"
├── Section 2: "AI & ML News"
│   └── inline_prompt: "Summarize AI/ML items with a focus on practical applications, 2-3 sentences each"
├── Section 3: "Security Updates"
│   └── inline_prompt: "List security items as bullet points with severity assessment"
├── Section 4: "Opinion Corner"
│   └── inline_prompt: "Write a brief editorial take on the single most surprising item this week"
└── Final pass: flow-check across all generated sections
```

The `compose/section` and `compose/flow-check` endpoints already exist on the backend — the question is how to expose this in the template authoring UX and what extensions would make it powerful.

---

## What I Want From You

### Part 1: Inline Prompt System Design
Deep-dive on the seed idea. Address:
1. **Syntax**: How should inline prompts be expressed within Jinja2 templates? (Custom tags? Jinja2 extensions? Front-matter? Separate sidecar file?)
2. **Section scoping**: How does the user define which items feed into which section? (Tag-based routing? Explicit filters per section? Automatic clustering?)
3. **Generation flow**: What's the execution order? (All sections in parallel → flow-check? Sequential with context carry-forward?)
4. **Editing UX**: How does Basic Mode surface this without overwhelming non-technical users? How does Advanced Mode give full control?
5. **Preview**: How does the user preview inline-prompt output before committing to a run?
6. **Failure modes**: What happens when one section's LLM call fails? Timeout? Token limit exceeded? Inappropriate content?

### Part 2: Template System Improvements (Beyond Inline Prompts)
Generate 10-15 additional improvement ideas across these categories:

**A. Authoring Experience**
- How can we make template creation faster, more discoverable, and less error-prone?
- What's missing from the recipe system?
- How can the visual composer be more useful?

**B. Template Intelligence**
- What AI-assisted features would help template authors?
- How can templates be smarter about the data they're rendering?
- What conditional logic patterns do users commonly need?

**C. Output Quality & Variety**
- How can templates produce better, more varied output?
- What output formats are we missing?
- How can users A/B test template variations?

**D. Reusability & Sharing**
- How can templates be shared, forked, and composed from reusable parts?
- What does a "template marketplace" or "community recipes" look like?
- How do partials/includes/inheritance work?

**E. Operational Maturity**
- What's missing for production use at scale (50+ monitors, 100+ sources)?
- Template performance monitoring? Output quality metrics?
- Regression detection across template versions?

### Part 3: Priority Matrix
Organize all ideas (inline prompts + improvements) into a priority matrix:

| Priority | Idea | User Problem Solved | Effort | Dependencies |
|----------|------|---------------------|--------|--------------|
| P0 | ... | ... | Low/Med/High | ... |

Use these priority criteria:
- **P0**: Directly blocks or degrades a primary use case today
- **P1**: Significant quality-of-life improvement for weekly users
- **P2**: Power-user feature or competitive differentiator
- **P3**: Nice-to-have or future-looking

---

## Constraints & Preferences

- **Backend is Python/FastAPI** with Jinja2 `SandboxedEnvironment`. Any template syntax extensions must work within Jinja2's extension API or via preprocessing.
- **Frontend is React/TypeScript** with Ant Design components and i18n via react-i18next.
- **LLM calls are provider-agnostic** — the system supports 16+ providers. Assume any LLM feature works with any provider.
- **Prefer incremental additions** over rewrites. The recipe system and Basic/Advanced mode split are working well — extend them, don't replace them.
- **Audio output is a first-class use case.** Templates that produce audio briefings (via multi-voice TTS) are equally important as text/HTML output.
- **Self-hosted, privacy-first.** No cloud dependencies. Template sharing would be export/import, not a hosted marketplace.
- **The compose/section and flow-check endpoints already exist.** Leverage them rather than designing from scratch.
