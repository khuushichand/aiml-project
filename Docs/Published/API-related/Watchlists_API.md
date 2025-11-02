# Watchlists API

This page documents the Watchlists endpoints relevant to sources, jobs, runs, items, and outputs, and highlights the bulk JSON create flow with per-entry status.

## Endpoints (selected)

- `POST /api/v1/watchlists/sources` - create a source
- `GET /api/v1/watchlists/sources` - list sources (filters: `q`, `tag`, `type`, ...)
- `GET /api/v1/watchlists/sources/{id}` - get a source
- `PATCH /api/v1/watchlists/sources/{id}` - update a source
- `DELETE /api/v1/watchlists/sources/{id}` - delete a source
- `POST /api/v1/watchlists/sources/bulk` - bulk JSON create (per-entry status)
- `POST /api/v1/watchlists/sources/import` - OPML import (multipart)
- `GET  /api/v1/watchlists/sources/export` - OPML export

- `GET  /api/v1/watchlists/runs` - list runs globally (filters: `q`, pagination)
- `GET  /api/v1/watchlists/runs/{id}/details` - run details with optional filter tallies
 - `POST /api/v1/watchlists/jobs/{id}/preview` - preview candidates and filter decisions without ingestion

Jobs and outputs endpoints are available in the server OpenAPI and are covered in the product docs.

## Bulk JSON Create (Sources)

`POST /api/v1/watchlists/sources/bulk`

- Request body: `{ "sources": SourceCreateRequest[] }`
- Response body:
  - `items[]`: `{ name, url, id?, status: "created"|"error", error?, source_type? }`
  - `total`, `created`, `errors`
- Validation:
  - When `source_type="rss"` and the URL is a YouTube link, only canonical RSS feeds are accepted:
    - `https://www.youtube.com/feeds/videos.xml?channel_id=...`
    - `https://www.youtube.com/feeds/videos.xml?playlist_id=...`
    - `https://www.youtube.com/feeds/videos.xml?user=...`
  - Non-feed YouTube URLs (e.g., `/watch`, `/shorts`, `@handle`) are rejected with `invalid_youtube_rss_url`.
  - Tags must be non-empty/non-whitespace strings; invalid tags are rejected per-entry with `invalid_tag_names: [..]`.

Example request:
```
{
  "sources": [
    {"name":"YT Bad","url":"https://youtu.be/abc","source_type":"rss"},
    {"name":"YT Good","url":"https://www.youtube.com/feeds/videos.xml?channel_id=UC...","source_type":"rss"},
    {"name":"Site A","url":"https://a.example.com/","source_type":"site"}
  ]
}
```

Example response:
```
{
  "items": [
    {"name":"YT Bad","url":"https://youtu.be/abc","status":"error","error":"invalid_youtube_rss_url","source_type":"rss"},
    {"name":"YT Good","url":"https://www.youtube.com/feeds/videos.xml?channel_id=UC...","id":201,"status":"created","source_type":"rss"},
    {"name":"Site A","url":"https://a.example.com/","id":202,"status":"created","source_type":"site"}
  ],
  "total": 3,
  "created": 2,
  "errors": 1
}
```

For OPML import/export and filters, see the server’s OpenAPI and the product docs under Watchlists. Also see Docs/Operations/Watchlists_Migration_Notes.md for a short migration guide (Subscriptions → Watchlists).

## OPML Import/Export

Endpoints:

- `POST /api/v1/watchlists/sources/import` - multipart with fields:
  - `file`: OPML file
  - `active` (bool, default true): mark created sources active
  - `tags` (list[str], optional): tag names applied to each created source
  - `group_id` (int, optional): group to attach each created source to
  - Response: `{ items[], total, created, skipped, errors }` with per-entry `status: created|skipped|error` and `error` message when applicable.

- `GET /api/v1/watchlists/sources/export` - returns OPML for RSS sources. Optional filters: `tag`, `group`, `type`.

Examples

- Import nested outlines with defaults:
```
multipart form
  file = (feeds.opml)
  active = 1
  tags = ["news","tech"]
  group_id = 12
```

- Export by group OR and tag AND:
```
GET /api/v1/watchlists/sources/export?group=10&group=11&tag=keep
```
Returns sources in group 10 or 11 that also have the tag "keep".

- Example OPML (simplified):
```
<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <head>
    <title>Watchlists Export</title>
  </head>
  <body>
    <outline text="Tech" title="Tech">
      <outline text="Feed A" title="Feed A" type="rss" xmlUrl="https://example.com/a.xml" htmlUrl="https://example.com/" />
      <outline text="Feed B" title="Feed B" type="rss" xmlUrl="https://example.com/b.xml" />
    </outline>
    <outline text="News" title="News">
      <outline text="Feed C" title="Feed C" type="rss" xmlUrl="https://example.com/c.xml" />
    </outline>
  </body>
  </opml>
```

