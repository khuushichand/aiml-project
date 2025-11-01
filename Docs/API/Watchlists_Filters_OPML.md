# Watchlists Filters and OPML

This page documents the Watchlists filter schema, endpoints, and OPML import/export usage.

## Filter Schema

Filters are configured per job as `job_filters` with the following structure:

- `require_include` (bool, optional): When true and any `include` rules exist, only include-matched items are ingested; others are recorded as `filtered`.
- `filters` (array): Ordered by descending `priority`, short-circuiting on first match.
  - `type` (keyword|author|date_range|regex|all)
  - `action` (include|exclude|flag)
  - `value` (object) - per-type shape:
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

## Bulk JSON Create (Sources)

- `POST /api/v1/watchlists/sources/bulk` - create multiple sources in one request.
  - Request body: `{ sources: SourceCreateRequest[] }`
  - Response body:
    - `items[]`: `{ name, url, id?, status: "created"|"error", error?, source_type? }`
    - `total`, `created`, `errors`
  - Validation:
    - When `source_type="rss"` and the URL is a YouTube link, only canonical RSS feeds are accepted, e.g. `https://www.youtube.com/feeds/videos.xml?channel_id=...`.
    - Non-feed YouTube URLs are rejected with `invalid_youtube_rss_url`.
    - Tags must be non-empty, non-whitespace strings. Invalid tags are rejected per-entry with `invalid_tag_names: [..]`.

Example response with mixed valid/invalid entries:
```
{
  "items": [
    {"name":"YT Bad","url":"https://youtu.be/abc","status":"error","error":"invalid_youtube_rss_url: use canonical feed URLs; channel → https://www.youtube.com/feeds/videos.xml?channel_id=..., playlist → https://www.youtube.com/feeds/videos.xml?playlist_id=...","source_type":"rss"},
    {"name":"YT Good","url":"https://www.youtube.com/feeds/videos.xml?channel_id=UC...","id":201,"status":"created","source_type":"rss"},
    {"name":"Site A","url":"https://a.example.com/","id":202,"status":"created","source_type":"site"}
  ],
  "total": 3,
  "created": 2,
  "errors": 1
}
```

## OPML Import/Export

- `POST /api/v1/watchlists/sources/import` - multipart upload, supports defaults:
  - form fields: `active` (bool), `tags[]` (multi-value), `group_id` (int)
  - returns per-entry results and totals

- `GET /api/v1/watchlists/sources/export` - returns OPML for current RSS sources; optional query:
  - `type=rss` (default), `tag=...` (multi), etc.

Examples are available via the tests under `tldw_Server_API/tests/Watchlists/`.
