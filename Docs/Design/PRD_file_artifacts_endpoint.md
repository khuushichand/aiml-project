# PRD: Structured File Artifacts API

## Overview
Introduce a backend capability to create structured file artifacts through a single API endpoint, with strict validation and optional server-side export. The endpoint accepts a `file_type` with a file-type-specific payload, validates it, persists the structured artifact, and optionally generates a server-validated export (ICS/MD/HTML/XLSX/CSV/JSON). Async exports are durable Jobs (core Jobs module) and tracked via job_id; exported binaries are transient and expire quickly. Inline exports are capped (configurable). This unifies file creation across multiple formats behind one interface and supports future file types via adapters.

## Goals
- Provide a single endpoint to create structured files across multiple formats.
- Validate and persist artifacts before export is available to clients.
- Support initial file types: iCal, Markdown tables, HTML tables, XLSX, CSV tables, JSON tables.
- Enable server-side export with URL or inline return when requested.
- Use the core Jobs module for durable async exports with metrics/tracking.
- Keep generated binaries transient; no long-lived server-side storage.

## Non-Goals
- Full UI integration or frontend workflows.
- Arbitrary file uploads or raw binary creation.
- Rich iCal recurrence validation beyond initial structural checks.
- Long-lived storage or listing/querying of generated file artifacts.
- Re-exporting artifacts in multiple formats (one export per artifact).

## Target Users
- API clients and UI services that need a unified way to generate structured files.
- Internal services producing structured artifacts for export and download.

## Core Requirements
1. `POST /api/v1/files/create` accepts `file_type`, `payload`, optional `export`, and persists the artifact.
2. Validation failures return hard errors (HTTP 422), and no artifact is persisted.
3. Successful requests return structured representation plus export metadata.
4. Exports can be synchronous (small) or asynchronous (large); async returns 202 and a durable `job_id`.
5. Exported binaries are transient (stored briefly under a per-user temp outputs area) and served via a download endpoint.
6. Exports are one-time per artifact; additional export attempts return an error (409).

## API Contract

### Create Artifact
`POST /api/v1/files/create`

Request:
```json
{
  "file_type": "ical | markdown_table | html_table | xlsx | data_table",
  "title": "optional display name",
  "payload": { "file_type_specific": "..." },
  "export": {
    "format": "ics | md | html | xlsx | csv | json",
    "mode": "url | inline",
    "async_mode": "auto | sync | async"
  },
  "options": {
    "max_bytes": 10485760,
    "max_rows": 5000,
    "max_cells": 200000,
    "export_ttl_seconds": 900
  }
}
```

Response:
```json
{
  "artifact": {
    "file_id": 123,
    "file_type": "data_table",
    "title": "Scores",
    "structured": { "...": "..." },
    "validation": { "ok": true, "warnings": [] },
    "export": {
      "status": "ready | pending | none",
      "format": "csv",
      "url": "https://.../api/v1/files/123/export?format=csv",
      "content_type": "text/csv",
      "bytes": 1203,
      "job_id": "optional",
      "content_b64": "optional",
      "expires_at": "optional"
    },
    "created_at": "2026-01-01T12:00:00Z",
    "updated_at": "2026-01-01T12:00:00Z"
  }
}
```

### Export Artifact
`GET /api/v1/files/{file_id}/export?format=ics|md|html|xlsx|csv|json`
- Returns a binary file response with safe `Content-Type` and `Content-Disposition`.
- Returns 404 if the artifact or export file is unavailable/expired.
- Returns 409 if the export was already consumed (one-time download).
- Successful downloads may delete the transient file immediately (one-time download).

## Structured Representations

### iCal (file_type=ical)
Payload:
```json
{
  "calendar": {
    "prodid": "-//tldw//files//EN",
    "version": "2.0",
    "events": [
      {
        "uid": "event-1",
        "summary": "Title",
        "start": "2026-01-01T10:00:00Z",
        "end": "2026-01-01T11:00:00Z",
        "description": "optional",
        "location": "optional",
        "timezone": "optional"
      }
    ]
  }
}
```

### Markdown/HTML Tables (file_type=markdown_table, html_table)
Payload:
```json
{
  "columns": ["Name", "Score"],
  "rows": [
    ["Alice", 95],
    ["Bob", 88]
  ]
}
```

### XLSX (file_type=xlsx)
Payload:
```json
{
  "sheets": [
    {
      "name": "Sheet1",
      "columns": ["Name", "Score"],
      "rows": [["Alice", 95]]
    }
  ]
}
```

### Data Table (file_type=data_table)
Payload:
```json
{
  "columns": ["Name", "Score"],
  "rows": [
    ["Alice", 95],
    ["Bob", 88]
  ]
}
```
Notes:
- Payload schema matches Markdown/HTML tables; export format controls CSV vs JSON vs XLSX output.

## Validation Rules
- Hard errors (422) for:
  - Missing required fields.
  - Empty columns or empty sheets.
  - Row length mismatch.
  - Invalid date-time strings for iCal events.
  - Unsupported export format.
- Rows may be empty (valid empty table/sheet).
- Warnings (non-blocking) are allowed but should be rare initially.

## Export Behavior
- If `export` is provided:
  - `sync`: attempt immediate export (may still offload heavy work).
  - `async`: always enqueue a durable Job and return 202 with job_id.
  - `auto`: enqueue a Job when data exceeds configured thresholds.
- Async jobs use the core Jobs module (domain `files`, queue `default`, job_type `file_artifact_export`).
- Client polling: `GET /api/v1/files/{file_id}` returns updated export status + job_id.
- Exports are stored transiently (per-user temp outputs path) and expire via TTL.
- `mode=inline` returns base64 content for small exports; otherwise returns a URL.
- Inline exports are capped (default 256KB). Configure via `config.txt` `[Files] inline_max_bytes` or `FILES_INLINE_MAX_BYTES`.

## Operations
- Async exports require a Jobs worker to complete:
  - In-process worker: set `FILES_JOBS_WORKER_ENABLED=true` on the API server.
  - External worker: run `python -m tldw_Server_API.app.core.File_Artifacts.jobs_worker`.
- If no worker is running, async jobs remain pending until a worker starts.

## Limits and Security
- Enforce max rows/cells/bytes thresholds.
- Sanitize spreadsheet cells to mitigate formula injection (`=`, `+`, `-`, `@`).
- HTML output is escaped; Markdown tables escape pipes/newlines.
- Ensure output filenames are safe and restricted to the user temp outputs directory.
- `options.persist` is required and must be true (requests with `persist=false` are rejected).

## Persistence
- Use the per-user Media DB via `CollectionsDatabase`.
- Add a new `file_artifacts` table to store structured payloads and export metadata.
- Store `structured_json` and `validation_json` as TEXT (JSON-encoded) for both SQLite and PostgreSQL.
- Do not retain exported binaries long-term; cleanup on download or TTL expiry.

## Observability
- Log validation failures and export errors with request IDs.
- Emit metrics for create/export success/failure; Jobs metrics should reflect queued/processing/completed exports.
  - `file_artifacts_operations_total{operation, status, file_type, export_format, reason}` (counter).

## Rollout
- Ship endpoint with initial file types.
- Add richer validation libraries as follow-up (e.g., full RFC 5545 validation).
- Expand file type adapters over time.