- Export all RSS sources tagged with "keep" (case-insensitive):
```
GET /api/v1/watchlists/sources/export?tag=keep&type=rss
```

Behavior and edge cases:
- Nested outlines are supported; importer walks the tree and processes `<outline xmlUrl="...">` entries.
- `htmlUrl` is preserved on export when available; import accepts entries without `htmlUrl` (ignored if missing).
- Duplicates by URL are idempotent; creation errors are returned per-entry.
- Invalid or unsupported outlines yield `status: error` with an actionable message without aborting the whole import.
- Tag filters are case-insensitive on export (e.g., `keep`, `Keep`, `KEEP` are equivalent).

## YouTube as RSS

When `source_type = "rss"` and a URL points to YouTube, the server attempts to normalize common forms to canonical feed URLs and exposes headers when this happens:

- Canonical feeds accepted or produced via normalization:
  - `https://www.youtube.com/feeds/videos.xml?channel_id=...`
  - `https://www.youtube.com/feeds/videos.xml?playlist_id=...`
  - `https://www.youtube.com/feeds/videos.xml?user=...`

- On successful normalization, responses include headers:
  - `X-YouTube-Normalized: 1`
  - `X-YouTube-Canonical-URL: <canonical-feed-url>`

- Unsupported forms are rejected with `400 invalid_youtube_rss_url` (e.g., `/watch`, `/shorts`, some `@handle` or `/c/...` vanity URLs that cannot be normalized server-side).

Tip: The WebUI normalizes many common YouTube URLs before submitting to the server.

Note: Bulk create does not emit per-entry normalization headers; normalization occurs per item and canonical URLs are returned in the response items.

## Runs

### Global runs list

`GET /api/v1/watchlists/runs`

- Query params:
  - `q` (optional): search by job name/description/status
  - `page` (default 1), `size` (default 50; max 200)
- Response: `{ items: Run[], total: number, has_more?: boolean }`

### Run details and tallies

`GET /api/v1/watchlists/runs/{id}/details`

- Query params:
  - `include_tallies` (bool, default false): include `filter_tallies` map
  - `filtered_sample_max` (int, default 5, max 50): include up to N filtered items for quick triage
- Response always contains flattened totals: `filters_include`, `filters_exclude`, `filters_flag`.
- When `include_tallies=true`, response also includes `filter_tallies` keyed by rule id/index.
- The response may include `filtered_sample` when `filtered_sample_max > 0`.
 - Header: `X-Watchlists-Filter-Debug-Max` reflects the server-side debug cap (env `WATCHLISTS_FILTER_DEBUG_MAX`).

### CSV exports

- Runs export (global/by job):
```
GET /api/v1/watchlists/runs/export.csv?scope=global&q=Alpha&page=1&size=200&include_tallies=false
GET /api/v1/watchlists/runs/export.csv?scope=job&job_id=123&page=1&size=200&include_tallies=true
```
Columns: `id,job_id,status,started_at,finished_at,items_found,items_ingested,filters_include,filters_exclude,filters_flag`.
Headers: server includes `X-Has-More: true|false` to mirror pagination parity.

When `include_tallies=true`, an additional column is appended:
- `filter_tallies_json` - JSON map of per-filter tallies for that run (keys are filter identifiers; values are counts).

- Per-run tallies export:
```
GET /api/v1/watchlists/runs/{run_id}/tallies.csv
```
Columns: `run_id,filter_key,count`

## History/Backfill

Watchlists can optionally fetch older pages of RSS/Atom feeds to build a fuller history.

- Strategy: `auto` (try Atom RFC5005, then WordPress), `atom`, `wordpress`, or `none`.
- Pagination budget: `max_pages` (includes the first page; e.g., 3 = first + 2 older pages).
- Per-page trimming: `per_page_limit` (optional; limit items per page during backfill).
- 304 behavior: `on_304` (when true, still attempt backfill when the first page returns 304 Not Modified).
- Boundary mode: `stop_on_seen` (when true, stop traversing when a fetched page has no items that are new relative to the source’s seen keys in the DB).

Per-source settings example (create/update):

```
{
  "settings": {
    "history": {
      "strategy": "auto",
      "max_pages": 5,
      "per_page_limit": 50,
      "on_304": true,
      "stop_on_seen": true
    },
    "rss": {
      "use_feed_content_if_available": true,
      "feed_content_min_chars": 600
    }
  }
}
```

Run stats include history counters when backfill is used:

```
"stats": {
  "items_found": 42,
  "items_ingested": 37,
  "history": {
    "pages_fetched": 4,
    "stop_on_seen_triggered": true
  }
}
```

Notes:
- Atom RFC5005: we follow `<link rel="prev-archive" href="…"/>` to discover older pages.
- WordPress feeds: we try common paged forms like `?paged=2` (heuristic and best-effort).
- Deduplication occurs across pages and against the source’s seen keys.
- To reduce network fetches for full text, prefer feed content via `settings.rss.use_feed_content_if_available` with a reasonable minimum length.

