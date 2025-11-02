 # PRD: Content Collections (Watchlists + Reading List) for tldw_server

Version: 0.2
Owner: Core Maintainers (Server/API + WebUI)
Status: In Progress
Updated: 2025-10-19

Related: Project_Guidelines.md, AGENTS.md, tldw_Server_API/app/main.py

---

## 1. Summary

Content Collections unify two complementary workflows:
- **Watchlists**: Source-centric scheduled collection from websites/news sites/RSS with jobs, runs, aggregated outputs, template-driven rendering, versioning, retention/TTL, and delivery (email + Chatbook). *Status: implemented; WebUI admin flows now consume the new APIs.*
- **Reading List**: Ad-hoc link capture with a clean reader UI, statuses (saved/reading/read/archived), favorites, highlights/notes, import/export. *Status: capture/status/favorite flows and basic WebUI shipped; highlights/import remain in backlog.*

Both flows will share a normalized collections layer that references (but does not replace) the existing Media DB. Media DB remains the canonical artifact store; the collections layer will provide dedupe, metadata, and search connectivity across Watchlists and Reading. Outputs can be generated from scheduled runs or filtered item sets, exported as Chatbooks, delivered via email, or linked back into Media DB.

## 2. Goals and Non-Goals

### Goals (MVP → v1)
- [x] Unified content item model and shared ingestion/dedupe/search/embeddings.
- [x] Reading capture: save URL → readable text; statuses/tags/favorites; search; basic WebUI. *(Highlights/import/export still planned.)*
- [x] Watchlists: manage sources, groups/tags; jobs with schedule; runs with logs/stats; RSS + simple sites (front page + top-N).
- [ ] Outputs: Markdown briefing/newsletter; optional MECE; optional TTS audio; export/ingest. *(Markdown/HTML + retention/delivery shipped; MECE/TTS automation pending.)*
- [x] APIs and WebUI slices for items, reading, watchlists, and outputs.

### Non-Goals (initial)
- Headless JS rendering for SPA-only sites, session/login scraping.
- Social/public sharing; multi-tenant sharing of collections.
- Distributed crawler fleet/proxy rotation; sophisticated anti-bot evasion.

## 3. Personas and Value

- Researcher/Analyst: Scheduled briefings from curated sources + ad-hoc reading capture.
- Power User: Fine tags/groups, multiple jobs, custom templates.
- Casual User: Save a few URLs and get a simple daily/weekly digest.

Primary value: one local-first place to capture → read → organize → search/RAG → summarize → deliver.

## 4. Success Metrics

- Job success rate; median run duration; per-host throttle adherence.
- New items discovered vs. duplicates ignored; ingestion failure rate.
- Search P50 latency; embeddings backlog size; output generation success.
- User retention: active collections/jobs; items saved per week.

## 5. Scope

### In-Scope
- Watchlists sources/groups/tags/jobs/runs with ingestion pipeline, template store, retention/versioning, and delivery (implemented).
- File-based template management and API-driven template CRUD (implemented).
- Ad-hoc link capture and reader UI with statuses/favorites/highlights (planned).
- Unified collections data layer that references Media DB while enabling dedupe and metadata across origins (planned).
- RSS polling; simple site extraction (front page + top-N). Forums remain Phase 3 (planned).
- Canonical URL/content-hash dedupe and change detection (planned).
- Outputs in Markdown/HTML plus MECE/TTS variants; Chatbook delivery; optional Media DB ingestion (partially implemented-MECE/TTS automation and ingest toggles planned).
- FTS5 search and ChromaDB embeddings per user over collections data (planned).

### Out-of-Scope (initial)
- Paywall bypass; authenticated scraping; heavy JS rendering.
- Social/public sharing; multi-tenant sharing of collections.

## 6. User Stories (MVP + v1)

MVP
- Save a URL; see readable text quickly; tag/favorite; mark read/archived.
- Manage sources and tags/groups; create a job targeting selected sources/groups/tags.
- Run a job (now or scheduled) that only stores new/updated items; view run logs and stats.
- Search across all items (reading + watchlists) by keywords; filter by tags/status/origin/domain/date.
- Generate a Markdown briefing from a run or a filtered item set; download artifact.

v1
- MECE/narrative templates; HTML newsletter; one-click TTS audio briefing.
- Import Pocket/Instapaper into items; export as Chatbook.
- Highlights/notes in reader view.

## 7. UX Flows (High-Level)

