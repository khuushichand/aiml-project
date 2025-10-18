# Watchlists PRD (tldw_server)

Status: Draft v0.1
Owner: Core Maintainers
Target Release: 0.2.x

## 1) Summary
A Watchlists feature that lets a user maintain categorized collections of media sources (websites, blogs, news sites, RSS feeds, forums) and schedule scraping/ingestion jobs. Each run detects new content since the last scrape, parses it using existing ingestion pipelines, and produces configurable outputs (e.g., newsletter, briefing, MECE summaries, or audio briefings via TTS). Results can be delivered, downloaded, exported as Chatbooks, and/or ingested into the Media DB.

## 2) Problem Statement
Users want recurring, customizable content collection without manual effort. Today, users can ingest URLs one-off, but cannot:
- Maintain curated, tagged, grouped lists of sources
- Run scheduled crawls with per-source rules
- Detect changes reliably and avoid duplicates
- Aggregate and transform fresh items into briefings/newsletters/audio

## 3) Goals and Non‑Goals
### Goals (MVP → v1)
- Create and manage sources (URL + type + settings) and logical groupings/tags
- Schedule scraping jobs for selected sources, groups, or entire watchlists
- Detect and ingest only new/changed items since last scrape
- Parse text/content with existing pipelines and extract key metadata
- Generate configured outputs (Markdown/HTML; briefing/newsletter/MECE); optional TTS
- Provide API + WebUI to manage sources, jobs, runs, and outputs

### Non‑Goals (initial)
- Full headless browser automation (Playwright/Puppeteer) for heavy JS sites
- Paid-site login/session management and paywall bypass
- Distributed crawler fleet / proxy rotation
- Sophisticated anti-bot evasion

## 4) Personas
- Researcher/Analyst: Curates sources across domains, wants briefings on a schedule
- Power User: Builds fine-grained categories/tags and multiple jobs
- Casual User: Imports a few RSS feeds and gets daily digest

## 5) Success Metrics
- Job success rate (%) and average run time
- New items discovered per run vs. duplicates ignored
- Output generation success (no failures) and open/usage rates (local)
- User retention: number of active watchlists/jobs over time

## 6) Scope
### In-Scope
- Sources: websites/blogs, news sites, RSS feeds, forums (basic patterns)
- Grouping: categories, tags; many-to-many
- Scheduling: interval/cron; per-host rate limits; retries
- Scraping: HTTP requests with ETag/Last-Modified when available; RSS polling
- Parsing: HTML article extraction; RSS item parsing; reuse existing ingestion
- Dedup/change detection: URL canonicalization + content hash
- Output generation: Markdown/HTML briefings; optional MECE summaries; optional TTS
- Delivery: save as files; ingest aggregated artifact; Chatbook export

### Out-of-Scope (initial)
- Headless browser rendering for SPA-only sites
- OAuth/login flows for gated sources
- Multi-tenant sharing of watchlists (post‑MVP)

## 7) User Stories
MVP
- As a user, I can add a list of URLs (RSS and sites) to my catalog, assign tags, and put them into groups/sections.
- As a user, I can create a job selecting multiple categories/tags or specific sources; set a schedule; and run it on demand.
- As a user, when a job runs, it only collects items that are new/updated since the last run.
- As a user, I can preview scrape results before saving the job.
- As a user, I can view run logs, counts of new items, and any errors.
- As a user, I can generate a Markdown briefing from the collected items and download it.

v1 Enhancements
- As a user, I can pick templates (newsletter, MECE, narrative) and store defaults per job.
- As a user, I can create an audio briefing using TTS and download or ingest it.
- As a user, I can export the run as a Chatbook or ingest into Media DB as a single artifact.
- As a user, I can set domain-level rate limits and max concurrency per job.

## 8) UX Flows (High-Level)
- Manage Sources: Add → Auto-detect type (RSS vs HTML) → Edit settings → Tag/Group
- Create Job: Choose scope (sources/groups/tags/all in watchlist) → Schedule → Options → Preview → Save
- Run Job: Manual trigger or scheduled → Live log/WS → View results → Generate outputs → Download or Ingest
- Review: Filter items by date/source/tag → Mark reviewed → Re-run or regenerate outputs

## 9) Functional Requirements
- Sources
  - Create, read, update, delete (CRUD) sources with metadata and settings
  - Types: `rss`, `site` (front page with top‑N), `forum` (basic list selectors)
  - Settings per type (see Data Model) including selectors and max items
- Grouping and Tags
  - Many-to-many: sources ↔ groups; sources ↔ tags
  - Filter UI and API for type, tag, group, search
- Jobs
  - Scope: selected sources, groups, tags, or entire watchlist
  - Schedule: cron/interval; active flag; time window; per-host delay; retry policy
  - “Run now”, “Dry run/Preview”, “Pause/Resume”
- Scraping/Collection
  - HTTP GET with `If-Modified-Since`/`If-None-Match` when present; follow redirects
  - RSS: track `guid`/`link`/`pubDate` with de-dup on canonical link and hash
  - Sites: extract article links from front page using CSS selector or auto-rules; limit top‑N
  - Forums: pagination selector and item link selector (basic)
