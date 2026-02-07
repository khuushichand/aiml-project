Release Notes
=============

2026-02-07

- Web scraping fallback hardening: responses now include `engine="legacy_fallback"` and `fallback_context` when enhanced scraping is unavailable.
- Legacy fallback now rejects unsupported advanced crawl controls with explicit `400` errors (instead of silently ignoring them), including `custom_headers`, unsupported `crawl_strategy`, `include_external=true`, and `score_threshold>0`.
- Predictable fallback degradation: `max_pages` is now enforced post-fetch for legacy `URL Level` and `Sitemap` runs.
- Added fallback-focused tests covering contract errors, fallback forcing, and smoke behavior for both `ephemeral` and `persist` modes.

2026-02-06

- Watchlists outputs: optional small-run TTS brief auto-generation now honors per-job `output_prefs` (`tts_brief`/`audio_brief`) and records metadata flags when auto mode is applied.
- Watchlists API: added per-source dedup/seen inspect/reset endpoints:
  - `GET /api/v1/watchlists/sources/{source_id}/seen`
  - `DELETE /api/v1/watchlists/sources/{source_id}/seen`
- Admin-capable user objects can inspect/reset dedup/seen state for another user via `target_user_id`; non-admin callers are rejected with `403 watchlists_admin_required_for_target_user`.
- Added focused Stage 5 reliability tests: scheduler controls roundtrip, dedup/seen tooling, and performance sanity for large filter sets.

2025-11-26

- ChaChaNotes schema v10 adds conversation metadata with an `in-progress` default/backfill plus topic and cluster labels.
- Notes now store backlinks via `conversation_id` and `message_id` with covering indexes; SQLite/Postgres migrations are included.
- Conversation title search applies global BM25 normalization so pagination returns stable ordering across the full result set.

2025-10-29

- Watchlists: OPML export supports group filters via `group` query parameter.
- Watchlists: RunDetail can include `filter_tallies` when `include_tallies=true`.
- Admin UI: Added a simple page to browse Watchlists runs and view filter counters/tallies (`/admin/watchlists-runs`).
- YouTube-as-RSS: Server now normalizes common YouTube URLs (channel, playlist, user) to canonical RSS feeds when creating/updating sources.
- Subscriptions API deprecation: `/api/v1/subscriptions/*` returns `410 Gone` with `Link` header to the corresponding `/api/v1/watchlists/*` endpoint.
- Admin UI: Runs page now supports CSV and JSON export of the current table view.
- Diagnostics: YouTube URL normalizations are logged at debug level with source and canonical URL.

Additions in this cycle
- CSV exports: `GET /api/v1/watchlists/runs/export.csv` supports `include_tallies=true` to append a `filter_tallies_json` column for each run.
- Preview (dry-run): `POST /api/v1/watchlists/jobs/{id}/preview` returns candidates and filter decisions without ingestion (honors include-only gating).
- Admin UI: Added Items view `/admin/watchlists-items` (paginate items for a run; link from Runs table). “Server CSV” export buttons now respect the “Include tallies” toggle.
- YouTube policy: Non-canonical forms like `@handle`, `/c/Vanity`, `/watch`, and `/shorts` return `400 invalid_youtube_rss_url`. Canonical normalization headers are set on accepted URLs (`X-YouTube-Normalized`, `X-YouTube-Canonical-URL`).