- Items: Unified list with filters (origin, tags, status, domain, date); search; bulk select for outputs.
- Reader: Distraction-free item detail with actions (Tag, Favorite, Mark Read, Summarize, Listen). Highlights/notes (v1).
- Watchlists: Sources (CRUD, tags/groups); Jobs (scope, schedule, options); Runs (logs/stats); Outputs.
- Reading: Quick save, import/export; tags/status/favorites.

## 8. Functional Requirements

### 8.1 Unified Content Items
- Single table for items from any origin (reading/manual/import/watchlist).
- Fields: url, canonical_url, domain, title, author?, published_at?, clean_html, text, content_hash, word_count, reading_time_seconds, language?, metadata_json.
- Optional fields for reading features: status (saved/reading/read/archived), favorite, read_at.
- Relations: source_id?, job_id?, run_id?, media_item_id?; tags many-to-many; highlights (v1).
- Dedupe: canonical URL and/or content_hash on stripped main content; merge tags on duplicate saves.
- Status: **Complete** - `CollectionsDatabase` provides `content_items`, tag joins, FTS hooks, and watchlists dual-write; `/api/v1/items` now queries this layer before falling back to legacy Media DB search.

### 8.2 Ingestion & Parsing
- URL validation; safe fetch (timeouts, size caps, content-type checks); follow redirects.
- RSS: parse items; track guid/link/pubDate; dedupe by canonical link+hash.
- Sites: index fetch; extract article links (CSS selector or defaults); cap top-N per source.
- Forums: moved to Phase 3 and behind a feature flag; excluded from MVP/v1.
- Readability-style article extraction; sanitize HTML; derive plain text.
- Metadata extraction: title, author (if present), publish date, canonical link; compute domain.

### 8.3 Organization
- Tags: normalized strings; suggest recent; many-to-many with items and sources; backed by a `tags` table and join tables that reference `tag_id` (no free-text tag joins).
- Groups: hierarchical or flat; sources ↔ groups; items inherit source context for filtering.

### 8.4 Scheduling & Runs (Watchlists)
- Scheduler: APScheduler (AsyncIOScheduler) with SQLAlchemyJobStore for persistence across restarts.
- Timezone: all schedule expressions are interpreted and stored with timezone `UTC+8`.
- Jobs: scope (sources/groups/tags), schedule (interval/cron), active flag, per-host delay, max concurrency, retry policy.
- Runs: status (queued/running/success/partial/failed), stats (new/updated/ignored/errors), logs, started/finished times.
- HTTP caching: ETag/Last-Modified; send If-Modified-Since/If-None-Match when supported.

### 8.5 Search & RAG
- FTS5 virtual table over title/domain/text; filters by tags/status/origin/domain/date/job/run.
- Embeddings in ChromaDB with namespace per user; expose items via existing RAG endpoints (opt-in by user preference).
- Re-embedding policy: when an item’s normalized text changes (content_hash diff), upsert vectors for that item and remove the old vector; record `embedding_model`, `embedding_model_version`, and `embedding_ts` in metadata. Background job supports full re-index when the configured embedding model/version changes.
- Status: **Complete** - FTS5 writes are active for collections, and both reading saves and watchlist ingestion enqueue embeddings via `EMBEDDINGS_REDIS_URL`/`REDIS_URL` backed worker queues (best-effort when Redis unavailable). Regression tests cover queueing and offline behavior.

### 8.6 Outputs & Delivery
- Output types: newsletter_markdown, briefing_markdown, mece_markdown, newsletter_html (v1), tts_audio (v1).
- Inputs: item IDs, saved filter query, or run_id; templating with variables (job, date, items, tags).
- Templates: managed via API (CRUD) with DB-backed storage and seed defaults; preview supported. Watchlist-specific templates are stored under `Config_Files/templates/watchlists` (override via `WATCHLIST_TEMPLATE_DIR`).
- Delivery: download file; optional Media DB ingest, email (SMTP provider via `NotificationsService`), Chatbook document generation.
- Retention: global defaults via `WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS` / `WATCHLIST_OUTPUT_TEMP_TTL_SECONDS`, per-job overrides under `output_prefs.retention`, per-output overrides during generation.
- Status: **Partially complete** - API + retention/versioning + email/Chatbook delivery and WebUI controls shipped; MECE/TTS automation and Media DB ingest toggles remain planned.

