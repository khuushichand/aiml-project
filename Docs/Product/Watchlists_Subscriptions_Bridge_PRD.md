# Watchlists - Subscriptions Bridge PRD (v0.2)

Status: Near Complete (v1 wrap-up)
Owner: Core Maintainers (Server/API + WebUI)
Updated: 2025-10-29

Related:
- Docs/Product/Watchlist_PRD.md (primary PRD)
- Docs/Product/Content_Collections_PRD.md
- Docs/Operations/Watchlists_Migration_Notes.md (migration notes)
- SUBS/01_OVERVIEW.md, SUBS/02_ARCHITECTURE.md, SUBS/03_DATABASE_SCHEMA.md, SUBS/04_API_DESIGN.md, SUBS/05_IMPLEMENTATION_PHASES.md, SUBS/06_RSS_YOUTUBE_INTEGRATION.md, SUBS/07_BACKGROUND_TASKS.md, SUBS/08_UI_MOCKUPS.md

---

## 1) Purpose

Define a compatibility and evolution plan to consume the legacy “SUBS” (Subscriptions) documentation into the current Watchlists model and APIs without regressing shipped behavior. This bridge PRD clarifies naming, API, data model, scheduling, and feature mappings, and records the product decisions:
- YouTube modeled as RSS (channel feeds) under `source_type="rss"` for now.
- SUBS Import Rules carried forward as job-level filters.
- OPML import/export kept in scope for Watchlists sources.

## 2) Summary

Watchlists remains the primary concept, with sources, groups/tags, jobs (with schedules), runs, items, and outputs (templates, TTL, delivery). The SUBS docs are absorbed by:
- Treating “Subscriptions” as “Sources” in Watchlists.
- Replacing per-subscription checks with job-scoped scheduling and run history.
- Mapping SUBS Import Rules to job-level filters attached to `scrape_jobs`.
- Adding OPML import/export for Watchlists sources to ease migration and bulk setup.
- Modeling YouTube channels/playlists as RSS under `source_type=rss`, using canonical feed URLs.

Implementation status

- Done
  - Data model: `scrape_jobs.job_filters_json` added with idempotent backfill; CRUD helpers for job filters; JobRow extended.
  - Filters pipeline: include/exclude/flag rules evaluated pre-ingestion for RSS and site; filtered items recorded; per-run counters + per-filter tallies tracked.
  - API: filters in job payloads; `PATCH /watchlists/jobs/{id}/filters` and `POST /watchlists/jobs/{id}/filters:add`; OPML `POST /sources/import` and `GET /sources/export` (with `tag`, `type`, `group`).
  - Global runs: `GET /watchlists/runs` with pagination/search.
  - YouTube normalization: server accepts channel/user/playlist URLs and normalizes to canonical feeds; sets `X-YouTube-Normalized` and `X-YouTube-Canonical-URL` headers. Unsupported `@handle`, `/c/…`, `youtu.be`, `/watch` return 400.
  - Deprecation shim: `/api/v1/subscriptions/*` returns 410 Gone with Link to Watchlists.
  - Admin/org: include-only gating org-level default (and env fallback); admin endpoints to read/update; WebUI toggle + orgs list with pagination (API returns `total`/`has_more`).
- Admin runs UI: global and by-job modes; filter counters; tallies on demand; CSV/JSON export.
- Admin runs UI polish: added pagination in By Job mode and a “Download Tallies CSV” button when tallies are loaded.
- Admin items UI: `/admin/watchlists-items` lists items for a selected run with pagination and status filtering; linked from the Runs table (“View items”).
  - Rate limits: SlowAPI limits on OPML import and job filters endpoints (test-aware bypass).
  - Preview/dry-run: `POST /watchlists/jobs/{job_id}/preview` ships; respects include-only gating; returns decision per item; test-mode stubs for deterministic previews.
  - CSV exports (server-side): `GET /watchlists/runs/export.csv` (global or by job) and `GET /watchlists/runs/{run_id}/tallies.csv`.
  - Docs: API page updated (global runs endpoint, run-detail tallies toggle, OPML group filter, preview endpoint, CSV exports). Release notes added.
  - Migration notes: new page added (Docs/Operations/Watchlists_Migration_Notes.md) clarifying that no dedicated CLI is required; use OPML + filters. Linked from API/PRD.
  - DB hardening: schema migration guards added to avoid duplicate-column ALTER noise.

