# Workflows PRD (v0.1 → v0.2)

This PRD consolidates the intended user experience, API scope, and technical requirements for the Workflows module, aligning with the current v0.1 implementation and outlining v0.2 priorities.

## Vision

Provide a safe, observable workflow runtime to orchestrate content processing, generation, and integrations across the platform. Users can create reusable definitions, run them ad‑hoc or saved, observe step‑level progress, and integrate via webhooks. Long‑term, a drag‑and‑drop GUI builder will sit on top of the same APIs.

## Personas

- Researcher/Editor: builds prompt+RAG pipelines, ingests documents, exports artifacts.
- Admin/Operator: sets policies, monitors runs, troubleshoots failures, manages retention.
- Developer/Integrator: triggers runs and consumes completion webhooks.

## Goals (v0.1)

- Linear workflows with minimal branching (`branch`, `map`), robust runtime (timeouts, retries with backoff, cancel, pause/resume, heartbeats, orphan reaping).
- Safe artifacts (scope validation, optional encryption), standardized persistence across SQLite/Postgres, ordered run events.
- Observability: metrics, traces, and structured events; webhook lifecycle with delivery history and DLQ.
- RBAC: owner‑scoped reads; admin override with audit trail.

## Non‑Goals (v0.1)

- Full DAG editor and complex fan‑in operators; distributed worker fleet; multi‑tenant billing/quotas beyond per‑user caps.

## APIs (Summary)

- Definitions: CRUD and immutable versions.
- Runs: create (sync/async), list/filter/paginate, get single; control (pause/resume/cancel/retry).
- Events: HTTP poll and WS stream.
- Artifacts: list, download, manifest with optional checksum verification.
- Step discovery: list step types with JSONSchema and examples.

### Control Flow Routing (v0.1)

Authors can combine three routing constructs to express if/else and success/failure paths:

1. **Branch step** – the `branch` adapter renders a templated condition and selects `true_next` or `false_next`, providing classic if/else semantics inside the step graph.
2. **Per-step `on_success` / `on_failure` targets** – any step may declare explicit follow-on step IDs for successful execution versus handled failures, keeping linear definitions easy to read while still diverging logic.
3. **Adapter-returned `__next__` overrides** – advanced adapters can return a payload containing `{"__next__": "step_id", "__status__": "ok|failed"}` to redirect execution programmatically (e.g., shortcuts, fallback paths, or external policy checks).

Builders and docs should surface these options so designers understand when to drop a branch node versus wiring success/failure continuations or deferring to adapter logic.

## Security & Policies

- Egress policy with profiles (strict/permissive/custom), allowed ports, host allowlist, private IP blocking. Webhook allow/deny (global and per tenant).
- Artifact scope validation with strict/non‑strict; per‑run `validation_mode` override.
- Optional encryption for artifact metadata (AES‑GCM) with env‑provided key.
- Per‑user quotas (burst/minute, daily) and endpoint rate limits (disabled under tests).

## Observability

- Metrics: runs/steps counters, durations, webhook deliveries; engine queue depth.
- Tracing: per‑run and per‑step; `traceparent` on outbound webhooks.
- Readiness: DB connectivity and schema version checks (Postgres), liveness and queue depth.

## Data & Persistence

- SQLite (default) or Postgres (recommended). Postgres uses JSONB for event payloads with GIN indexes; foreign keys with cascades; unique `(run_id, event_seq)`.
- Background workers: webhook DLQ retry/backoff; artifact GC by age.

## v0.2 Priorities

- DAG enhancements: richer branching/conditions, parallel map with structured fan‑in, timeouts and budgets per step.
- UX: WebUI builder MVP; validations from step schemas; example templates library.
- Operations: migration tooling and safety checks; schema versioning; dark‑launch rollout for new steps.

---

## Validation Modes (Artifacts)

Artifact downloads enforce scope and integrity checks with two validation modes:

- Strict (default):
  - Path scope: ensures the resolved `file://` path is contained by the recorded `workdir` for the run; 403 on failure.
  - Integrity: when `checksum_sha256` is present on an artifact, the download verifies checksum; 409 on mismatch.
