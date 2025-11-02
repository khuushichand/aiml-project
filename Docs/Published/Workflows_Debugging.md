# Workflows Debugging (Curated)

Condensed troubleshooting tips for Workflows. See the full guide at `../Operations/Workflows_Debugging.md`.

## Enable Logs

- `WORKFLOWS_DEBUG=1` - broad debug logs
- `WORKFLOWS_ARTIFACTS_DEBUG=1` - artifact endpoints
- `WORKFLOWS_DLQ_DEBUG=1` - DLQ endpoints/worker

## Artifacts

- Containment enforced when `workdir` recorded; strict vs non-block controls blocking vs warning.
- Single `Range` per request; `206` with `Content-Range` on success.
- Checksums: `409` on mismatch in strict; warn in non-block.

## Webhooks

- HMAC v1 over `"{ts}.{body}"` with `WORKFLOWS_WEBHOOK_SECRET`.
- Validate `X-Workflows-Signature` using `X-Signature-Timestamp`.
- DLQ for failures; replay with worker enabled.

## Controls & Human-in-Loop

- Pause/Resume/Cancel are idempotent and emit events.
- Human steps (`wait_for_human`/`wait_for_approval`): resume via `approve` or `reject` endpoints.

## Idempotency

- Provide `idempotency_key` in run requests to deduplicate; same `run_id` is returned.

## DB Checks

- Ensure `DATABASE_URL_WORKFLOWS` consistency across app/tests.
- SQLite contention → reduce writers or use Postgres.
