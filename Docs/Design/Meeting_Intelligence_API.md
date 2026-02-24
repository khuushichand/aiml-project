# Meeting Intelligence API (v1)

Design metadata:
- `design_created`: 2026-02-23
- `moved_to_docs_design`: 2026-02-24
- `original_location`: `Docs/API-related/Meeting_Intelligence_API.md`

Meeting Intelligence v1 is exposed under ` /api/v1/meetings ` and provides:
- Meeting sessions, templates, and artifacts CRUD.
- Finalization from transcript text to summary/action artifacts.
- Live updates via SSE and WebSocket.
- Sharing to Slack incoming webhooks and generic webhooks.

## Auth

Use the same auth model as the rest of the API:
- Single-user: `X-API-KEY`
- Multi-user: `Authorization: Bearer <token>`

## Endpoints

Health:
- `GET /api/v1/meetings/health`

Sessions:
- `POST /api/v1/meetings/sessions`
- `GET /api/v1/meetings/sessions`
- `GET /api/v1/meetings/sessions/{session_id}`
- `POST /api/v1/meetings/sessions/{session_id}/status`

Templates:
- `POST /api/v1/meetings/templates`
- `GET /api/v1/meetings/templates`
- `GET /api/v1/meetings/templates/{template_id}`

Artifacts:
- `POST /api/v1/meetings/sessions/{session_id}/artifacts`
- `GET /api/v1/meetings/sessions/{session_id}/artifacts`
- `POST /api/v1/meetings/sessions/{session_id}/commit`

Sharing:
- `POST /api/v1/meetings/sessions/{session_id}/share/slack`
- `POST /api/v1/meetings/sessions/{session_id}/share/webhook`

Live transport:
- `GET /api/v1/meetings/sessions/{session_id}/events` (SSE)
- `WS /api/v1/meetings/sessions/{session_id}/stream`

## Key Request Models

Create session:
```json
{
  "title": "Weekly Product Sync",
  "meeting_type": "standup",
  "source_type": "upload",
  "language": "en"
}
```

Finalize/commit:
```json
{
  "transcript_text": "TODO: Alice updates API docs. DECISION: Ship in two phases.",
  "include": ["summary", "action_items", "decisions", "speaker_stats"]
}
```

Share (Slack/webhook):
```json
{
  "webhook_url": "https://hooks.example.test/meeting",
  "artifact_ids": ["art_123", "art_456"]
}
```

## Event Envelope

SSE and WS use the same event shape:
```json
{
  "id": "evt_...",
  "type": "artifact.ready",
  "session_id": "sess_...",
  "timestamp": "2026-02-23T00:00:00+00:00",
  "data": {}
}
```

Current event types:
- `session.created`
- `session.status`
- `artifact.ready`
- `transcript.partial`
- `transcript.final`
- `integration.queued`
- `integration.retrying`
- `integration.delivered`
- `integration.failed`
- `stream.complete`

## Sharing Worker and Retries

Queued dispatches are persisted in `meeting_integration_dispatch` and retried by:
- `tldw_Server_API/app/services/meetings_webhook_dlq_service.py`

Worker controls:
- `MEETINGS_WEBHOOK_DLQ_ENABLED` (default disabled)
- `MEETINGS_WEBHOOK_DLQ_INTERVAL_SEC`
- `MEETINGS_WEBHOOK_DLQ_BATCH`
- `MEETINGS_WEBHOOK_DLQ_TIMEOUT_SEC`
- `MEETINGS_WEBHOOK_DLQ_MAX_ATTEMPTS`
- `MEETINGS_WEBHOOK_DLQ_BASE_SEC`
- `MEETINGS_WEBHOOK_DLQ_MAX_BACKOFF_SEC`

The worker enforces egress policy before delivery and marks dispatch rows as `delivered`, `retrying`, or `failed`.

## Current v1 Limits

- Integrations are limited to Slack incoming webhooks and generic webhooks.
- No calendar ingestion or conferencing connectors in this version.
- Finalize artifacts are deterministic/basic (summary/action/decision/stats) and can be expanded in later phases.
