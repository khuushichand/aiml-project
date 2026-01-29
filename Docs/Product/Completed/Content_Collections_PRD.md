 # PRD: Content Collections (Watchlists + Reading List) for tldw_server

Version: 0.2
Owner: Core Maintainers (Server/API + WebUI)
Status: In Progress
Updated: 2026-01-12

Related: Project_Guidelines.md, AGENTS.md, tldw_Server_API/app/main.py, Docs/Product/Content_Collections_UX_Backlog_PRD.md, Docs/Product/Watchlists-UX-PRD.md

---

## 1. Summary

Content Collections unify two complementary workflows:
- **Watchlists**: Source-centric scheduled collection from websites/news sites/RSS with jobs, runs, aggregated outputs, template-driven rendering, versioning, retention/TTL, and delivery (email + Chatbook). *Status: implemented; WebUI admin flows now consume the new APIs; run WebSocket streaming and forum gating shipped.*
- **Reading List**: Ad-hoc link capture with a clean reader UI, statuses (saved/reading/read/archived), favorites, notes, highlights, import/export. *Status: capture/status/favorite/notes flows and basic WebUI shipped; Pocket/Instapaper import/export API shipped; highlights + import/export UX tracked in Content_Collections_UX_Backlog_PRD.*

Both flows will share a normalized collections layer stored inside the per-user Media DB (`Media_DB_v2.db`). Media DB remains the canonical artifact store and the central DB for `content_items`, templates, and highlights, while the collections layer (via `CollectionsDatabase`) provides dedupe, metadata, and search connectivity across Watchlists and Reading. Outputs can be generated from scheduled runs or filtered item sets, exported as Chatbooks, delivered via email, or linked back into Media DB.

## 2. Goals and Non-Goals

### Goals (MVP → v1)
- [x] Unified content item model and shared ingestion/dedupe/search/embeddings.
- [x] Reading capture: save URL → readable text; statuses/tags/favorites/notes; search; basic WebUI. *(Highlights UI and import/export UX tracked in Content_Collections_UX_Backlog_PRD.)*
- [x] Watchlists: manage sources, groups/tags; jobs with schedule; runs with logs/stats; RSS + simple sites (front page + top-N).
- [x] Outputs: Markdown briefing/newsletter; MECE and TTS audio variants; export/ingest.
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
- Ad-hoc link capture and reader UI with statuses/favorites/notes (implemented; highlights UI pending; import/export API shipped; UX tracked in Content_Collections_UX_Backlog_PRD).
- Unified collections data layer that references Media DB while enabling dedupe and metadata across origins (implemented).
- RSS polling; simple site extraction (front page + top-N). Forums are feature-flagged with throttling (implemented; disabled by default).
- Canonical URL/content-hash dedupe and change detection (implemented).
- Outputs in Markdown/HTML plus MECE/TTS variants; Chatbook delivery; optional Media DB ingestion (implemented).
- FTS5 search and ChromaDB embeddings per user over collections data (implemented).

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
- Import Pocket/Instapaper into items; export JSONL/zip.
- Highlights/notes in reader view.

## 7. UX Flows (High-Level)

- Items: Unified list with filters (origin, tags, status, domain, date); search; bulk select for outputs via `/api/v1/outputs` using selected `item_ids`.
- Reader: Distraction-free item detail with actions (Tag, Favorite, Mark Read, Summarize, Listen). Highlights/notes (v1).
- Watchlists: Sources (CRUD, tags/groups); Jobs (scope, schedule, options); Runs (logs/stats); Outputs.
- Reading: Quick save; tags/status/favorites; import/export UX tracked in Content_Collections_UX_Backlog_PRD.

## 8. Functional Requirements