### 8.7 Reading Features
- Status transitions (saved → reading → read/archived); favorites; per-item notes (basic); highlights (v1).
- Highlights anchoring: store `quote` and anchor via fuzzy text matching with `content_hash_ref`; offsets are advisory. On text change, attempt re-anchor; if failing, mark highlight `stale` while preserving original context.
- Import: Pocket/Instapaper (JSON/CSV) to items with tag merging; Export: JSONL or zip bundle.

### 8.8 Observability & Limits
- Structured logs (run/job/source/item); per-run metrics; error categories.
- Rate limiting on capture and run triggers; per-host throttling and bounded concurrency.
- Respect robots.txt by default (configurable per job with warning).

### 8.9 AuthNZ & Privacy
- Per-user isolation across items, sources, jobs, runs, outputs.
- Single-user API key and multi-user JWT modes supported.
- Local-first; no external telemetry.

## 9. Non-Functional Requirements

- Performance: typical libraries (<10k items) search P50 < 200ms; jobs on <100 sources finish in minutes.
- Reliability: retries with backoff; partial failure isolation.
- Resource use: capped response sizes; bounded concurrency; per-host delays.

## 10. Data Model (Conceptual)

Persist in per-user `Databases/user_databases/<user_id>/Media_DB_v2.db` via DB abstractions.

Entities
- content_items
  - id, user_id, origin[`reading`|`watchlist`|`import`|`manual`], url, canonical_url, domain, title,
    author, published_at, clean_html, text, content_hash, word_count, reading_time_seconds, language,
    status, favorite, metadata_json, created_at, updated_at, read_at,
    embedding_model (nullable), embedding_model_version (nullable), embedding_ts (nullable),
    source_id (nullable), job_id (nullable), run_id (nullable), media_item_id (nullable)
- item_tags (join)
  - item_id, tag_id
- item_highlights (v1)
  - id, item_id, quote, start_offset, end_offset, color, note, created_at,
    anchor_strategy[`fuzzy_quote`|`exact_offset`], content_hash_ref, context_before (nullable), context_after (nullable), state[`active`|`stale`]
- sources
  - id, user_id, name, url, source_type[`rss`|`site`|`forum`], active, settings_json,
    last_scraped_at, etag, last_modified, status, created_at, updated_at
- groups, source_groups (join)
  - groups: id, user_id, name, description, parent_group_id (nullable)
  - source_groups: source_id, group_id
- tags, source_tags (join)
  - tags: id, user_id, name
  - source_tags: source_id, tag_id
- scrape_jobs
  - id, user_id, name, description, scope_json (sources|groups|tags), schedule_expr,
    active, max_concurrency, per_host_delay_ms, retry_policy_json,
    output_prefs_json, schedule_timezone[`UTC+8`], created_at, updated_at, last_run_at, next_run_at
- scrape_runs
  - id, job_id, status, started_at, finished_at, stats_json, error_msg, log_path
- outputs
  - id, user_id, job_id (nullable), run_id (nullable), type, title, format[`md`|`html`|`mp3`],
    storage_path, metadata_json, created_at, media_item_id (nullable), chatbook_path (nullable)

Indexes
- content_items: canonical_url, content_hash, created_at; FTS5 (title, domain, text)
- tags: UNIQUE(user_id, name)
- item_tags: (item_id), (tag_id)
- source_tags: (source_id), (tag_id)
- sources.url; scrape_runs.job_id; outputs.run_id

Embeddings Mapping (ChromaDB)
- Collection: `items:{user_id}`; vector per item; metadata: `title`, `url`, `tags`, `origin`, `embedding_model`, `embedding_model_version`, `embedding_ts`, timestamps

Retention
- Runs/logs retained on a configurable window; outputs retained per policy; items retained until user deletes.

## 11. APIs (OpenAPI Style)

Base prefixes
- Reading: `/api/v1/reading`
- Watchlists: `/api/v1/watchlists`
- Items (shared): `/api/v1/items`
- Outputs: `/api/v1/outputs`

Reading
- `POST /reading/save` → save URL (title?, tags?, notes?)
- `GET /reading/items` → list, filters: q, tags, status, favorite, domain, date
- `GET /reading/items/{id}` → full item
- `PATCH /reading/items/{id}` → update title/tags/status/favorite/notes
- `DELETE /reading/items/{id}` → soft delete; `?hard=true`
- `POST /reading/import` → Pocket/Instapaper; returns job id
- `GET /reading/export` → JSONL/zip
- `POST /reading/items/{id}/highlight` (v1)

