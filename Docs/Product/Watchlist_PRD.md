# Watchlists PRD (tldw_server)

Status: MVP snapshot (v0.2 codebase) - outputs now include TTL + delivery support
Owner: Core Maintainers
Target Release: 0.2.x

## 1) Summary
A Watchlists feature that lets a user maintain categorized collections of media sources (websites, blogs, news sites, RSS feeds) and schedule scraping/ingestion jobs. The v0.2 implementation ships an end-to-end pipeline: jobs resolve scope (tags/groups/sources), fetch RSS feeds or site front pages, deduplicate items, ingest new content into the Media DB, and persist structured `scraped_items`. Users can review items, mark them as reviewed, generate Markdown or HTML briefings with per-job defaults, and optionally deliver outputs via email or Chatbook generated documents. The WebUI now surfaces watchlist jobs, items, outputs, and template/delivery defaults on the admin tab. Audio/TTS, Media DB aggregation exports, and forum ingestion remain future work.

## 2) Problem Statement
Users want recurring, customizable content collection without manual effort. Today, users can ingest URLs one-off, but cannot:
- Maintain curated, tagged, grouped lists of sources
- Run scheduled crawls with per-source rules
- Detect changes reliably and avoid duplicates
- Aggregate and transform fresh items into briefings/newsletters/audio

## 3) Goals and Non-Goals
### Goals (implemented MVP → v1 roadmap)
- [x] Create and manage sources (URL + type + settings) and logical groupings/tags
- [x] Schedule scraping jobs for selected sources, groups, or tag combinations
- [x] Detect and ingest only new/changed items since last scrape (ETag/Last-Modified, dedupe table)
- [x] Parse text/content with existing ingestion pipeline and capture run stats
- [x] Generate Markdown/HTML briefings from scraped items; download via API
- [x] Provide API to manage sources, jobs, runs, items, and outputs
- [x] File-backed template management API plus per-job defaults (v0.2.1)
- [x] Output retention/versioning with configurable TTLs, email + Chatbook delivery hooks
- [x] Watchlists tab in WebUI for items/outputs/templates management, including per-job template/retention/delivery configuration
- [ ] WebUI authoring for rich template creation; MECE/newsletter presets and deeper per-job defaults
- [ ] Optional TTS/audio briefings and Chatbook/Media DB aggregation exports

### Non-Goals (initial)
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
- Sources: websites/blogs, news sites, RSS feeds (forums are deferred)
- Grouping: categories, tags; many-to-many
- Scheduling: interval/cron; per-host rate limits; retries
- Scraping: HTTP requests with ETag/Last-Modified when available; RSS polling
- Parsing: HTML article extraction; RSS item parsing; reuse existing ingestion
- Dedup/change detection: URL canonicalization + content hash
- Output generation: Markdown/HTML briefings with template store; MECE/HTML variants and TTS are future increments
- Delivery: Download rendered output; configurable email + Chatbook deliveries via NotificationsService with per-job defaults; Media DB aggregation planned. Templates stored under `Config_Files/templates/watchlists/` (override with `WATCHLIST_TEMPLATE_DIR`).
- Admin WebUI slice: watchlists tab for listing items, creating outputs (with delivery options), and managing templates

### Out-of-Scope (initial)
- Headless browser rendering for SPA-only sites
- OAuth/login flows for gated sources
- Multi-tenant sharing of watchlists (post-MVP)

## 7) User Stories
MVP (implemented)
- As a user, I can add a list of URLs (RSS and sites) to my catalog, assign tags, and put them into groups/sections.
- As a user, I can create a job selecting multiple categories/tags or specific sources; set a schedule; and run it on demand.
- As a user, when a job runs, it only collects items that are new/updated since the last run.
- As a user, I can preview scrape results before saving the job.
- As a user, I can view run logs, counts of new items, and any errors.
- As a user, I can generate a Markdown briefing from the collected items and download it.
- As a user, I can review scraped items, filter them (status/reviewed), and mark them as reviewed or ignored.

v1 Enhancements (in progress)
- As a user, I can tailor MECE/newsletter presets via a UI template editor and share defaults across jobs.
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
  - Types: `rss`, `site` (front page with top-N), `forum` (basic list selectors)
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
  - Sites: extract article links from front page using CSS selector or auto-rules; limit top-N
  - Forums: pagination selector and item link selector (basic)
- Parsing
  - Article content extraction via existing ingestion pipeline (HTML→text)
  - Metadata extraction: title, author (if available), publish date, canonical link
- Dedup & Change Detection
  - Compute normalized URL and SHA256 of stripped main content to detect new/updated
  - Ignore “stale” if unchanged since last run
- Outputs
  - Current types: Markdown (`md`) and HTML (`html`) briefings generated from scraped items
  - Stored inline (`content` column) with metadata (item ids, counts)
  - Future: templating, MECE/newsletter variants, TTS audio, Chatbook export
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

