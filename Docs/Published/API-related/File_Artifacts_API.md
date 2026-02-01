# File Artifacts API

The File Artifacts API creates structured files (tables, calendars, images) with strict validation and optional server-side export.

Base path: `/api/v1/files`

## Endpoints

- `POST /create` - create a structured file artifact
- `GET /{file_id}` - fetch artifact metadata
- `GET /{file_id}/export?format=...` - download a one-time export
- `DELETE /{file_id}` - soft or hard delete
- `POST /purge` - purge expired or soft-deleted artifacts

## Create Artifact

`POST /api/v1/files/create`

Request:
```
{
  "file_type": "data_table",
  "title": "Scores",
  "payload": {
    "columns": ["Name", "Score"],
    "rows": [["Ada", 98], ["Grace", 96]]
  },
  "export": {
    "format": "csv",
    "mode": "url",
    "async_mode": "auto"
  },
  "options": {
    "persist": true,
    "max_bytes": 10485760,
    "max_rows": 5000,
    "max_cells": 200000,
    "export_ttl_seconds": 900
  }
}
```

Response:
```
{
  "artifact": {
    "file_id": 123,
    "file_type": "data_table",
    "title": "Scores",
    "structured": {"columns": ["Name", "Score"], "rows": [["Ada", 98]]},
    "validation": {"ok": true, "warnings": []},
    "export": {
      "status": "ready",
      "format": "csv",
      "url": "http://127.0.0.1:8000/api/v1/files/123/export?format=csv",
      "content_type": "text/csv",
      "bytes": 1203,
      "expires_at": "2026-01-29T12:00:00Z"
    }
  }
}
```

### File Types

Supported `file_type` values:
- `ical`
- `markdown_table`
- `html_table`
- `xlsx`
- `data_table`
- `image`

Supported export `format` values:
- `ics`, `md`, `html`, `xlsx`, `csv`, `json`, `png`, `jpg`, `webp`

## Export

`GET /api/v1/files/{file_id}/export?format=csv`

Notes:
- Exports are one-time downloads; a successful fetch marks the export as consumed.
- If the export is expired or already consumed, the endpoint returns 404/409.

## Delete

`DELETE /api/v1/files/{file_id}`

Query params:
- `hard` (default false)
- `delete_file` (default false; only applies to hard delete)

## Purge

`POST /api/v1/files/purge`

Request:
```
{
  "delete_files": true,
  "soft_deleted_grace_days": 30,
  "include_retention": true
}
```

## Notes

- `options.persist` must be true for current API versions.
- Large exports may return `status=pending` with a `job_id`.
- Inline exports are capped and returned as base64 (`export.content_b64`).
