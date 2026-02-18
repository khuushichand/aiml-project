# Prompt Studio Realtime Status Contract (Stage 4)

Date: 2026-02-18  
Scope: `/api/v1/prompt-studio/ws` status invalidation path for Studio tab

## Objective

Reduce status staleness during active Prompt Studio jobs by adding a WebSocket event path, while retaining polling as a fallback.

## Client Subscription

- Endpoint: `/api/v1/prompt-studio/ws`
- Auth:
  - single-user: `?api_key=<key>`
  - multi-user: `?token=<jwt>`
- Optional query: `project_id`
- On socket open, client sends:
  - `{ "type": "subscribe" }` for global status
  - `{ "type": "subscribe", "project_id": <id> }` for project-scoped status

## Event Types That Trigger Status Refresh

- `job_created`
- `job_started`
- `job_progress`
- `job_completed`
- `job_failed`
- `job_cancelled`
- `job_retrying`
- `evaluation_started`
- `evaluation_progress`
- `evaluation_completed`
- `optimization_started`
- `optimization_iteration`
- `optimization_completed`
- `job_update`
- `subscribed`

## Frontend Handling Rules

- Parse inbound JSON payloads.
- If payload `type` is in the status event set, invalidate React Query key `["prompt-studio", "status"]`.
- Ignore non-JSON or unknown payloads.
- Do not block UI on WebSocket errors.
- Keep adaptive polling active (`5s` when processing > 0, else `30s`) as fallback.

## Failure Behavior

- If socket setup fails (missing config/auth, network failure, handshake failure), client silently continues polling.
- If socket disconnects mid-session, no crash; status updates continue via polling.