## 11) Data Model (Current Implementation)
All tables live in each user’s primary SQLite Media DB (`Databases/user_databases/<user_id>/Media_DB_v2.db`). Postgres parity is future work.

| Table | Purpose | Key Columns |
| --- | --- | --- |
| `sources` | Source catalog | `id`, `user_id`, `name`, `url`, `source_type` (`rss` \| `site`), `settings_json`, `last_scraped_at`, `etag`, `last_modified`, `consec_not_modified`, `defer_until`, `status` |
| `groups` | Logical groupings | `id`, `user_id`, `name`, `description`, `parent_group_id` |
| `source_groups` | Source ↔ group join | `source_id`, `group_id` |
| `tags` | Normalized tag names | `id`, `user_id`, `name` |
| `source_tags` | Source ↔ tag join | `source_id`, `tag_id` |
| `scrape_jobs` | Job definitions | `id`, `user_id`, `name`, `scope_json`, `schedule_expr`, `schedule_timezone`, `active`, `max_concurrency`, `per_host_delay_ms`, `retry_policy_json`, `output_prefs_json`, `last_run_at`, `next_run_at`, `wf_schedule_id` |
| `scrape_runs` | Run history | `id`, `job_id`, `status`, `started_at`, `finished_at`, `stats_json`, `error_msg`, `log_path` |
| `scrape_run_items` | Run → ingested media | `run_id`, `media_id`, `source_id` |
| `source_seen_items` | RSS dedupe cache | `source_id`, `item_key`, `etag`, `last_modified`, `first_seen_at`, `last_seen_at` |
| `scraped_items` | Structured run items | `id`, `run_id`, `job_id`, `source_id`, `media_id`, `media_uuid`, `url`, `title`, `summary`, `published_at`, `tags_json`, `status`, `reviewed`, `created_at` |
| `watchlist_outputs` | Generated outputs | `id`, `run_id`, `job_id`, `type`, `format`, `title`, `content`, `storage_path`, `metadata_json`, `media_item_id`, `chatbook_path`, `version`, `expires_at`, `created_at` |

Retention: per-user SQLite (default). TTL is enforced via `expires_at` with env defaults (`WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS`, `WATCHLIST_OUTPUT_TEMP_TTL_SECONDS`) and per-job overrides. Expired rows are purged on access. Postgres parity is still planned.

## 12) APIs (FastAPI, OpenAPI 3.0 - implemented)
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

Items
- `GET  /api/v1/watchlists/items` (filters: `run_id`, `job_id`, `source_id`, `status`, `reviewed`, `q`, `since`, `until`)
- `GET  /api/v1/watchlists/items/{id}` retrieve item
- `PATCH /api/v1/watchlists/items/{id}` mark reviewed / update status

Outputs
- `POST /api/v1/watchlists/outputs` generate Markdown or HTML output from the most recent items (optional explicit item IDs) with support for TTL overrides and delivery configs (`deliveries.email`, `deliveries.chatbook`)
- `GET  /api/v1/watchlists/outputs` list outputs (filter by `run_id`, `job_id`)
- `GET  /api/v1/watchlists/outputs/{id}` fetch metadata/content
- `GET  /api/v1/watchlists/outputs/{id}/download` download rendered content (`text/markdown` or `text/html`)

Settings
- `GET /api/v1/watchlists/settings` returns default TTLs/environment info used by WebUI

Not yet implemented: watchlist-level CRUD, WS streams, Chatbook export, audio output, preview/dry-run endpoints.

Schemas
- Pydantic in `tldw_Server_API/app/api/v1/schemas/watchlists.py`

## 13) System Design & Components
Modules
- Core: `tldw_Server_API/app/core/Watchlists/`
  - `manager.py` (CRUD + orchestration), `scraper.py` (fetchers), `parser.py` (dispatch to existing ingestion),
    `dedupe.py`, `outputs.py` (templating + TTS), `scheduler.py` (APScheduler or async tasks), `models.py` (DB ops)
- Notifications: `tldw_Server_API/app/core/Notifications/service.py` (email + Chatbook delivery bridge using AuthNZ email service and Chatbook document generator)
- API: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Services: `tldw_Server_API/app/services/watchlist_jobs.py` (background runs, queues)
- WebUI: `tldw_Server_API/WebUI/tabs/watchlists_content.html` + helpers in `WebUI/js/tab-functions.js` (items/outputs/templates panel)

Key Flows
- Fetch: HTTP client with per-host delay and ETag/Last-Modified cache
- Parse: For RSS, parse feed entries → items; For site/forum, get index → extract links → fetch articles → extract main content
- Dedupe: Normalize URL + SHA256 main text; skip unchanged
- Persist: Write items and run stats; optional ingest via existing Media DB path
- Output & Delivery: Render Markdown/HTML, apply template store, enforce retention, and hand off to NotificationsService for email/Chatbook delivery (Media DB aggregation pending); optional MECE summarization via LLM; optional TTS via `/api/v1/audio/speech`
- Collections Bridge: Stage 1 of Content Collections will introduce a shared `content_items` layer inside Collections DB. Watchlists will dual-write to this layer (in addition to Media DB) to power unified `/items` queries without altering existing Media DB schemas.

