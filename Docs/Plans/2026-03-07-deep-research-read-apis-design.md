# Deep Research Read APIs Design

## Overview

This slice adds polling-oriented read APIs for deep research runs and artifacts. The backend execution loop is already complete; this work makes the run state and generated outputs usable through first-class REST endpoints.

## Goals

- Expose run/session status through a dedicated read endpoint.
- Expose the final `bundle.json` through a dedicated bundle endpoint.
- Expose selected internal artifacts through an allowlisted artifact endpoint.
- Keep the API REST-only and polling-oriented for v1.

## Non-Goals

- No SSE or websocket progress streaming.
- No generic file browser over research storage.
- No mutation endpoints beyond the existing checkpoint approval flow.
- No artifact pagination or search.

## Architecture

Extend `ResearchService` with read helpers:

- `get_session(...)`
- `get_bundle(...)`
- `get_artifact(...)`

Artifact reads should be allowlisted, not arbitrary-path based. The service should resolve the latest manifest entry for a given artifact name and return normalized content:

- JSON artifacts -> parsed objects
- JSONL artifacts -> list of parsed objects
- text/markdown artifacts -> string

Extend `tldw_Server_API/app/api/v1/endpoints/research_runs.py` with:

- `GET /api/v1/research/runs/{id}`
- `GET /api/v1/research/runs/{id}/bundle`
- `GET /api/v1/research/runs/{id}/artifacts/{name}`

## Artifact Allowlist

V1 artifact reads should support:

- `plan.json`
- `approved_plan.json`
- `source_registry.json`
- `evidence_notes.jsonl`
- `collection_summary.json`
- `outline_v1.json`
- `claims.json`
- `report_v1.md`
- `synthesis_summary.json`
- `bundle.json`

Unsupported names return `400`.

## API Contracts

### `GET /runs/{id}`

Returns the session state:

```json
{
  "id": "rs_123",
  "status": "completed",
  "phase": "completed",
  "active_job_id": null,
  "latest_checkpoint_id": "cp_123",
  "completed_at": "2026-03-07T00:00:00+00:00"
}
```

### `GET /runs/{id}/bundle`

Returns the parsed final bundle from `bundle.json`.

- `404` if the run or bundle is missing

### `GET /runs/{id}/artifacts/{name}`

Returns:

```json
{
  "artifact_name": "report_v1.md",
  "content_type": "text/markdown",
  "content": "# Research Report\n..."
}
```

For JSONL artifacts, `content` is a list of parsed objects.

## Error Handling

- missing run -> `404`
- missing bundle -> `404`
- missing allowlisted artifact -> `404`
- disallowed artifact name -> `400`

## Testing

Add or extend:

- service tests for reading sessions, bundles, and allowlisted artifacts
- endpoint tests for the new GET routes
- e2e test for fetching run status, the final bundle, and one intermediate artifact after completion

## Follow-On Work

After the polling APIs land, the next likely step is live progress transport:

- SSE or Jobs event passthrough
- richer progress fields on run status
- artifact manifest listing if clients need discovery