### 8.1 Unified Content Items
- Single table for items from any origin (reading/manual/import/watchlist).
- Fields: url, canonical_url, domain, title, summary, notes, content_hash, word_count, published_at, status, favorite, read_at, metadata_json.
- Metadata: author, clean_html, text, reading_time_seconds, language, embedding_* fields, media_uuid, and other ingestion context are stored in `metadata_json`.
- Relations: source_id?, job_id?, run_id?, media_id?; tags many-to-many; highlights (v1).
- Dedupe: canonical URL and/or content_hash on stripped main content; tag behavior depends on `merge_tags` (reading save/import uses `merge_tags=true`). When tags are omitted, existing tags are preserved; with `merge_tags=true` tags are unioned; otherwise provided tags replace the prior set.
- Status: **Complete** - `CollectionsDatabase` provides `content_items`, tag joins, FTS hooks, and watchlists dual-write; `/api/v1/items` now queries this layer before falling back to legacy Media DB search.

### 8.2 Ingestion & Parsing
- URL validation; safe fetch (timeouts, size caps, content-type checks); follow redirects.
- RSS: parse items; track guid/link/pubDate; dedupe by canonical link+hash.
- Sites: index fetch; extract article links (CSS selector or defaults); cap top-N per source.
- Forums: gated behind feature flag with throttling; disabled by default.
- Readability-style article extraction; sanitize HTML; derive plain text.
- Metadata extraction: title, author (if present), publish date, canonical link; compute domain.

### 8.3 Organization
- Tags: normalized strings; suggest recent; many-to-many with items and sources; backed by a `collection_tags` table and join tables that reference `tag_id` (no free-text tag joins).
- Groups: hierarchical or flat; sources ↔ groups; items inherit source context for filtering.

### 8.4 Scheduling & Runs (Watchlists)
- Scheduler: APScheduler (AsyncIOScheduler) with SQLAlchemyJobStore for persistence across restarts.
- Timezone: all schedule expressions are interpreted and stored with timezone `UTC`.
- Jobs: scope (sources/groups/tags), schedule (interval/cron), active flag, per-host delay, max concurrency, retry policy.
- Runs: status (queued/running/success/partial/failed), stats (new/updated/ignored/errors), logs, started/finished times.
- Runs: WebSocket streaming for status/log tail (implemented).
- HTTP caching: ETag/Last-Modified; send If-Modified-Since/If-None-Match when supported.

### 8.5 Search & RAG
- FTS5 virtual table over title/summary/metadata (text is stored in metadata_json); filters by tags/status/origin/domain/date/job/run.
- Embeddings in ChromaDB with namespace per user; expose items via existing RAG endpoints (opt-in by user preference).
- Re-embedding policy: when an item’s normalized text changes (content_hash diff), upsert vectors for that item and remove the old vector; record `embedding_model`, `embedding_model_version`, and `embedding_ts` in metadata. Background job supports full re-index when the configured embedding model/version changes.
- Status: **Complete** - FTS5 writes are active for collections, and both reading saves and watchlist ingestion enqueue embeddings via `EMBEDDINGS_REDIS_URL`/`REDIS_URL` backed worker queues (best-effort when Redis unavailable). Regression tests cover queueing and offline behavior.

### 8.6 Outputs & Delivery
- Output types: newsletter_markdown, briefing_markdown, mece_markdown, newsletter_html (v1), tts_audio (v1).
- Inputs: item_ids, run_id, or inline data payload; templating with variables (job, date, items, tags).
- Templates: managed via API (CRUD) with DB-backed storage and preview via `/api/v1/outputs/templates`. Watchlists outputs resolve DB templates by name; legacy file-based watchlists templates live under `tldw_Server_API/Config_Files/templates/watchlists` (override via `WATCHLIST_TEMPLATE_DIR`) and are supported as fallback.
- Delivery: download file; optional Media DB ingest, email (SMTP provider via `NotificationsService`), Chatbook document generation.
- Retention: global defaults via `WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS` / `WATCHLIST_OUTPUT_TEMP_TTL_SECONDS`, per-job overrides under `output_prefs.retention`, per-output overrides during generation.
- Status: **Complete** - API + retention/versioning + email/Chatbook delivery and WebUI controls shipped; MECE/TTS automation and Media DB ingest toggles included.

