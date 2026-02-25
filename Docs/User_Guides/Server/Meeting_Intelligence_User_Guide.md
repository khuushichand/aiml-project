# Meeting Intelligence User Guide

Last Updated: 2026-02-24

## Overview

Meeting Intelligence gives you a meeting-first API surface under `/api/v1/meetings` for:

1. Managing meeting sessions.
2. Applying templates.
3. Generating structured artifacts from transcripts.
4. Streaming meeting updates (SSE and WebSocket).
5. Sharing artifacts to Slack or generic webhooks with retry support.

For the technical API contract, see `Docs/Design/Meeting_Intelligence_API.md`.

## Prerequisites

1. Server is running and auth is configured.
2. You have either:
   - `X-API-KEY` (single-user), or
   - `Authorization: Bearer <token>` (multi-user/JWT).

Base URL in examples:

```bash
export BASE_URL="http://127.0.0.1:8000"
```

## Quickstart Workflow

### 1. Health Check

```bash
curl -s "$BASE_URL/api/v1/meetings/health" | jq
```

### 2. Create a Session

```bash
curl -s -X POST "$BASE_URL/api/v1/meetings/sessions" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <your-api-key>" \
  -d '{
    "title": "Weekly Product Sync",
    "meeting_type": "standup",
    "source_type": "upload",
    "language": "en"
  }' | jq
```

Save `id` as `session_id`.

### 3. Optional: List Templates

Scopes are validated and limited to:

1. `builtin`
2. `org`
3. `team`
4. `personal`

```bash
curl -s "$BASE_URL/api/v1/meetings/templates?scope=builtin" \
  -H "X-API-KEY: <your-api-key>" | jq
```

### 4. Finalize Transcript into Artifacts

```bash
curl -s -X POST "$BASE_URL/api/v1/meetings/sessions/<session_id>/commit" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <your-api-key>" \
  -d '{
    "transcript_text": "TODO: Alice sends follow-up. DECISION: ship in two phases."
  }' | jq
```

By default, v1 generates:

1. `summary`
2. `action_items`
3. `decisions`
4. `speaker_stats`

### 5. List Artifacts

```bash
curl -s "$BASE_URL/api/v1/meetings/sessions/<session_id>/artifacts" \
  -H "X-API-KEY: <your-api-key>" | jq
```

### 6. Share to Slack or Generic Webhook

```bash
curl -s -X POST "$BASE_URL/api/v1/meetings/sessions/<session_id>/share/slack" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <your-api-key>" \
  -d '{
    "webhook_url": "https://hooks.slack.test/services/T000/B000/XXXX",
    "artifact_ids": []
  }' | jq
```

```bash
curl -s -X POST "$BASE_URL/api/v1/meetings/sessions/<session_id>/share/webhook" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <your-api-key>" \
  -d '{
    "webhook_url": "https://webhooks.example.test/meeting"
  }' | jq
```

## Live Updates

### SSE

```bash
curl -N "$BASE_URL/api/v1/meetings/sessions/<session_id>/events" \
  -H "X-API-KEY: <your-api-key>"
```

### WebSocket

Use:

1. Header auth (`Authorization` / `X-API-KEY`) or
2. Query auth (`?token=...` or `?api_key=...`).

Behavior:

1. `ping` message returns `pong`.
2. `transcript.partial` frames are streamed back but not persisted.
3. Final transcript events (`transcript.final`, or messages marked `final`/`is_final`) are persisted.

## Rate Limiting

Meetings HTTP routes use the same API rate limiting dependency pattern as other server routes. If you hit limits, the API returns `429` with `Retry-After`.

## Common Errors

### 401 Unauthorized

Check API key/JWT and ensure the correct auth mode is configured.

### 403 Forbidden on Template Creation

You cannot create `builtin` templates, and `org`/`team` scopes require elevated privileges.

### 404 Meeting Not Found

The `session_id` does not exist for your authenticated user scope.

### 422 Invalid Template Scope

`scope` query must be one of: `builtin`, `org`, `team`, `personal`.

## Operational Notes

Webhook and Slack dispatches are queued and retried by the meetings DLQ worker:

1. Enable with `MEETINGS_WEBHOOK_DLQ_ENABLED=1`.
2. Tune retry controls via `MEETINGS_WEBHOOK_DLQ_*` environment variables.

See `Docs/Design/Meeting_Intelligence_API.md` for full worker variables and event types.
