# Workflows PRD (Curated)

This document summarizes the Product Requirements for the Workflows module as of v0.1 with forward-looking notes for v0.2. For the full living design, see `../Design/Workflows_PRD.md`.

## Scope

- Definition CRUD and immutable versions
- Run submission (saved/adhoc), control (pause/resume/cancel/retry)
- Events (HTTP/WS), artifacts (list/manifest/download)
- Webhook lifecycle with signing and DLQ
- SQLite (default) and PostgreSQL (recommended) backends

### Control Flow Routing

- `branch` step: templated condition with `true_next` / `false_next` targets (if/else).
- Per-step `on_success` / `on_failure` jump targets for linear success/failure splits.
- Adapter-returned `{"__next__": "step_id", "__status__": ...}` to programmatically choose the next step.

## Validation Modes (Artifacts)

- Strict (default): path scope + checksum enforced
- Non-block (per-run override): proceed with warnings
- Env: `WORKFLOWS_ARTIFACT_VALIDATE_STRICT`; per-run override `validation_mode="non-block"`
- Range responses: single `Range` supported; capped by `WORKFLOWS_ARTIFACT_MAX_DOWNLOAD_BYTES`

## Control Semantics

- Pause → `paused` + `run_paused` event; cooperatively idles
- Resume → `running` + `run_resumed`; continues from current step
- Cancel → sets cancel flag, best-effort terminate subprocesses, `run_cancelled`
- Adapters check `ctx.is_cancelled()`; control endpoints are idempotent

## Webhooks

- Configure with `on_completion_webhook`
- Egress policy enforceable; retries via DLQ worker
- Signing (v1):
  - `X-Workflows-Signature-Version: v1`
  - `X-Signature-Timestamp`, `X-Webhook-ID`, `X-Workflow-Id`, `X-Run-Id`
  - `X-Workflows-Signature` = HMAC-SHA256 over `"{ts}.{body}"` with `WORKFLOWS_WEBHOOK_SECRET`
  - `X-Hub-Signature-256: sha256=<hex>` alias

## Retention

- Artifact GC worker: `WORKFLOWS_ARTIFACT_GC_ENABLED` (days: `WORKFLOWS_ARTIFACT_RETENTION_DAYS`)
- Run/event retention: manage via DB policies; no hard cutoff by default

## Debug Flags

- `WORKFLOWS_DEBUG=1` - enable broad Workflows debug logs
- `WORKFLOWS_ARTIFACTS_DEBUG=1` - artifact endpoints
- `WORKFLOWS_DLQ_DEBUG=1` - DLQ endpoints/worker