Watchlists
- `POST /watchlists/sources` | `GET /watchlists/sources` | `GET/PATCH/DELETE /watchlists/sources/{id}`
- `POST /watchlists/sources/bulk` (per-entry status + errors)
- `POST /watchlists/groups` | `POST /watchlists/tags` and assign to sources
- `POST /watchlists/sources/{id}/test` → dry-run preview
- `POST /watchlists/jobs` | `GET /watchlists/jobs` | `GET/PATCH/DELETE /watchlists/jobs/{id}`
- `POST /watchlists/jobs/{id}/run` → trigger now
- `GET /watchlists/jobs/{id}/runs` | `GET /watchlists/runs/{run_id}` | `GET /watchlists/runs/{run_id}/log`
- `WS /watchlists/runs/{run_id}/stream` (v1)

Shared Items
- `GET /items` → unified list (origin, tags, status, domain, date, job_id, run_id)
- `GET /items/{id}` → item regardless of origin

Tags Semantics (API)
- Endpoints that accept `tags` expect a list of tag names (strings).
- Server normalizes names (lowercase, trimmed), ensures existence in the per-user `tags` table (creating missing tags), and resolves to `tag_id`s for joins.
- Responses include tag names by default. For clients that need IDs, add `?include_tag_ids=true` to include `{name, id}` pairs in responses where applicable.
- Watchlists tag assignment endpoints accept names and follow the same normalization and resolution behavior.

Outputs
- `POST /outputs` → from item ids, saved filter, or run_id; body includes template id/options and TTS toggle
- `GET /outputs/{id}` | `GET /outputs/{id}/download`

Templates (Outputs)
- `GET /outputs/templates` | `POST /outputs/templates` | `GET /outputs/templates/{id}` | `PATCH /outputs/templates/{id}` | `DELETE /outputs/templates/{id}`
- `POST /outputs/templates/{id}/preview` → render with sample or provided item ids without persisting

Schemas
- Pydantic under `tldw_Server_API/app/api/v1/schemas/collections.py` (items), `watchlists.py`, and `reading.py`.

## 12. System Design & Components

Modules
- Core: `tldw_Server_API/app/core/Collections/`
  - `items.py` (CRUD, search, dedupe, embeddings queue)
  - `reading/` (capture/import/export, reader helpers)
  - `watchlists/` (manager, scraper, parser dispatch, scheduler, dedupe)
  - `outputs.py` (templating, rendering, TTS integration)
- API: `tldw_Server_API/app/api/v1/endpoints/reading.py`, `watchlists.py`, `items.py`, `outputs.py`
- Services: `tldw_Server_API/app/services/collection_jobs.py` (background queues, schedulers)
- WebUI: `tldw_Server_API/WebUI/collections/*` (items list/detail, reading), `.../watchlists/*`

Key Flows
- Fetch with per-host delay; use ETag/Last-Modified; safe timeouts/size limits.
- Parse via existing ingestion pipelines; sanitize and produce text.
- Dedupe normalize URL + SHA256 of main text.
- Persist item and update FTS5; enqueue embeddings; optionally enqueue summary.
- Outputs render markdown/html; optional TTS via `/api/v1/audio/speech`; export/ingest artifacts.

Scheduling
- APScheduler (AsyncIOScheduler) with SQLAlchemyJobStore persists schedules across restarts; timezone for all schedules is `UTC+8`. Bounded worker pool; global per-host throttles shared across jobs.

## 13. Configuration

- Defaults in `tldw_Server_API/Config_Files/config.txt` (collections/watchlists section):
  - `WATCHLIST_MAX_CONCURRENCY`, `WATCHLIST_PER_HOST_DELAY_MS`, `WATCHLIST_MAX_ITEMS_PER_SOURCE`, `WATCHLIST_OBEY_ROBOTS=true`
  - `ITEM_FETCH_TIMEOUT_MS`, `ITEM_MAX_DOWNLOAD_MB`
- Templates are DB-managed via API, with optional seed defaults loaded from `tldw_Server_API/Config_Files/templates/collections/` on first run.
- Env var overrides supported.

## 14. Security & Compliance

- Input validation for URLs and selectors; sanitize HTML; strip scripts/styles.
- Respect robots.txt by default with an explicit opt-out warning per job.
- Rate limit run triggers and imports; never log secrets or raw content.

