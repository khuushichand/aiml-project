# Data Tables API

Data Tables provide LLM-generated tables stored in the Media DB with async jobs, versioned metadata, and export support.

Base path: `/api/v1/data-tables`

## Endpoints

- `POST /generate` - submit a generation job (optionally wait for completion)
- `GET /` - list tables
- `GET /{table_uuid}` - table detail (columns/rows/sources)
- `GET /{table_uuid}/export` - export as CSV/JSON/XLSX
- `PUT /{table_uuid}/content` - replace columns + rows
- `PATCH /{table_uuid}` - update name/description
- `DELETE /{table_uuid}` - soft delete
- `POST /{table_uuid}/regenerate` - regenerate from stored sources
- `GET /jobs/{job_id}` - job status
- `DELETE /jobs/{job_id}` - cancel job

## Core Object: DataTableSummary

Key fields:
- `uuid`, `name`, `description`, `workspace_tag`
- `prompt`, `column_hints`
- `status`: `queued|running|ready|failed|cancelled`
- `row_count`, `column_count`, `source_count`
- `generation_model`, `last_error`
- `created_at`, `updated_at`, `last_modified`, `version`

## Generate

`POST /api/v1/data-tables/generate`

Query params:
- `wait_for_completion` (bool, default false)
- `wait_timeout_seconds` (1..1800)

Request:
```
{
  "name": "Vendors",
  "prompt": "Extract vendors with price and license",
  "sources": [
    {
      "source_type": "rag_query",
      "source_id": "vendors-2026-01",
      "title": "Vendor notes",
      "snapshot": {"query": "vendor pricing", "chunks": []}
    }
  ],
  "column_hints": [
    {"name": "Vendor", "type": "text"},
    {"name": "Price", "type": "currency"},
    {"name": "License", "type": "text"}
  ],
  "model": "gpt-4o",
  "max_rows": 200
}
```

Response (202):
```
{
  "job_id": 42,
  "job_uuid": "...",
  "status": "queued",
  "table": {"uuid": "...", "name": "Vendors", "status": "queued"}
}
```

Request validation note:
- `max_rows` in the request body is validated to `1..DATA_TABLES_MAX_ROWS` (default `2000`).

## List

`GET /api/v1/data-tables`

Filters: `status`, `search`, `workspace_tag`, `limit`, `offset`.

## Detail

`GET /api/v1/data-tables/{table_uuid}`

Query params:
- `include_rows` (default true)
- `include_sources` (default true)
- `rows_limit` (1..2000)
- `rows_offset`

## Export

`GET /api/v1/data-tables/{table_uuid}/export`

Query params:
- `format`: `csv|json|xlsx`
- `async_mode`: `auto|sync|async`
- `mode`: `url|inline`
- `download`: `true` to return the file directly

Exports may be routed through File Artifacts when `mode=url` or `async_mode` is used.

## Update Content

`PUT /api/v1/data-tables/{table_uuid}/content`

Replaces columns and rows.

Request (simplified):
```
{
  "columns": [
    {"name": "Vendor", "type": "text"},
    {"name": "Price", "type": "currency"}
  ],
  "rows": [
    {"row_id": "row-1", "data": {"Vendor": "Acme", "Price": 99}}
  ]
}
```

## Update Metadata

`PATCH /api/v1/data-tables/{table_uuid}` with `name` and/or `description`.

## Jobs

- `GET /api/v1/data-tables/jobs/{job_id}` - status
- `DELETE /api/v1/data-tables/jobs/{job_id}` - cancel
- Generate/regenerate jobs are enqueued on `DATA_TABLES_JOBS_QUEUE` (default `default`).
- `wait_for_completion=true` treats `completed`, `failed`, `cancelled`, and `quarantined` as terminal job states.

## Notes

- External identifiers are `uuid`; internal numeric IDs are DB-only.
- Regenerate pulls stored sources and can override `prompt`, `model`, or `max_rows`.
- Exports may be async; poll job status when `status=pending`.
