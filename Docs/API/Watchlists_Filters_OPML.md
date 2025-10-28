# Watchlists Filters and OPML

This page documents the Watchlists filter schema, endpoints, and OPML import/export usage.

## Filter Schema

Filters are configured per job as `job_filters` with the following structure:

- `require_include` (bool, optional): When true and any `include` rules exist, only include-matched items are ingested; others are recorded as `filtered`.
- `filters` (array): Ordered by descending `priority`, short-circuiting on first match.
  - `type` (keyword|author|date_range|regex|all)
  - `action` (include|exclude|flag)
  - `value` (object) — per-type shape:
    - keyword: `{ keywords: ["ai", "ml"], match: "any|all", fields?: ["title","summary","content","author"] }`
    - author: `{ names: ["john"], match: "any|all" }`
    - regex: `{ pattern: "(?i)breaking", flags?: "ims", field?: "title|summary|content|author" }`
    - date_range: `{ max_age_days: 7 }`
    - all: `{}`
  - `priority` (int, optional; default 0)
  - `is_active` (bool; default true)

Actions:
- `exclude`: record item as `filtered`, do not ingest
- `flag`: ingest and add `flagged` tag to stored content
- `include`: marks a match; when `require_include` is true, only include-matched items ingest

## API Endpoints

- Replace job filters
  - `PATCH /api/v1/watchlists/jobs/{job_id}/filters`
  - Body: `{ require_include?: boolean, filters: [...] }`

- Append job filters
  - `POST /api/v1/watchlists/jobs/{job_id}/filters:add`
  - Body: `{ filters: [...] }`

Rate limits (test-aware):
- `PATCH/POST jobs/*/filters`: 30/minute per client
- `POST /watchlists/sources/import`: 10/minute per client

Run details include:
- `items_found`, `items_ingested`
- When filters are used: `filters_matched`, `filters_include`, `filters_exclude`, `filters_flag`

## OPML Import/Export

- `POST /api/v1/watchlists/sources/import` — multipart upload, supports defaults:
  - form fields: `active` (bool), `tags[]` (multi-value), `group_id` (int)
  - returns per-entry results and totals

- `GET /api/v1/watchlists/sources/export` — returns OPML for current RSS sources; optional query:
  - `type=rss` (default), `tag=...` (multi), etc.

Examples are available via the tests under `tldw_Server_API/tests/Watchlists/`.