WebUI:
- The Watchlists Sources editor should expose a compact “History & RSS” advanced panel to edit these settings. Until the UI ships, you can PATCH a source with the `settings` structure above.

## Admin UI Notes

- Runs admin view: `/admin/watchlists-runs` (global/by-job browsing, search, pagination). When the dataset is large, prefer the server CSV export buttons in the UI.
- Items admin view: `/admin/watchlists-items` lists items for a specific run (supports `status` filter and pagination). The Runs table links to this view via “View items”.
- Role gating: the "Runs" navigation link can be gated by role via env flags. Set `NEXT_PUBLIC_ENABLE_RUNS_LINK=1` to enable the link and `NEXT_PUBLIC_RUNS_REQUIRE_ADMIN=true` to require an admin user. Admin detection checks `user.is_admin`, `user.role==='admin'`, or `user.roles` including `admin`. Adjust to match your auth user shape if needed.

Link: The WebUI pages are shipped with the server and can be reached from the header navigation when enabled.

## Job Filters and Include-Only Gating

Job filters attach to a job via `job_filters` or the dedicated endpoints:

- `PATCH /api/v1/watchlists/jobs/{id}/filters` (replace full set)
- `POST  /api/v1/watchlists/jobs/{id}/filters:add` (append)

Filter shape: `{ type: keyword|author|date_range|regex|all, action: include|exclude|flag, value, priority?, is_active? }`.

Regex flags: Only `i`, `m`, and `s` flags are supported.

Include-only gating (summary):
- When `require_include=true` on a job and any include rules exist, only include-matched items are ingested; others are marked as `filtered`.
- If unset, a default can be sourced from `organizations.metadata.watchlists.require_include_default` (or flat key `watchlists_require_include_default`), falling back to `WATCHLISTS_REQUIRE_INCLUDE_DEFAULT`.
- Per-run stats include `filters_matched`, `filters_actions` (include/exclude/flag counters), and `filter_tallies` keyed by rule id/index.

Quick behavior table:

| Setting source | Value | Include rules exist? | Behavior |
| --- | --- | --- | --- |
| Job `require_include` | true | yes | Only include-matched ingested; others `filtered` |
| Job `require_include` | false | yes/no | Standard include/exclude/flag semantics; non-matching still ingested unless excluded |
| Job `require_include` unset | org default / env | yes | Only include-matched ingested; others `filtered` |
| Job `require_include` unset | org default / env | no | Standard include/exclude/flag semantics |

Notes:
- Org default lives at `organizations.metadata.watchlists.require_include_default` (flat key `watchlists_require_include_default` also read for backward compatibility). Env fallback: `WATCHLISTS_REQUIRE_INCLUDE_DEFAULT`.
- Include-only gating applies only when at least one include rule exists.

Quick reference:
- Job flag: `job_filters.require_include = true|false`
- Org default: `organizations.metadata.watchlists.require_include_default`
- Env fallback: `WATCHLISTS_REQUIRE_INCLUDE_DEFAULT`

Behavior table:

| Include rules exist | Job flag | Org default | Effective gating |
|---------------------|----------|-------------|------------------|
| No                  | any      | any         | Off              |
| Yes                 | true     | any         | On               |
| Yes                 | false    | any         | Off              |
| Yes                 | unset    | true        | On               |
| Yes                 | unset    | false/unset | Off              |

Notes
- Gating applies only when include rules are present.
- The preview endpoint honors include-only gating to show which candidates would be filtered.

Reference: This behavior is also summarized in the bridge PRD. See Docs/Product/Watchlists_Subscriptions_Bridge_PRD.md.

## Deprecated: Subscriptions API

The legacy `/api/v1/subscriptions/*` API is deprecated. Requests to this prefix return `410 Gone` along with a `Link` header that points to the replacement Watchlists endpoint (for example, `/api/v1/watchlists/*`).

Migration:
- Subscription → Source (`/watchlists/sources`)
- SubscriptionChecks → Scrape Runs (`/watchlists/jobs/{id}/runs`, `/watchlists/runs/{run_id}`)
- ImportRules → Job Filters (`/watchlists/jobs/{id}/filters`)
### Preview candidates (dry-run)

`POST /api/v1/watchlists/jobs/{id}/preview`

- Query params:
  - `limit` (default 20): max candidates to return across all sources
  - `per_source` (default 10): max candidates per source
  - `include_content` (reserved; previews currently return summary only)
- Response: `{ items: PreviewItem[], total, ingestable, filtered }`
- PreviewItem fields: `source_id`, `source_type`, `url`, `title`, `summary`, `published_at`, `decision` (`ingest|filtered`), `matched_action` (`include|exclude|flag|None`), `matched_filter_key`, `flagged`.

Notes
- Include-only gating is honored: when active and include rules exist, items that don’t match an include rule are shown as `decision=filtered`.
- No DB writes or ingestion occur during preview.