Cross-links
- Admin Items view: `/admin/watchlists-items` allows browsing items for a run with pagination and status filters; linked from Runs table.
- CSV endpoints: see Docs/Published/API-related/Watchlists_API.md for `GET /api/v1/watchlists/runs/export.csv` (supports `include_tallies` and returns `X-Has-More` header for pagination parity) and `GET /api/v1/watchlists/runs/{run_id}/tallies.csv`.

- In Progress
  - Docs polish (light): continue expanding OPML examples and include-only semantics quick table where helpful.
  - WebUI env: `NEXT_PUBLIC_RUNS_CSV_SERVER_THRESHOLD` controls when the UI prefers server CSV exports (default 2000 rows).
  - Optional preview endpoint tests: additional RSS+site preview scenarios and edge cases (regex errors, empty filters).

- Remaining (Phase B / nice-to-have)
  - Admin runs view polish: optional richer metrics columns; optionally integrate server CSV endpoints directly into the UI.
  - Optional: server-side YouTube resolver for `@handle`/vanity (policy remains 400; resolver out of scope for v1).

## 3) Goals and Non-Goals

### Goals
- Align terminology and API surfaces with Watchlists, deprecating SUBS naming.
- Implement OPML import/export for sources.
- Introduce job-level filters with behavior equivalent to SUBS Import Rules.
- Document YouTube-as-RSS handling with validated feed discovery and limits.
- Provide a clear data migration and compatibility plan.

### Non-Goals (initial)
- Re-introducing distinct `source_type` for YouTube/Podcasts (remain as RSS feeds for this phase).
- Headless browser automation or authenticated scraping.
- Multi-tenant sharing or public profiles.

## 4) Terminology Mapping (SUBS → Watchlists)

- Subscription → Source
- SubscriptionItems → Scraped Items (per run)
- SubscriptionChecks → Scrape Runs
- ImportRules → Job Filters
- Watchlist (SUBS “all new”) → Items API with filters (status=unreviewed/new)

## 5) Data Model (Additions/Adjustments)

Watchlists PRD tables remain the source of truth: `sources`, `groups`, `source_groups`, `tags`, `source_tags`, `scrape_jobs`, `scrape_runs`, `scrape_run_items`, `source_seen_items`, `scraped_items`, `watchlist_outputs`.

Additions:
- Job Filters (stored on `scrape_jobs` as JSON; optional dedicated table later):
  - Field: `scrape_jobs.job_filters_json` (nullable JSON)
  - Filter shape (compatible with SUBS Import Rules):
    - `id` (server-assigned), `type`[`keyword`|`author`|`date_range`|`regex`|`all`], `value` (object),
      `priority` (int), `action`[`include`|`exclude`|`flag`], `is_active` (bool), `stats` (optional).
- OPML seed fields (no schema change required; mapping occurs in import/export handlers).

Notes:
- Dedupe cache `source_seen_items` persists GUID/ETag/Last-Modified keys (from SUBS) keyed by `source_id`.
- Scheduling fields remain on `scrape_jobs` (`schedule_expr`, `schedule_timezone`, etc.). Default timezone behavior mirrors Watchlists (UTC+8 default at API level; stored as provided).

## 6) API Surface (Watchlists)

Base prefix remains: `/api/v1/watchlists`

### Sources (existing + OPML) - Implemented
- `POST /watchlists/sources` (create)
- `GET /watchlists/sources` (list; filters: `q`, `type`, `tag`, `group`, `active`)
- `GET /watchlists/sources/{id}` (get)
- `PATCH /watchlists/sources/{id}` (update)
- `DELETE /watchlists/sources/{id}` (delete)
- `POST /watchlists/sources/bulk` (bulk create; returns per-entry status with `created|error` and `error` message; strict backend validation for YouTube-as-RSS)
- `POST /watchlists/sources/import` (OPML multipart; fields: `file`, optional defaults: `active`, `tags`, `group_id`)
- `GET /watchlists/sources/export` (OPML; optional filters to scope export)

### Jobs (add filters) - Implemented
- `POST /watchlists/jobs` | `GET /watchlists/jobs` | `GET/PATCH/DELETE /watchlists/jobs/{id}`
- `PATCH /watchlists/jobs/{id}/filters` (replace full filter set)
- `POST /watchlists/jobs/{id}/filters:add` (append one or more filters)
- `POST /watchlists/jobs/{id}/run` (trigger now)
- `GET /watchlists/jobs/{id}/runs` | `GET /watchlists/runs/{run_id}` | `GET /watchlists/runs/{run_id}/log`

