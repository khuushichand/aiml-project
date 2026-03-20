# Meetings Developer Guide

This guide is for contributors maintaining and extending Meeting Intelligence (`/api/v1/meetings/*`).

## Module Overview

Primary code roots:

1. Endpoints: `tldw_Server_API/app/api/v1/endpoints/meetings.py`
2. Schemas: `tldw_Server_API/app/api/v1/schemas/meetings_schemas.py`
3. DB access: `tldw_Server_API/app/core/DB_Management/Meetings_DB.py`
4. Domain services:
   - `tldw_Server_API/app/core/Meetings/session_service.py`
   - `tldw_Server_API/app/core/Meetings/template_service.py`
   - `tldw_Server_API/app/core/Meetings/artifact_service.py`
   - `tldw_Server_API/app/core/Meetings/events_service.py`
   - `tldw_Server_API/app/core/Meetings/integration_service.py`
5. WS/HTTP deps:
   - `tldw_Server_API/app/api/v1/API_Deps/Meetings_DB_Deps.py`
6. Retry worker:
   - `tldw_Server_API/app/services/meetings_webhook_dlq_service.py`

## Request Path and Dependencies

### HTTP routes

Meetings HTTP handlers are defined as sync `def` handlers and include:

1. `Depends(get_meetings_db_for_user)` for per-user DB scope.
2. `Depends(check_rate_limit)` for ingress rate limiting.

`list_templates` validates `scope` at the schema layer using `MeetingTemplateScope`.

### WebSocket route

`/sessions/{session_id}/stream` uses `get_meetings_db_for_websocket`, which:

1. Extracts auth from:
   - `Authorization: Bearer ...`
   - `X-API-KEY`
   - `sec-websocket-protocol` bearer format
   - query `token` / `api_key`
2. Builds a request-like object and delegates to `get_request_user`.
3. Initializes per-user `MeetingsDatabase`.

## Data Model

Core tables in `Meetings_DB`:

1. `meeting_sessions`
2. `meeting_templates`
3. `meeting_artifacts`
4. `meeting_integration_dispatch`
5. `meeting_event_log`

`meeting_artifacts`, `meeting_integration_dispatch`, and `meeting_event_log` enforce:

```sql
FOREIGN KEY(session_id) REFERENCES meeting_sessions(id) ON DELETE CASCADE
```

Migration logic in `_run_schema_migrations` rebuilds older dispatch/event tables if cascade FKs are missing.

## Event Semantics

`MeetingEventsService.emit(...)` writes to `meeting_event_log`, then returns a normalized envelope.

WebSocket persistence behavior:

1. `transcript.partial` (and interim aliases): emitted to client only, not persisted.
2. `transcript.final` (or payloads marked `final`/`is_final`): persisted.
3. Unknown `transcript.*` variants except partial are treated as persistent transcript events.

This keeps event-log growth bounded during long live sessions while preserving stable checkpoints.

## Sharing and DLQ Worker

Share endpoints enqueue dispatch rows via `MeetingIntegrationService.queue_dispatch(...)`.

`run_meetings_webhook_dlq_worker`:

1. Discovers per-user media DB targets.
2. Reuses `MeetingsDatabase` instances across loop iterations (cached by `(db_path, user_id)`).
3. Claims due dispatches with `claim_due_integration_dispatches`.
4. Applies egress policy and backoff retry rules.
5. Emits `integration.retrying`, `integration.delivered`, or `integration.failed` events.

Control variables:

1. `MEETINGS_WEBHOOK_DLQ_ENABLED`
2. `MEETINGS_WEBHOOK_DLQ_INTERVAL_SEC`
3. `MEETINGS_WEBHOOK_DLQ_BATCH`
4. `MEETINGS_WEBHOOK_DLQ_TIMEOUT_SEC`
5. `MEETINGS_WEBHOOK_DLQ_MAX_ATTEMPTS`
6. `MEETINGS_WEBHOOK_DLQ_BASE_SEC`
7. `MEETINGS_WEBHOOK_DLQ_MAX_BACKOFF_SEC`

## Extension Patterns

### Add a new artifact type

1. Update `MeetingArtifactKind` literal in schemas.
2. Add DB validation support in `_ARTIFACT_KINDS`.
3. Extend `MeetingArtifactService._build_finalize_payloads`.
4. Add unit + API tests.

### Add a new integration target

1. Extend `MeetingIntegrationType` literal.
2. Add queue-time validation in `integration_service`.
3. Extend worker dispatch routing logic.
4. Add integration API + worker tests.

### Add new WS event types

1. Decide transient vs persistent semantics.
2. Update `_resolve_ws_event_persistence` mapping.
3. Add WS tests asserting event log behavior.

## Testing

Meetings tests live under `tldw_Server_API/tests/Meetings`.

Targeted suite:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_db.py \
  tldw_Server_API/tests/Meetings/test_meetings_artifact_service.py \
  tldw_Server_API/tests/Meetings/test_meetings_sessions_api.py \
  tldw_Server_API/tests/Meetings/test_meetings_templates_api.py \
  tldw_Server_API/tests/Meetings/test_meetings_stream_ws.py \
  tldw_Server_API/tests/Meetings/test_meetings_events_sse.py \
  tldw_Server_API/tests/Meetings/test_meetings_integrations_api.py \
  tldw_Server_API/tests/Meetings/test_meetings_ingest_finalize_api.py \
  tldw_Server_API/tests/Meetings/test_meetings_webhook_dlq_worker.py
```

Note: full suite runs can still hit environment-specific heavy import crashes in `test_meetings_routes_smoke` depending on local ML/native library state.

## Documentation Cross-References

1. Product PRD: `Docs/Product/Meeting-Transcripts-PRD.md`
2. API contract/design: `Docs/Design/Meeting_Intelligence_API.md`