### 8.7 Reading Features
- Status transitions (saved → reading → read/archived); favorites; per-item notes (basic); highlights (v1). *(Notes shipped; highlights UI pending; import/export API shipped; UX tracked in Content_Collections_UX_Backlog_PRD.)*
- Highlights anchoring: store `quote` and anchor via fuzzy text matching with `content_hash_ref`; offsets are advisory. On text change, attempt re-anchor; if failing, mark highlight `stale` while preserving original context.
- Import: Pocket/Instapaper (JSON/CSV) to items with tag merging; Export: JSONL or zip bundle. Status: **Complete (API)**; UX tracked in Content_Collections_UX_Backlog_PRD.

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

Persist in per-user `<USER_DB_BASE_DIR>/<user_id>/Media_DB_v2.db` via DB abstractions.

`USER_DB_BASE_DIR` is defined in `tldw_Server_API.app.core.config` (defaults to `Databases/user_databases/` under the project root). Override via environment variable or `Config_Files/config.txt` as needed.

Entities
- content_items
  - id, user_id, origin[`reading`|`watchlist`|`import`|`manual`], url, canonical_url, domain, title,
    summary, notes, content_hash, word_count, published_at, status, favorite, metadata_json,
    media_id (nullable), source_id (nullable), job_id (nullable), run_id (nullable), read_at,
    created_at, updated_at
  - metadata_json includes author, clean_html, text, reading_time_seconds, language, embedding_* fields, media_uuid, and other ingestion context.
- content_item_tags (join)
  - item_id, tag_id
- reading_highlights (v1)
  - id, item_id, quote, start_offset, end_offset, color, note, created_at,
    anchor_strategy[`fuzzy_quote`|`exact_offset`], content_hash_ref, context_before (nullable), context_after (nullable), state[`active`|`stale`]
- sources
  - id, user_id, name, url, source_type[`rss`|`site`|`forum`], active, settings_json,
    last_scraped_at, etag, last_modified, status, created_at, updated_at
- groups, source_groups (join)
  - groups: id, user_id, name, description, parent_group_id (nullable)
  - source_groups: source_id, group_id
- collection_tags, source_tags (join)
  - collection_tags: id, user_id, name
  - source_tags: source_id, tag_id
- scrape_jobs
  - id, user_id, name, description, scope_json (sources|groups|tags), schedule_expr,
    active, max_concurrency, per_host_delay_ms, retry_policy_json,
    output_prefs_json, schedule_timezone[`UTC`], created_at, updated_at, last_run_at, next_run_at
- scrape_runs
  - id, job_id, status, started_at, finished_at, stats_json, error_msg, log_path
- outputs
  - id, user_id, job_id (nullable), run_id (nullable), type, title, format[`md`|`html`|`mp3`],
    storage_path, metadata_json, created_at, media_item_id (nullable), chatbook_path (nullable)

Indexes
- content_items: canonical_url, content_hash, created_at; FTS5 (title, summary, metadata)
- collection_tags: UNIQUE(user_id, name)
- content_item_tags: (item_id), (tag_id)
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
- `GET /reading/items` → list, filters: q, tags, status, favorite, domain, date_from, date_to
- `GET /reading/items/{id}` → full item
- `PATCH /reading/items/{id}` → update title/tags/status/favorite/notes
- `DELETE /reading/items/{id}` → soft delete; `?hard=true`
- `POST /reading/items/bulk` → alias for `/items/bulk` bulk updates
- `POST /reading/import` → Pocket/Instapaper; returns summary (imported/updated/skipped/errors)
- `GET /reading/export` → JSONL/zip
- `POST /reading/items/{id}/highlight` (v1)
- `GET /reading/items/{id}/highlights` (v1)
- `PATCH /reading/highlights/{id}` (v1)
- `DELETE /reading/highlights/{id}` (v1)

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
- `GET /items` → unified list (origin, tags, status, domain, date_from/date_to, job_id, run_id)
- `GET /items/{id}` → item regardless of origin
- `POST /items/bulk` → bulk update items (status, favorite, tags, delete)

Tags Semantics (API)
- Endpoints that accept `tags` expect a list of tag names (strings).
- Server normalizes names (lowercase, trimmed), ensures existence in the per-user `collection_tags` table (creating missing tags), and resolves to `tag_id`s for joins.
- Responses include tag names only; tag IDs are not exposed by current APIs.
- Watchlists tag assignment endpoints accept names and follow the same normalization and resolution behavior.

