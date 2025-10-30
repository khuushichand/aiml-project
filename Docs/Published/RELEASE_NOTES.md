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
