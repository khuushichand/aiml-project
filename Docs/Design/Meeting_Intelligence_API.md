# Meeting Intelligence API (v1)

Design metadata:
- `design_created`: 2026-02-23
- `moved_to_docs_design`: 2026-02-24
- `original_location`: `Docs/API-related/Meeting_Intelligence_API.md`

Meeting Intelligence v1 is exposed under `/api/v1/meetings` and provides:
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

ID conventions:
- `id` uses `evt_<opaque-id>` and is globally unique + immutable.
- `session_id` uses `sess_<opaque-id>` and is globally unique + immutable.
- `artifact_ids[]` use `art_<opaque-id>` and are stable handles for persisted artifacts.
- Opaque IDs may be UUID-, ULID-, or snowflake-like tokens, but the prefixes above are required for validation and routing contracts.

## Sharing Worker and Retries

Queued dispatches are persisted in `meeting_integration_dispatch` and retried by:
- `tldw_Server_API/app/services/meetings_webhook_dlq_service.py`

Worker controls:
- `MEETINGS_WEBHOOK_DLQ_ENABLED` (`bool`, default: `false`)
- `MEETINGS_WEBHOOK_DLQ_INTERVAL_SEC` (`int` seconds, default: `15`)
- `MEETINGS_WEBHOOK_DLQ_BATCH` (`int` count, default: `25`)
- `MEETINGS_WEBHOOK_DLQ_TIMEOUT_SEC` (`float` seconds, default: `10`)
- `MEETINGS_WEBHOOK_DLQ_MAX_ATTEMPTS` (`int` count, default: `8`)
- `MEETINGS_WEBHOOK_DLQ_BASE_SEC` (`int` seconds, default: `30`)
- `MEETINGS_WEBHOOK_DLQ_MAX_BACKOFF_SEC` (`int` seconds, default: `3600`)

Webhook delivery security requirements:
- Validate and normalize submitted URLs before any network call: hostname must be present, hostname is normalized (IDNA/lowercase/trailing-dot handling), and invalid ports are rejected.
- Enforce allowed schemes for webhook dispatches (`https` required for production targets) and disallow protocol downgrade across retries/redirect paths.
- Block private/local destinations by policy (`RFC1918`, loopback/localhost, link-local, multicast, reserved ranges, and IPv6 equivalents) prior to send.
- Apply DNS rebinding protection by resolving hostnames and re-evaluating resolved IPs on each retry attempt; if resolution fails or returns blocked ranges, mark dispatch as policy-denied.
- Do not auto-follow redirects for webhook dispatches (`follow_redirects=False` in the shared HTTP client path); if redirect handling is introduced later, cap redirect count and re-run egress checks on each hop.
- Enforce bounded connection/read timeouts via `MEETINGS_WEBHOOK_DLQ_TIMEOUT_SEC` and bounded retry/backoff via `MEETINGS_WEBHOOK_DLQ_MAX_ATTEMPTS`, `MEETINGS_WEBHOOK_DLQ_BASE_SEC`, and `MEETINGS_WEBHOOK_DLQ_MAX_BACKOFF_SEC`.
- Log and metricize policy denials, retries, deliveries, and terminal failures so operators can audit delivery decisions.

The worker marks dispatch rows as `delivered`, `retrying`, or `failed` after each attempt.

## Current v1 Limits

- Integrations are limited to Slack incoming webhooks and generic webhooks.
- No calendar ingestion or conferencing connectors in this version.
- Finalize artifacts are deterministic/basic (summary/action/decision/stats) and can be expanded in later phases.
