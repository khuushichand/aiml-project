# Watchlists API

This page documents the Watchlists endpoints relevant to sources, jobs, runs, items, and outputs, and highlights the bulk JSON create flow with per-entry status.

## Endpoints (selected)

- `POST /api/v1/watchlists/sources` — create a source
- `GET /api/v1/watchlists/sources` — list sources (filters: `q`, `tag`, `type`, ...)
- `GET /api/v1/watchlists/sources/{id}` — get a source
- `PATCH /api/v1/watchlists/sources/{id}` — update a source
- `DELETE /api/v1/watchlists/sources/{id}` — delete a source
- `POST /api/v1/watchlists/sources/bulk` — bulk JSON create (per-entry status)
- `POST /api/v1/watchlists/sources/import` — OPML import (multipart)
- `GET  /api/v1/watchlists/sources/export` — OPML export

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

For OPML import/export and filters, see the server’s OpenAPI and the product docs under Watchlists.