Filter JSON example:
```
{
  "filters": [
    {"type": "keyword", "value": {"keywords": ["ai", "ml"], "match": "any"}, "action": "include", "priority": 100, "is_active": true},
    {"type": "date_range", "value": {"max_age_days": 30}, "action": "include", "priority": 90, "is_active": true},
    {"type": "regex", "value": {"field": "title", "pattern": "(?i)breaking"}, "action": "exclude", "priority": 110, "is_active": true}
  ]
}
```

### Items, Runs, Outputs - Implemented/extended
- `GET /watchlists/items` (filters: `run_id`, `job_id`, `source_id`, `status`, `reviewed`, `q`, `since`, `until`)
- `PATCH /watchlists/items/{id}` (mark reviewed / update status)
- Outputs and Templates remain as in Watchlists PRD (TTL, versioning, delivery via NotificationsService).

## 7) YouTube as RSS (Phase Now)

Decision: Model YouTube channels/playlists as RSS under `source_type="rss"`.

Behavior:
- Users add canonical feed URLs (e.g., channel feed). Feed validation uses the existing RSS parser.
- Any YouTube-specific link forms are normalized client-side or by a helper (future) to canonical RSS feed URLs.
- Enclosures and media hints (video) are inferred by entry metadata and link patterns, consistent with the RSS parser.

### Canonical feed URL patterns (UI help + API docs)

- Channel (recommended): `https://www.youtube.com/feeds/videos.xml?channel_id=<CHANNEL_ID>`
- Playlist: `https://www.youtube.com/feeds/videos.xml?playlist_id=<PLAYLIST_ID>`
- Legacy user (if applicable): `https://www.youtube.com/feeds/videos.xml?user=<USERNAME>`

Notes:
- Channel IDs typically start with `UC…` and are visible on channel pages with `/channel/<CHANNEL_ID>`.
- Handle URLs (e.g., `https://www.youtube.com/@handle`) and vanity URLs (e.g., `/c/...`) are not canonical feeds. Users should resolve to the channel page and copy the `channel_id` form.

Optional client-side UX (recommended):
- When users paste a non-feed YouTube URL:
  - If it is a channel page (`/channel/<CHANNEL_ID>`) or playlist page (`?list=<PLAYLIST_ID>`), normalize it to the canonical feed URL automatically and confirm the change in the UI.
  - Otherwise, reject with an actionable error that shows the accepted patterns (above) and how to locate `channel_id`. The bulk JSON API surfaces this as per-entry `status:"error"` with `error:"invalid_youtube_rss_url"`.
  - This aligns with “optionally reject non-feed YouTube URLs with actionable error” (see this section).

## 8) OPML Import/Export

Scope: OPML outlines map to Watchlists sources and optionally groups/tags.

Import (`POST /watchlists/sources/import`):
- Accepts an OPML file; creates sources for `<outline>` entries with `xmlUrl` + `title`.
- Optional defaults in multipart: `active` (bool), `tags` (list of names), `group_id` (int).
- Returns summary counts and per-entry errors for invalid or unsupported outlines.

Details and edge cases:
- Nested outlines are supported; importer walks all children and handles duplicates idempotently.
- `htmlUrl` is retained on export and ignored if missing on import.
- Invalid OPML or outlines missing `xmlUrl` produce an error entry but do not abort the entire import.
  The response reports `created`, `skipped`, and `errors` totals for observability.

Export (`GET /watchlists/sources/export`):
- Returns OPML with `xmlUrl` and `htmlUrl` where available.
- Optional filters (`tag`, `group`, `type`) to scope the export. Group filter supports multiple ids (OR semantics) and can be combined with tag (AND semantics).
 - Unknown group ids result in an empty RSS list (HTTP 200 with an empty body list), avoiding partial matches by design.

Link: see Docs/Published/API-related/Watchlists_API.md for request/response examples and guidance.

Include-only gating reference

See the quick behavior table in Docs/Published/API-related/Watchlists_API.md (Job Filters and Include-Only Gating). The UI and preview endpoint follow the same semantics; org defaults can be changed via the admin setting.

## 9) Scheduling & Timezone Semantics

- Jobs own scheduling: `schedule_expr` (cron/interval) and `schedule_timezone` (string, stored as provided).
- Default behavior in API/UI normalizes “UTC+8” style inputs to valid timezone identifiers for scheduler.
- Background workers respect global concurrency caps and per-host delays defined in config and job fields.

