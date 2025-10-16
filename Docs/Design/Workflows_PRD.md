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