Bulk Items (API)
- Actions: `set_status`, `set_favorite`, `add_tags`, `remove_tags`, `replace_tags`, `delete`.
- Soft delete sets `status=archived`; hard delete removes the row.
- Returns per-item success/error with aggregate counts.
- Output generation is not a bulk action; UI should call `POST /api/v1/outputs` with `template_id` + `item_ids`.

Example: add tags
```json
{
  "item_ids": [101, 102, 103],
  "action": "add_tags",
  "tags": ["research", "priority"]
}
```

Example: mark read
```json
{
  "item_ids": [101, 102],
  "action": "set_status",
  "status": "read"
}
```

Example: archive (soft delete)
```json
{
  "item_ids": [101],
  "action": "delete"
}
```

Example: hard delete
```json
{
  "item_ids": [101],
  "action": "delete",
  "hard": true
}
```

Example response
```json
{
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    {"item_id": 101, "success": true},
    {"item_id": 102, "success": false, "error": "item_not_found"},
    {"item_id": 103, "success": true}
  ]
}
```

Outputs
- `POST /outputs` → from item_ids or run_id (inline data optional); body includes template_id/options and optional MECE/TTS toggles
- `GET /outputs/{id}` | `GET /outputs/{id}/download`

Templates (Outputs)
- `GET /outputs/templates` | `POST /outputs/templates` | `GET /outputs/templates/{id}` | `PATCH /outputs/templates/{id}` | `DELETE /outputs/templates/{id}`
- `POST /outputs/templates/{id}/preview` → render with sample or provided item ids without persisting

Schemas
- Pydantic under `tldw_Server_API/app/api/v1/schemas/items_schemas.py`, `watchlists_schemas.py`, `reading_schemas.py`, `reading_highlights_schemas.py`, `outputs_schemas.py`, and `outputs_templates_schemas.py`.

## 12. System Design & Components

Modules
- Core: `tldw_Server_API/app/core/Collections/`
  - `reading_service.py` (capture/update/list/delete)
  - `reading_importers.py` (Pocket/Instapaper parsing)
  - `embedding_queue.py` (enqueue embeddings jobs)
  - `utils.py` (hashing, truncation helpers)
- Core (Watchlists): `tldw_Server_API/app/core/Watchlists/` (pipeline, fetchers, scheduler, template store)
- API: `tldw_Server_API/app/api/v1/endpoints/reading.py`, `reading_highlights.py`, `watchlists.py`, `items.py`, `outputs.py`, `outputs_templates.py`
- Services: `tldw_Server_API/app/services/outputs_service.py`, `outputs_purge_scheduler.py`
- WebUI (Next.js): `apps/tldw-frontend/pages/items.tsx`, `apps/tldw-frontend/pages/reading.tsx`, `apps/tldw-frontend/pages/watchlists.tsx`, `apps/tldw-frontend/pages/admin/watchlists-items.tsx`, `apps/tldw-frontend/pages/admin/watchlists-runs.tsx`.

Key Flows
- Fetch with per-host delay; use ETag/Last-Modified; safe timeouts/size limits.
- Parse via existing ingestion pipelines; sanitize and produce text.
- Dedupe normalize URL + SHA256 of main text.
- Persist item and update FTS5; enqueue embeddings; optionally enqueue summary.
- Outputs render markdown/html; optional TTS via `/api/v1/audio/speech`; export/ingest artifacts.

Scheduling
- APScheduler (AsyncIOScheduler) with SQLAlchemyJobStore persists schedules across restarts; timezone for all schedules is `UTC`. Bounded worker pool; global per-host throttles shared across jobs.

## 13. Configuration

- Defaults in `tldw_Server_API/Config_Files/config.txt` (collections/watchlists section):
  - `WATCHLIST_MAX_CONCURRENCY`, `WATCHLIST_PER_HOST_DELAY_MS`, `WATCHLIST_MAX_ITEMS_PER_SOURCE`, `WATCHLIST_OBEY_ROBOTS=true`
  - `ITEM_FETCH_TIMEOUT_MS`, `ITEM_MAX_DOWNLOAD_MB`