## 15. Error Handling & Logging

- Consistent HTTP error formats; Loguru structured logs with context ids (user/job/run/source/item).
- Retries with exponential backoff on transient network errors; hard-fail on 4xx (except 429 with retry after).

## 16. Migration Plan

- Add new tables via `app/core/DB_Management`; idempotent migration script and indexes.
- No changes to existing tables required; link outputs/items to Media DB via `media_item_id` when ingested.

## 17. Testing Strategy

- Unit: URL canonicalization; hashing; RSS parsing; selector extraction; reader sanitization; template rendering; schedule parsing.
- Integration: reading save→ingest→retrieve→search; watchlist job→run→items→output; outputs download.
- Property-based: dedupe invariants (equivalent content → same fingerprint).
- Mocks: network calls; time; LLM/TTS providers; RSS fixtures; HTML fixtures.
- Markers: `unit`, `integration`, `external_api` (skipped by default).
- Coverage target: ≥80% for new modules.

- Scheduler persistence/timezone: time-freezing tests verifying APScheduler with SQLAlchemyJobStore persists jobs across restarts and interprets cron/interval triggers using timezone `UTC+8` (including DST and boundary conditions). Validate `next_run_at` computation and on-restart rehydration.

## 18. Implementation Roadmap (Media DB remains separate)

1. **Unified Collections Layer** - *shipped*
   - `content_items` + tag joins live in Collections DB alongside Media DB.
   - Watchlist ingestion dual-writes; `/api/v1/items` resolves from collections before falling back to legacy search.

2. **Reading Workflow** - *MVP shipped; highlights/import pending*
   - URL capture (save), status/favorite/tags, reader endpoints, and WebUI page delivered.
   - Highlights lifecycle and third-party import/export remain TODO.

3. **Search & Retrieval Enhancements** - *shipped*
   - FTS5 online updates for collections; embeddings queueing via Redis job manager; provenance filters exposed on `/items`.
   - End-to-end embeddings worker validation pending full worker stack smoke tests.

4. **Outputs & Delivery Expansion** - *in progress*
   - Markdown/HTML generation, retention TTLs, NotificationsService delivery, and output templates wired into WebUI.
   - MECE/TTS automation and Media DB ingest switch to follow.

5. **WebUI & Admin UX** - *shipped*
   - Next.js pages for Items, Reading, and Watchlists consume the new APIs; job output preferences editable (template, retention, email/chatbook deliveries).
   - Future: reader highlights UI, template editor, bulk item actions.

6. **Stage 2 - Postgres Enablement** - *planned*
   - Refactor schema creation/migration scripts for Postgres compatibility.
   - Validate Watchlists/Collections DB backends against Postgres and update tooling/documentation accordingly.

## 19. Rollout Plan

- **Phase 1 (complete):** Unified collections schema, ingestion bridge, reading capture/search UI, WebUI wiring for items/reading/watchlists.
- **Phase 2 (active):** Advanced outputs (MECE/TTS automation), delivery UX refinements, embeddings worker hardening, optional forums ingestion experiments.
- **Phase 3 (planned):** Reader enhancements (highlights/notes UX), third-party imports, WebSocket run streaming, Postgres enablement (Stage 2).

## 20. Risks & Mitigations

- Dynamic JS sites → mark unsupported initially; consider optional headless rendering later.
- Anti-scraping limits → robots compliance; per-host delays; backoff on 429; cap items per source.
- Content variability → per-source selectors with sane defaults; robust sanitization.
- Storage growth → retention policies for runs/logs/outputs; user-controlled cleanup.

## 21. Open Questions

- Email delivery: integrate SMTP now or defer to exports/webhooks? **Answer:** Implemented now via NotificationsService; document SMTP env vars (`EMAIL_PROVIDER`, host/port credentials) and add integration tests for real providers when available.
- Template editor: file-based to start vs in-UI editor. **Answer:** File-based (`WATCHLIST_TEMPLATE_DIR`) for now; plan UI-driven editor post-MECE/TTS.
- Provenance in RAG: how to present origin (reading vs watchlist) in citations by default? **Answer:** `/items` exposes `type` and tags; downstream RAG callers should include origin metadata in citation payloads. Future work: helper that maps origin to default citation format.

---
Implementation must follow project conventions: PEP 8, type hints, Loguru, Pydantic models, dependency injection, no raw SQL outside DB abstractions, and rate limiters on endpoints that trigger network/compute.
