Release Notes
=============

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
