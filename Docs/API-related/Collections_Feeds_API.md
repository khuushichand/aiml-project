# Collections Feeds API

Collections Feeds is a thin API over Watchlists sources and jobs that ingests RSS/Atom into Collections items. Each subscription is stored as a Watchlists source and polled by a Watchlists job. Items are written to the Collections DB with `origin="feed"`.

This API is ingest-only. It does not publish RSS/Atom or render UI. See `Docs/Design/Collections_Feeds_Ingestion.md` for the roadmap and `Reference implementation` below for newsletter-to-Atom details.

## Endpoints

- `POST /api/v1/collections/feeds` - create a feed subscription
- `GET /api/v1/collections/feeds` - list feed subscriptions
- `GET /api/v1/collections/feeds/{feed_id}` - get a feed subscription
- `PATCH /api/v1/collections/feeds/{feed_id}` - update a feed subscription
- `DELETE /api/v1/collections/feeds/{feed_id}` - delete a feed subscription

## Core object: CollectionsFeed

Key fields:
- `id`: watchlists source id
- `name`, `url`, `source_type` (`rss`)
- `origin`: always `feed`
- `tags`: list of tag strings
- `active`: source/job active flag
- `settings`: optional source settings (sanitized)
- `last_scraped_at`, `etag`, `last_modified`, `defer_until`, `status`, `consec_not_modified`: polling state
- `created_at`, `updated_at`: source timestamps
- `job_id`: watchlists job id
- `schedule_expr`, `timezone`, `job_active`, `next_run_at`, `wf_schedule_id`: job schedule and scheduler metadata

## Create

`POST /api/v1/collections/feeds`

Request:
```json
{
  "url": "https://example.com/feed.xml",
  "name": "Example Feed",
  "tags": ["news"],
  "active": true,
  "timezone": "UTC",
  "settings": {
    "history": {"strategy": "auto", "max_pages": 3}
  }
}
```

Response:
```json
{
  "id": 42,
  "name": "Example Feed",
  "url": "https://example.com/feed.xml",
  "source_type": "rss",
  "origin": "feed",
  "tags": ["news"],
  "active": true,
  "settings": {
    "history": {"strategy": "auto", "max_pages": 3}
  },
  "job_id": 101,
  "schedule_expr": "0 * * * *",
  "timezone": "UTC",
  "job_active": true,
  "next_run_at": "2025-01-01T01:00:00+00:00",
  "wf_schedule_id": "sched_abc123"
}
```

Notes:
- If `name` is omitted, it defaults to the URL hostname.
- If `schedule_expr` is omitted, the subscription defaults to hourly polling (`0 * * * *`) and auto-promotes to daily after 24 hours (see Scheduling).
- `timezone` accepts IANA names (e.g. `America/New_York`) or `UTC+/-` offsets.

## List

`GET /api/v1/collections/feeds`

Query params: `q`, `page` (default 1), `size` (default 20, max 200).

Response:
```json
{
  "items": [
    {
      "id": 42,
      "name": "Example Feed",
      "url": "https://example.com/feed.xml",
      "source_type": "rss",
      "origin": "feed",
      "tags": ["news"],
      "active": true,
      "settings": null,
      "job_id": 101,
      "schedule_expr": "0 * * * *",
      "timezone": "UTC",
      "job_active": true,
      "next_run_at": "2025-01-01T01:00:00+00:00",
      "wf_schedule_id": "sched_abc123"
    }
  ],
  "total": 1
}
```

## Get

`GET /api/v1/collections/feeds/{feed_id}`

Returns a `CollectionsFeed` object.

## Update

`PATCH /api/v1/collections/feeds/{feed_id}`

Request:
```json
{
  "name": "Example Feed (Daily)",
  "tags": ["news", "daily"],
  "schedule_expr": "0 0 * * *",
  "timezone": "UTC",
  "active": true,
  "settings": {
    "history": {"strategy": "none"}
  }
}
```

Response: updated `CollectionsFeed`.

Notes:
- When you set `schedule_expr` via PATCH, the job switches to manual scheduling and stops auto-promoting.
- `settings` is merged into existing settings; reserved keys are overwritten (see Settings).

## Delete

`DELETE /api/v1/collections/feeds/{feed_id}`

Response:
```json
{ "success": true }
```

## Scheduling behavior

