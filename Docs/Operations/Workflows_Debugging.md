# Workflows Debugging Guide

Targeted troubleshooting tips for Workflows runs, artifacts, webhooks, and human-in-loop flows. Use alongside the Runbook.

## Enable Debug Logs

Set environment flags before starting the server:

- `WORKFLOWS_DEBUG=1` - broad debug logs for endpoints and engine
- `WORKFLOWS_ARTIFACTS_DEBUG=1` - artifact endpoints (IDs, file paths, Range parsing, containment decisions)
- `WORKFLOWS_DLQ_DEBUG=1` - webhook DLQ list/replay endpoints and worker

Check application logs for lines prefixed with `Workflows:` or `Artifacts:` hints.

## Artifact Downloads

- Containment: Enforced only when a `workdir` is recorded on the run/step metadata. If strict mode blocks unexpected paths, ensure your step recorded the correct workdir.
- Strict vs Non-block:
  - Strict: `WORKFLOWS_ARTIFACT_VALIDATE_STRICT=true` (default) or run `validation_mode='block'`
  - Non-block: per-run `validation_mode='non-block'` or env set to false (proceeds with warnings)
- Range: Only a single `Range` header is honored; responses use `206 Partial Content` and `Content-Range`.
- Checksums: When present, checksum mismatches trigger `409 Conflict` in strict mode; non-block logs a warning and continues.

Checklist:
- Confirm the artifact is listed under `GET /runs/{run_id}/artifacts`.
- Ensure the API and your test harness point to the same DB (check `DATABASE_URL_WORKFLOWS`).
- Inspect debug logs with `WORKFLOWS_ARTIFACTS_DEBUG=1` for resolved path and containment decisions.

## Webhooks

- Signing scheme (v1): The server signs the body with HMAC-SHA256 using `WORKFLOWS_WEBHOOK_SECRET`.
  - Headers: `X-Workflows-Signature-Version: v1`, `X-Workflows-Signature`, `X-Hub-Signature-256`, `X-Signature-Timestamp`, `X-Webhook-ID`, `X-Workflow-Id`, `X-Run-Id`
  - Compute signature over `f"{ts}.{body}"` using the `X-Signature-Timestamp` value.

Python verifier snippet:

```python
import hmac, hashlib

def verify(secret: str, ts: str, body: str, received: str) -> bool:
    mac = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), received)
```

- Egress policy: If deliveries show `blocked`, check allow/deny lists and private IP blocking configuration.
- DLQ: Inspect `workflow_webhook_dlq` for failures; enable `WORKFLOWS_DLQ_DEBUG=1` and run the worker to replay.

## Pause/Resume/Cancel & Human-in-Loop

- Pause: sets `paused` and emits `run_paused`; engine cooperatively idles and maintains leases.
- Resume: sets `running` and emits `run_resumed`.
- Cancel: sets cancel flag, best-effort terminates subprocesses, updates run to `cancelled`.
- Human steps: `wait_for_human`/`wait_for_approval` set `waiting_human`/`waiting_approval` status; resume flow by POSTing to:
  - `POST /api/v1/workflows/runs/{run_id}/steps/{step_id}/approve`
  - `POST /api/v1/workflows/runs/{run_id}/steps/{step_id}/reject`

Debug checklist:
- Inspect events stream (`GET /runs/{run_id}/events?limit=200`) for `run_paused`, `run_resumed`, `run_cancelled`, `step_*`.
- If resume stalls, verify `after_step_id` handling via logs (enabled by `WORKFLOWS_DEBUG`).

## Idempotency

- Provide `idempotency_key` in run requests to deduplicate repeated submissions.
- With `WORKFLOWS_DEBUG=1`, logs show reuse decisions for existing runs.
- Expect the same `run_id` to be returned if a matching run exists for your key and user.

## DB & Environment

- Ensure `DATABASE_URL_WORKFLOWS` is consistent across app/test contexts.
- SQLite: watch for `database is locked`; reduce concurrent writers or move to Postgres for heavier loads.
- Postgres: monitor connection pool saturation and autovacuum on `workflow_events`.
