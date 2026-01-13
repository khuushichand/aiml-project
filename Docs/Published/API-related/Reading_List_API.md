# Reading List API

Reading List endpoints support capture, extraction, organization, import/export, and actions (summarize/TTS).

## Endpoints (MVP)

- `POST /api/v1/reading/save` - save a URL (or inline content)
- `GET /api/v1/reading/items` - list items with filters/search
- `GET /api/v1/reading/items/{id}` - item detail with text/clean_html
- `PATCH /api/v1/reading/items/{id}` - update metadata (status/tags/notes/title)
- `DELETE /api/v1/reading/items/{id}` - soft delete (archived) or hard delete
- `POST /api/v1/reading/items/{id}/summarize` - summarize an item
- `POST /api/v1/reading/items/{id}/tts` - generate TTS audio for an item
- `POST /api/v1/reading/import` - Pocket/Instapaper import (multipart)
- `GET /api/v1/reading/export` - JSONL or ZIP export

## Core object: ReadingItem

Key fields:
- `id`, `url`, `canonical_url`, `title`
- `status`: `saved|reading|read|archived`
- `processing_status`: `processing|ready`
- `tags`, `favorite`
- `media_id` (link to Media DB when ingested)
- `created_at`, `updated_at`, `read_at`

## Save

`POST /api/v1/reading/save`

Request:
```
{
  "url": "https://example.com/article",
  "title": "Example Article",
  "tags": ["ai", "reading"],
  "notes": "Why it matters"
}
```

Response (ReadingItem):
```
{
  "id": 123,
  "title": "Example Article",
  "url": "https://example.com/article",
  "canonical_url": "https://example.com/article",
  "status": "saved",
  "processing_status": "processing",
  "favorite": false,
  "tags": ["ai", "reading"],
  "created_at": "2025-10-19T09:15:00Z",
  "updated_at": "2025-10-19T09:15:00Z"
}
```

Notes:
- Use `content` in the request body to supply inline text (offline/testing).
- Non-HTML URLs (PDF, EPUB, etc.) are routed into the document ingestion pipeline.

## List

`GET /api/v1/reading/items`

Filters: `q`, `tags`, `status`, `favorite`, `domain`, pagination (`page`/`size`), `offset`/`limit`, and `sort`.

Sort options: `updated_desc` (default), `updated_asc`, `created_desc`, `created_asc`, `title_asc`, `title_desc`, `relevance`.

Example:
```
GET /api/v1/reading/items?status=saved&tags=ai&favorite=true&q=vector&sort=updated_desc&limit=20&offset=0
```

Response:
```
{
  "items": [...],
  "total": 42,
  "page": 1,
  "size": 20,
  "offset": 0,
  "limit": 20
}
```

## Detail

`GET /api/v1/reading/items/{id}`

Response (ReadingItemDetail) includes:
- `text` (plain text)
- `clean_html` (sanitized HTML)
- `metadata` (extra fields like `reading_time_seconds`, `media_uuid`)

## Update

`PATCH /api/v1/reading/items/{id}`

Request:
```
{
  "status": "read",
  "favorite": true,
  "tags": ["ai", "priority"],
  "notes": "Follow up later"
}
```

Response: updated ReadingItem.

## Delete

`DELETE /api/v1/reading/items/{id}`

- Soft delete (default) marks the item as `archived`.
- Hard delete: `?hard=true`.

Response:
```
{ "status": "archived", "item_id": 123, "hard": false }
```

## Summarize

`POST /api/v1/reading/items/{id}/summarize`

Request:
```
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "prompt": "Summarize for a product brief."
}
```

Response:
```
{
  "item_id": 123,
  "summary": "Short summary text...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "citations": [
    {
      "item_id": 123,
      "url": "https://example.com/article",
      "canonical_url": "https://example.com/article",
      "title": "Example Article",
      "source": "reading"
    }
  ],
  "generated_at": "2025-10-19T09:20:00Z"
}
```

## TTS

`POST /api/v1/reading/items/{id}/tts`

Request:
```
{
  "model": "kokoro",
  "voice": "af_heart",
  "response_format": "mp3",
  "stream": true,
  "text_source": "text",
  "max_chars": 12000
}
```

Response:
- Streaming audio bytes (Content-Type based on `response_format`)
- Non-streaming mode returns raw bytes in the response body

## Import

`POST /api/v1/reading/import` (multipart)

Form fields:
- `file`: Pocket JSON or Instapaper CSV
- `source`: `auto|pocket|instapaper`
- `merge_tags`: `true|false`

Example:
```
multipart form
  file = (pocket.json)
  source = pocket
  merge_tags = true
```

## Export

`GET /api/v1/reading/export`

Query params:
- `format`: `jsonl` (default) or `zip`
- filters: `status`, `tags`, `favorite`, `q`, `domain`

JSONL line example:
```
{"id":123,"url":"https://example.com/article","canonical_url":"https://example.com/article","domain":"example.com","title":"Example Article","summary":"...","notes":null,"status":"saved","favorite":0,"tags":["ai"],"created_at":"2025-10-19T09:15:00Z","updated_at":"2025-10-19T09:15:00Z","read_at":null,"published_at":null,"origin_type":"manual","metadata":{"import_source":"pocket"}}
```