- Templates are DB-managed via `/api/v1/outputs/templates`. Legacy watchlists templates remain file-based under `tldw_Server_API/Config_Files/templates/watchlists/` for fallback/compatibility.
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

- Scheduler persistence/timezone: time-freezing tests verifying APScheduler with SQLAlchemyJobStore persists jobs across restarts and interprets cron/interval triggers using timezone `UTC`. Validate `next_run_at` computation and on-restart rehydration.

## 18. Implementation Roadmap (Media DB remains separate)

1. **Unified Collections Layer** - *shipped*
   - `content_items` + tag joins live in `Media_DB_v2.db` (central DB) via `CollectionsDatabase`.
   - Watchlist ingestion dual-writes; `/api/v1/items` resolves from collections before falling back to legacy search.

2. **Reading Workflow** - *MVP shipped; highlights UI pending; import/export API shipped*
   - URL capture (save), status/favorite/tags/notes, reader endpoints, and WebUI page delivered.
   - Highlights UI and import/export UX remain TODO; tracked in Content_Collections_UX_Backlog_PRD.

3. **Search & Retrieval Enhancements** - *shipped*
   - FTS5 online updates for collections; embeddings queueing via Redis job manager; provenance filters exposed on `/items`.
   - End-to-end embeddings worker validation pending full worker stack smoke tests.

4. **Outputs & Delivery Expansion** - *complete*
   - Markdown/HTML generation, retention TTLs, NotificationsService delivery, MECE/TTS automation, Media DB ingest toggles, and output templates wired into WebUI.

5. **WebUI & Admin UX** - *shipped (core)*
   - Next.js pages for Items, Reading, and Watchlists consume the new APIs; job output preferences editable (template, retention, email/chatbook deliveries).
   - Remaining UX work tracked in Content_Collections_UX_Backlog_PRD: reader highlights UI, template editor, bulk output generation (via `/api/v1/outputs`), Pocket/Instapaper import/export UX.

6. **Stage 2 - Postgres Enablement** - *complete*
   - Collections/Watchlists schema creation and inserts validated against Postgres; integration smoke tests added.

## 19. Rollout Plan

- **Phase 1 (complete):** Unified collections schema, ingestion bridge, reading capture/search UI, WebUI wiring for items/reading/watchlists.
- **Phase 2 (complete):** Advanced outputs (MECE/TTS automation + ingest toggles), delivery UX refinements, embeddings worker hardening, forum gating.
- **Phase 3 (planned):** Reader highlights/notes UX, template editor, bulk output generation, Pocket/Instapaper import/export UX (see Content_Collections_UX_Backlog_PRD).

## 20. Risks & Mitigations

- Dynamic JS sites → mark unsupported initially; consider optional headless rendering later.
- Anti-scraping limits → robots compliance; per-host delays; backoff on 429; cap items per source.
- Content variability → per-source selectors with sane defaults; robust sanitization.
- Storage growth → retention policies for runs/logs/outputs; user-controlled cleanup.

## 21. Open Questions

- Email delivery: integrate SMTP now or defer to exports/webhooks? **Answer:** Implemented now via NotificationsService; document SMTP env vars (`EMAIL_PROVIDER`, host/port credentials) and add integration tests for real providers when available.
- Template editor: file-based to start vs in-UI editor. **Answer:** DB-backed outputs templates are primary; legacy watchlists templates remain file-based fallback. UI editor work is tracked in Content_Collections_UX_Backlog_PRD.
- Provenance in RAG: how to present origin (reading vs watchlist) in citations by default? **Answer:** `/items` exposes `type` and tags; downstream RAG callers should include origin metadata in citation payloads. Future work: helper that maps origin to default citation format.

---
Implementation must follow project conventions: PEP 8, type hints, Loguru, Pydantic models, dependency injection, no raw SQL outside DB abstractions, and rate limiters on endpoints that trigger network/compute.