Concurrency & Scheduling
- Use bounded worker pool; per-host delay; max concurrent fetches per job
- Schedules stored on jobs; APScheduler or FastAPI background tasks register on startup

## 14) Configuration
- Defaults in `tldw_Server_API/Config_Files/config.txt` (watchlist section)
  - `WATCHLIST_MAX_CONCURRENCY`, `WATCHLIST_PER_HOST_DELAY_MS`, `WATCHLIST_MAX_ITEMS_PER_SOURCE`, `WATCHLIST_OBEY_ROBOTS=true`
- Env overrides permitted
- Templates in `tldw_Server_API/Config_Files/templates/watchlists/`
- TTL overrides via env: `WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS`, `WATCHLIST_OUTPUT_TEMP_TTL_SECONDS` (per-job `output_prefs.retention` takes precedence)

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
- SQLite: handled via `WatchlistsDatabase.ensure_schema()` (idempotent `CREATE TABLE IF NOT EXISTS` plus column backfills).
- Postgres: not supported yet; requires dedicated schema patch and SQL adjustments (`INSERT ... ON CONFLICT` etc.).
- Future migrations: outputs templating, watchlist collections, retention TTL.

## 18) Testing Strategy
- Unit
  - URL normalization; content hashing; RSS parsing; selector extraction; schedule parsing; template rendering
  - Embedding queue enqueue on watchlist ingestion (best-effort Redis stub)
- Integration
  - End-to-end: create sources → create job → dry run → run → generate output
  - API contract tests with httpx; DB fixtures for in-memory SQLite
  - NotificationsService email/chatbook delivery flows exercised with mock provider/Chatbook store
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
- Phase 1 (complete): RSS + site (front page/top-N) support; Markdown/HTML briefing; manual + interval schedule; API review tools.
- Phase 2 (active): MECE/newsletter automation + TTS, richer template editing, Media DB ingest toggle. **Delivered:** per-job output defaults, NotificationsService delivery, admin WebUI wiring.
- Phase 3 (planned): TTS audio (if not completed in Phase 2), Chatbook export enhancements, forum patterns, WS live logs, multi-tenant sharing, optional Postgres backend.

## 21) Risks & Mitigations
- Dynamic JS sites: mark unsupported initially; later headless rendering option
- Anti-scraping / rate limits: obey robots; per-host delays; backoff on 429
- Content variability: allow per-source selectors; robust defaults
- Legal/compliance: user acknowledgment for scraping settings; documentation

## 22) Open Questions / Next Steps
- Outputs retention/versioning strategy and storage limits.
  **Answer:** Shipped: every output is versioned and stamped with `expires_at`. Global defaults are driven by `WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS` / `WATCHLIST_OUTPUT_TEMP_TTL_SECONDS`, and jobs can override via `output_prefs.retention`. Naming convention `<RUN_NAME>-Output-<n>` holds; add admin UX for managing expirations.
- Template/editor experience (file-based vs. UI-driven), templating language.
  **Answer:** File-based templates + CRUD API are live (Jinja2 sandbox). Next iteration: UI-driven editor built atop the same endpoints. Template language remains Jinja2; validation hooks exist server-side.
- Delivery mechanisms (email, Chatbook, Media DB aggregation).
  **Answer:** Email delivery (mockable SMTP) and Chatbook generated-document storage ship in v0.2.1 with per-job defaults. Media DB aggregation remains roadmap work.
- Per-job rate limiting UI; per-user Postgres backend support.
  **Answer:** Expose rate-limit controls via API first; surface UI later. Postgres backend is deferred until the broader DB abstraction is ready.
- WebUI parity for new items/outputs endpoints.
  **Answer:** Achieved: the Next.js admin watchlists tab lists items, previews outputs, edits per-job defaults (template/retention/delivery), and surfaces run stats. Future UI work focuses on template editing and richer item review.
- Content Collections alignment.
  **Answer:** When the Collections `content_items` tables land, update Watchlists ingestion to dual-write (Media DB + Collections DB) and ensure `/watchlists/items` and `/items` endpoints stay consistent. Postgres enablement remains deferred to Stage 2 so both modules migrate together.

---
Implementation should follow project conventions:
- Core logic in `app/core/Watchlists/`, endpoints in `app/api/v1/endpoints/`, schemas in `app/api/v1/schemas/`, services in `app/services/`
- Tests in `tldw_Server_API/tests/watchlists/` with unit/integration split (pipeline, scheduler jitter, TTL/delivery integration)
- Use `MediaDatabase` abstractions for DB access; avoid raw SQL outside DB layer