- Parsing
  - Article content extraction via existing ingestion pipeline (HTML→text)
  - Metadata extraction: title, author (if available), publish date, canonical link
- Dedup & Change Detection
  - Compute normalized URL and SHA256 of stripped main content to detect new/updated
  - Ignore “stale” if unchanged since last run
- Outputs
  - Types: `newsletter_markdown`, `briefing_markdown`, `mece_markdown`, `newsletter_html`
  - Templating: configurable templates with variables (job, date range, items)
  - Optional TTS audio briefing via existing TTS module
  - Export as Chatbook; ingest output into Media DB
- Observability & Logs
  - Per-run stats: items discovered/new/updated/ignored; errors; duration
  - View run logs; WebSocket stream for live status (optional v1)
- AuthNZ & Security
  - Per-user ownership; AuthNZ integrated (single-user API key or JWT)
  - Respect robots.txt by default (configurable per job with warning)
  - Rate limiting and per-host delays to avoid abuse

## 10) Non-Functional Requirements
- Performance: jobs should process typical RSS/site lists (<100 sources) within minutes
- Reliability: retries with exponential backoff; partial failure isolation
- Resource Use: bounded concurrency; per-host delays; cache ETag/Last-Modified
- Privacy: no telemetry; logs are local; do not store credentials

## 11) Data Model (Conceptual)
Tables are persisted in `Databases/Media_DB_v2.db` via project DB abstractions.

Entities
- watchlists
  - id, user_id, name, description, tags (optional JSON), created_at, updated_at
- sources
  - id, user_id, name, url, source_type[`rss`|`site`|`forum`], active, settings_json,
    last_scraped_at, etag, last_modified, status, created_at, updated_at
  - settings_json examples:
    - rss: { "accept_categories": [..] }
    - site: { "index_url": "https://...", "article_link_selector": "a.headline", "max_items": 10,
              "content_selector": "article", "follow_sitemap": false }
    - forum: { "index_url": "https://...", "item_selector": "a.topic", "pagination_selector": "a.next" }
- groups
  - id, user_id, name, description, parent_group_id (nullable)
- source_groups (join)
  - source_id, group_id
- tags
  - id, user_id, name
- source_tags (join)
  - source_id, tag_id
- scrape_jobs
  - id, user_id, watchlist_id (nullable), name, description, scope_json (sources|groups|tags),
    schedule_expr (cron or interval), active, max_concurrency, per_host_delay_ms,
    retry_policy_json, output_prefs_json, created_at, updated_at, last_run_at, next_run_at
- scrape_runs
  - id, job_id, status[`queued`|`running`|`success`|`partial`|`failed`], started_at, finished_at,
    stats_json, error_msg, log_path
- scraped_items
  - id, source_id, job_id, run_id, url, canonical_url, title, author, published_at,
    content_text, content_html, fingerprint_sha256, metadata_json, status, created_at,
    updated_at, media_item_id (nullable, if ingested)
- outputs
  - id, job_id, run_id, type, title, format[`md`|`html`|`mp3`], storage_path,
    metadata_json, created_at, media_item_id (nullable), chatbook_path (nullable)

Indexes
- sources.url, scraped_items.canonical_url, scraped_items.fingerprint_sha256
- scrape_runs.job_id, outputs.run_id

Retention
- Keep runs and logs for configurable time window; items retained unless user deletes

## 12) APIs (FastAPI, OpenAPI 3.0)
Base: `/api/v1/watchlists/...`

Sources
- `POST /api/v1/watchlists/sources` create
- `GET /api/v1/watchlists/sources` list (filters: `q`, `type`, `tag`, `group`, `active`)
- `GET /api/v1/watchlists/sources/{id}` get
- `PATCH /api/v1/watchlists/sources/{id}` update
- `DELETE /api/v1/watchlists/sources/{id}` delete
- `POST /api/v1/watchlists/sources:bulk` bulk create/update
- `POST /api/v1/watchlists/sources/{id}/test` dry-run fetch + parse preview

Groups/Tags
- `POST /api/v1/watchlists/groups` CRUD; `POST /api/v1/watchlists/tags` CRUD
- `POST /api/v1/watchlists/sources/{id}/groups` assign; `.../tags` assign

Jobs
- `POST /api/v1/watchlists/jobs` create
- `GET /api/v1/watchlists/jobs` list
- `GET /api/v1/watchlists/jobs/{id}` get
- `PATCH /api/v1/watchlists/jobs/{id}` update (pause/resume)
- `DELETE /api/v1/watchlists/jobs/{id}` delete
- `POST /api/v1/watchlists/jobs/{id}/run` trigger now
- `GET /api/v1/watchlists/jobs/{id}/runs` list runs
- `GET /api/v1/watchlists/runs/{run_id}` run details
- `GET /api/v1/watchlists/runs/{run_id}/log` log text
- `WS  /api/v1/watchlists/runs/{run_id}/stream` live status (optional v1)