- Non‑block (per‑run override):
  - Allow the download to proceed while logging warnings on scope or integrity failures.

Configuration and resolution order:
- Per‑run override `validation_mode="non-block"` (stored on run metadata when provided) takes precedence.
- Otherwise, `WORKFLOWS_ARTIFACT_VALIDATE_STRICT=true|false` controls behavior globally (default true).
- Containment is only enforced when a `workdir` is recorded on the run/step metadata to avoid false positives.

Range requests and limits:
- Single `Range` header is supported (bytes=START-END or bytes=START-).
- Responses include `Content-Range` and `206 Partial Content` when honored.
- Max served bytes per request are capped by `WORKFLOWS_ARTIFACT_MAX_DOWNLOAD_BYTES`.

Artifact manifest verification:
- `GET /runs/{run_id}/artifacts/manifest?verify=true` recomputes hashes and returns an `integrity_summary`.

## Control: Pause, Resume, Cancel

Runtime control actions are cooperative and observable:

- Pause: sets run status to `paused` and emits `run_paused`. The engine periodically checks and idles, keeping step leases alive. Subsequent `resume` continues from the current step.
- Resume: sets status back to `running` and emits `run_resumed`. The engine continues execution.
- Cancel: sets a cancel flag and attempts best‑effort termination of recorded subprocesses for the run, emits `step_cancelled` for each, updates run to `cancelled`, and emits `run_cancelled`. Adapters should cooperatively check `ctx.is_cancelled()`.

Idempotency and retries:
- Control endpoints are idempotent; repeated pause/resume/cancel return success and emit at most one state‑transition event.
- Per‑step retry defaults exist (e.g., `prompt`, `webhook`), overridable via `retry` on the step.

## Webhook Lifecycle

Completion webhooks can be configured via `on_completion_webhook` on a definition:

- Configuration:
  - Inline string or object `{ "url": "https://...", "include_outputs": true }`.
  - Global disable with `WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS=true`.
  - Timeouts via `WORKFLOWS_WEBHOOK_TIMEOUT` (seconds).
  - Egress policy enforced (global and per‑tenant allow/deny, private IP blocking).

- Delivery semantics:
  - Events: `webhook_delivery` appended with `status=delivered|failed|blocked` and HTTP status code when applicable.
  - Retries: failures enqueue into DLQ (`workflow_webhook_dlq`) with exponential backoff; worker enabled by `WORKFLOWS_WEBHOOK_DLQ_ENABLED=true`.

- Signing and replay protection (v1):
  - Headers set on each delivery:
    - `X-Workflow-Id`, `X-Run-Id`
    - `X-Webhook-ID`: unique per send (includes timestamp)
    - `X-Signature-Timestamp`: integer seconds
    - `X-Workflows-Signature-Version: v1`
    - `X-Workflows-Signature`: HMAC‑SHA256 hex digest over `"{ts}.{body}"` using `WORKFLOWS_WEBHOOK_SECRET`
    - `X-Hub-Signature-256: sha256=<hex>` (compat alias)
  - Receivers should validate timestamp freshness, recompute the HMAC over `f"{ts}.{body}"`, and compare using a constant‑time check.

## Retention & GC

- Artifact retention:
  - Worker: `WORKFLOWS_ARTIFACT_GC_ENABLED=true` starts a background GC loop.
  - Settings: `WORKFLOWS_ARTIFACT_RETENTION_DAYS` (default 30), `WORKFLOWS_ARTIFACT_GC_INTERVAL_SEC`.
  - Behavior: deletes DB entries and `file://` artifacts older than cutoff.
- Run/event retention:
  - Not enforced by default; depends on database backup/archival policies. Consider periodic purging by age in high‑volume deployments.

## Debugging

Enable targeted debug logs to aid incident triage:
- `WORKFLOWS_DEBUG=1` – umbrella flag enabling all Workflows debug logs.
- `WORKFLOWS_ARTIFACTS_DEBUG=1` – add logs to artifact list/manifest/download endpoints (IDs, paths, range headers).
- `WORKFLOWS_DLQ_DEBUG=1` – verbose logs for webhook DLQ listing and replay endpoints/workers.