## 10) Migration Plan (SUBS → Watchlists)

Mapping:
- `Subscriptions` → `sources` (name, url, active; map type→`rss`/`site`).
- `SubscriptionItems` → `scraped_items` (migrate only if needed; otherwise start fresh on runs).
- `SubscriptionChecks` → `scrape_runs` (optional historical import; not required for MVP).
- `ImportRules` → `scrape_jobs.job_filters_json` (consolidate into job filters; create 1 job per prior subscription if no jobs exist).

Process (Status: not required for prod)
1) Export all SUBS as OPML; import via `/watchlists/sources/import`.
2) For SUBS with Import Rules, create jobs targeting those sources and translate each rule into a job filter entry.
3) Disable/mark deprecated any `/api/v1/subscriptions/*` clients; point to `/api/v1/watchlists/*`.

Notes
- Subscriptions was never pushed to production; a dedicated migration CLI is not required. For bulk seeding, OPML import is sufficient.

Compatibility (optional):
- For a limited window, expose read-only redirects for `/api/v1/subscriptions/*` returning 410/Link headers to the new resources.

## 11) Error Handling & Rate Limits

- Use Watchlists error shape and limits. OPML import/export returns actionable per-entry errors.
- Filters endpoints validate filter schema and reject unknown `type`/`action`.
- Rate limits applied to OPML import and filters endpoints; test mode bypass documented.

## 12) Testing Strategy

- Unit: OPML parser; filter evaluation (keyword/date/regex); RSS-to-YouTube URL canonicalization; include-only org default logic.
- Integration: import OPML → list sources; create job with filters → run → items filtered; generate outputs with TTL and optional delivery; runs detail tallies.
- Property-based: filter ordering by priority; equivalent filter sets yield identical inclusion/exclusion decisions.
- Markers: `unit`, `integration` with network mocked; skip external RSS by default.

Implemented tests (selection)
- Filters matching and API CRUD: `tldw_Server_API/tests/Watchlists/test_filters_matching.py`, `test_filters_api.py`
- Pipeline filters e2e (exclude/flag, include-only): `test_watchlists_pipeline_filters.py`, `test_include_org_default.py`
- Runs detail counters + tallies toggle: `test_run_detail_filters_totals.py`
- OPML import/export (nested, edge cases, group filter): `test_opml_api.py`, `test_opml_nested.py`, `test_opml_edge_cases.py`, `test_opml_export_group.py`, `test_opml_export_group_more.py`
- YouTube normalization and policy tests: `test_youtube_url_validation.py`, `test_youtube_normalization_more.py`
- Admin org settings + search: `tests/Admin/test_admin_watchlists_org_settings.py`, `tests/Admin/test_admin_orgs_search.py`, `tests/Admin/test_admin_orgs_search_edge.py`
- Include-only gating (site) e2e: `test_site_include_only_gating.py`
- Rate-limit headers (deterministic, non-test mode): `test_rate_limit_headers_strict.py`

## 13) Rollout Plan

Phase A (this cycle):
- OPML import/export endpoints - Done.
- Job filters fields and endpoints; pipeline evaluation - Done.
- YouTube-as-RSS guidance in WebUI and API docs - Done (server normalization and docs updated).

Phase B (next):
- Redirects/deprecations for `/api/v1/subscriptions/*` - Done (410 shim) + docs.
- Optional: additional normalization helpers (policy kept as 400 for `@handle` and vanity URLs).
- Metrics/admin visibility - Partial (run counters + tallies and admin page shipped; deeper metrics/export polish remain).

## 14) Risks & Mitigations

- Inconsistent OPML forms → robust parsing + per-entry error details; ignore unsupported outlines.
- Over-aggressive filters → “dry-run preview” on jobs (planned) and filter stats per run.
- YouTube feed variability → document canonical URL patterns, fallback discovery, and limits.

## 15) Acceptance Criteria

- Users can import/export sources via OPML under `/api/v1/watchlists/sources/*`.
- Jobs support persistent filters; filters are applied during run item selection.
- YouTube sources work through RSS feeds; entries appear as expected and can be included in outputs.
- Existing Watchlists outputs (TTL, versioning, delivery) remain unaffected.

---
Implementation must follow project conventions (PEP 8, type hints, Loguru, Pydantic, DI, no raw SQL outside DB abstractions, and rate limiters on network/compute endpoints). Coordinate API schema updates with WebUI.
