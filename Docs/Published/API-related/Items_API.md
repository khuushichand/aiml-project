# Items API

Items provide a unified, read-friendly list across Collections content items (reading list, watchlists, feeds) with a fallback to legacy Media DB rows when no collection items exist.

Base path: `/api/v1/items`

## Endpoints

- `GET /` - list items (filters, paging)
- `GET /{item_id}` - get an item by id
- `POST /bulk` - bulk update items (status, favorite, tags, delete)

## List Items

`GET /api/v1/items`

Query params:
- `ids`: repeated item ids to include
- `q`: full-text search (title/content)
- `tags`: require tags (repeated)
- `domain`: hostname filter
- `date_from`, `date_to`: ISO-8601 range (inclusive)
- `status_filter`: repeated values (example: `saved`, `read`, `archived`)
- `favorite`: boolean
- `origin`: filter by origin (watchlist, reading, feed, etc.)
- `job_id`, `run_id`: filter by ingest job/run
- `page`: default 1
- `size`: default 20, max 200

Response: `ItemsListResponse`

Example response:
```
{
  "items": [
    {
      "id": 42,
      "content_item_id": 911,
      "media_id": 42,
      "title": "Example article",
      "url": "https://example.com/post",
      "domain": "example.com",
      "summary": "Short summary...",
      "published_at": "2025-01-01T12:00:00Z",
      "tags": ["ai", "reading"],
      "type": "reading"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20
}
```

## Get Item

`GET /api/v1/items/{item_id}`

Response: `Item`

## Bulk Update Items

`POST /api/v1/items/bulk`

Request: `ItemsBulkRequest`

Actions:
- `set_status`: requires `status`
- `set_favorite`: requires `favorite`
- `add_tags`: requires `tags`
- `remove_tags`: requires `tags`
- `replace_tags`: requires `tags`
- `delete`: soft delete by default; set `hard=true` for permanent delete

Example request:
```
{
  "item_ids": [42, 43],
  "action": "add_tags",
  "tags": ["review", "ml"]
}
```

Example response:
```
{
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {"item_id": 42, "success": true, "error": null},
    {"item_id": 43, "success": true, "error": null}
  ]
}
```

## Core Objects

### Item

```
{
  "id": 42,
  "content_item_id": 911,
  "media_id": 42,
  "title": "Example article",
  "url": "https://example.com/post",
  "domain": "example.com",
  "summary": "Short summary...",
  "published_at": "2025-01-01T12:00:00Z",
  "tags": ["ai", "reading"],
  "type": "reading"
}
```

### ItemsBulkRequest

```
{
  "item_ids": [42],
  "action": "set_status",
  "status": "read",
  "favorite": false,
  "tags": ["tag"],
  "hard": false
}
```