Items & Outputs
- `GET /api/v1/watchlists/items` list (filters: date, source, group, tag, job, status)
- `GET /api/v1/watchlists/items/{id}` get; `PATCH .../items/{id}` mark reviewed
- `POST /api/v1/watchlists/outputs` generate output from a set (body: item ids + template)
- `GET /api/v1/watchlists/outputs/{id}` metadata; `.../download` file
- Integrations: `POST /api/v1/chatbooks/export` (existing), `POST /api/v1/media/process` for ingest

Schemas
- Pydantic in `tldw_Server_API/app/api/v1/schemas/watchlists.py`

## 13) System Design & Components
Modules
- Core: `tldw_Server_API/app/core/Watchlists/`
  - `manager.py` (CRUD + orchestration), `scraper.py` (fetchers), `parser.py` (dispatch to existing ingestion),
    `dedupe.py`, `outputs.py` (templating + TTS), `scheduler.py` (APScheduler or async tasks), `models.py` (DB ops)
- API: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Services: `tldw_Server_API/app/services/watchlist_jobs.py` (background runs, queues)
- WebUI: `tldw_Server_API/WebUI/watchlists/*` (pages, components)

Key Flows
- Fetch: HTTP client with per-host delay and ETag/Last-Modified cache
- Parse: For RSS, parse feed entries → items; For site/forum, get index → extract links → fetch articles → extract main content
- Dedupe: Normalize URL + SHA256 main text; skip unchanged
- Persist: Write items and run stats; optional ingest via existing Media DB path
- Output: Render Markdown/HTML; optional MECE summarization via LLM; optional TTS via `/api/v1/audio/speech`

Concurrency & Scheduling
- Use bounded worker pool; per-host delay; max concurrent fetches per job
- Schedules stored on jobs; APScheduler or FastAPI background tasks register on startup

## 14) Configuration
- Defaults in `tldw_Server_API/Config_Files/config.txt` (watchlist section)
  - `WATCHLIST_MAX_CONCURRENCY`, `WATCHLIST_PER_HOST_DELAY_MS`, `WATCHLIST_MAX_ITEMS_PER_SOURCE`, `WATCHLIST_OBEY_ROBOTS=true`
- Env overrides permitted
- Templates in `tldw_Server_API/Config_Files/templates/watchlists/`

## 15) Security & Compliance
- Respect robots.txt by default; explicit opt-out shows warning
- Rate limiting with slowapi or internal limiter for endpoints that trigger runs
- Input validation for URLs/types; sanitize selectors; size limits on responses
- Never log secrets; redact URLs with tokens if any

## 16) Error Handling & Logging
- Structured logs via loguru: run id, job id, source id, URL, error category
- User-facing errors use consistent formats and HTTP codes
- Retries with backoff for transient network failures; hard-fail on 4xx (except 429 with retry)

## 17) Migration Plan
- Add new tables via DB management layer (`app/core/DB_Management`)
- Data migration script: create tables + indexes; idempotent
- No changes to existing tables required initially; link final outputs to Media DB by `media_item_id` when ingested

## 18) Testing Strategy
- Unit
  - URL normalization; content hashing; RSS parsing; selector extraction; schedule parsing; template rendering
- Integration
  - End-to-end: create sources → create job → dry run → run → generate output
  - API contract tests with httpx; DB fixtures for in-memory SQLite
- Property-Based
  - Dedup invariants (same content variants map to same fingerprint)
- Mocks
  - Network calls; time; LLM/TTS providers
- Markers
  - `unit`, `integration`, `external_api` (skipped by default)

## 19) Acceptance Criteria (MVP)
- CRUD for sources, groups, tags available via API and WebUI
- Create a job that selects by groups/tags and runs on schedule
- Job run discovers and stores only new items from RSS and simple sites
- User can preview scrape for a source
- Generate Markdown briefing for a run and download it
- Run logs and stats visible; errors surfaced clearly

## 20) Rollout Plan
- Phase 1 (MVP): RSS + site (front page + top‑N) support; Markdown briefing; manual + interval schedule; WebUI basics
- Phase 2 (v1): MECE template + HTML newsletter; TTS audio; Chatbook export integration
- Phase 3: Forum patterns; cron expressions; live WS logs; richer templates

## 21) Risks & Mitigations
- Dynamic JS sites: mark unsupported initially; later headless rendering option
- Anti-scraping / rate limits: obey robots; per-host delays; backoff on 429
- Content variability: allow per-source selectors; robust defaults
- Legal/compliance: user acknowledgment for scraping settings; documentation

## 22) Open Questions
- Should outputs be versioned per job with retention policy defaults?
- Template editor in WebUI or file-based only initially?
- Do we support email delivery natively (SMTP) or leave to user export?

---
Implementation should follow project conventions:
- Core logic in `app/core/Watchlists/`, endpoints in `app/api/v1/endpoints/`, schemas in `app/api/v1/schemas/`, services in `app/services/`
- Tests in `tldw_Server_API/tests/watchlists/` with unit/integration split
- Use `MediaDatabase` abstractions for DB access; avoid raw SQL outside DB layer