Default behavior:
- If `schedule_expr` is omitted on create, the job starts hourly (`0 * * * *`).
- After 24 hours, the watchlists pipeline promotes the schedule to daily (`0 0 * * *`) and marks the job as promoted.

Manual behavior:
- If you set `schedule_expr` on create or update, the job is treated as manual and will not auto-promote.
- `timezone` is normalized to UTC when absent.

## Settings pass-through

`settings` is stored in the Watchlists source `settings_json` and is passed into the RSS fetchers.

Reserved keys are enforced by the server and will be removed or overwritten:
- `collections_origin`
- `collections_feed_job_id`, `collections_job_id`
- `collections.origin`, `collections.job_id`

For supported `settings` fields (history/backfill options, limits), see `Docs/Published/API-related/Watchlists_API.md` and `tldw_Server_API/app/core/Watchlists/fetchers.py`.

## Collections ingestion behavior

- RSS/Atom sources are fetched via the Watchlists pipeline (ETag/Last-Modified, RFC5005 history, dedupe by guid/url/title).
- Items are upserted into Collections with:
  - `origin = "feed"`
  - `origin_type = source_type`
  - `origin_id = source id`
- Embeddings metadata includes `origin` for traceability.

## Reference implementation: Kill the Newsletter (MIT)

The Kill the Newsletter script is a useful reference for email ingestion, Atom rendering, and UI flows. These features are not implemented in tldw_server yet, but can guide future work.

### Data model (SQLite)

Tables and key columns:
- `feeds`: `id`, `publicId`, `title`, `icon`, `emailIcon`
- `feedEntries`: `id`, `publicId`, `feed`, `createdAt`, `author`, `title`, `content`
- `feedEntryEnclosures`: `id`, `publicId`, `type`, `length`, `name`
- `feedEntryEnclosureLinks`: `feedEntry`, `feedEntryEnclosure`
- `feedVisualizations`: `feed`, `createdAt` (rate limiting)
- `feedWebSubSubscriptions`: `feed`, `createdAt`, `callback`, `secret`

### SMTP/email ingestion and attachments

- SMTP server with TLS, AUTH disabled, and a size limit (`2 ** 19`).
- Validates `mailFrom` and recipient addresses, blocks known relay domains.
- Parses email with mailparser; chooses HTML or text-as-HTML for content.
- Creates `feedEntryEnclosures` for attachments and writes files under `data/files/<publicId>/<name>`.
- Links enclosures to entries; feed rendering exposes them as Atom enclosures.
- Caps feed size by total title + content length (`2 ** 19`) and deletes oldest entries and links when exceeded.

### Atom feed rendering

- Feed id: `urn:kill-the-newsletter:<feed publicId>`.
- `self` link: `/feeds/<publicId>.xml`, `hub` link: `/feeds/<publicId>/websub`.
- Optional `<icon>` from `icon` or `emailIcon`.
- `updated` uses most recent entry `createdAt`.
- Entries include `link` to HTML entry view, `published`/`updated`, `author`, `title`, and `<content type="html">`.
- Enclosures are emitted as `<link rel="enclosure" type="..." length="..." href="...">`.
- Footer link in entry content points back to feed settings page.

### HTML entry views

- `/feeds/<feedPublicId>/entries/<entryPublicId>.html` returns raw HTML body.
- CSP: `default-src 'self'; img-src *; style-src 'self' 'unsafe-inline'; frame-src 'none'; object-src 'none'; form-action 'self'; frame-ancestors 'none'`.

### UI and settings pages

- Root page creates a feed, then shows the generated email address and Atom URL.
- Feed settings page includes copy-to-clipboard for email/feed URLs, update title/icon, and delete with title confirmation.
- Uses flash notifications, simple CSS layout, and form-based flows.

### WebSub push and rate limiting

- `POST /feeds/<publicId>/websub` validates callback URL, blocks localhost, and caps new callbacks per day.
- Background verification job calls the hub with `hub.challenge`.
- Dispatch job POSTs the Atom body to each callback, with `Link` headers and optional `X-Hub-Signature` HMAC.
- `feedVisualizations` limits XML feed requests to 10 per hour and is cleaned up hourly.

### Cleanup jobs

- Removes orphaned attachment files and DB rows.
- Deletes stale `feedVisualizations` (> 1 hour) and `feedWebSubSubscriptions` (> 24 hours).
