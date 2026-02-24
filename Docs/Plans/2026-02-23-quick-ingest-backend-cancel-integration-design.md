# Quick Ingest Backend-Cancel Integration Design

## Date
2026-02-23

## Owner
WebUI/Extension quick-ingest flow

## Goal
Complete full quick-ingest integration with existing backend media-ingest jobs cancellation semantics, without introducing new backend API surface in this checkpoint.

## Scope

In scope:
- Quick ingest `storeRemote` flow in extension/background and direct web runtime.
- Use existing backend endpoints:
  - `POST /api/v1/media/ingest/jobs`
  - `GET /api/v1/media/ingest/jobs/{job_id}`
  - `POST /api/v1/media/ingest/jobs/cancel?batch_id=...`
- Session-bound cancellation behavior and result mapping.
- Unit/integration/e2e coverage for mid-process cancel.

Out of scope:
- Migrating to SSE (`/api/v1/media/ingest/jobs/events/stream`) for this checkpoint.
- New backend endpoints or schema changes.
- Context-menu ingest architecture refactor outside quick-ingest runtime touchpoints.

## Current Backend Capability (Already Available)

Backend already supports what this checkpoint needs:
- Batch job submit with `batch_id`.
- Job status polling per job.
- Batch cancel by `batch_id` (and alias `session_id`) with owner/admin authorization.
- Worker cooperative cancellation (`cancel_check` propagation in media ingestion worker).

This means the remaining work is integration hardening in client/runtime layers and tests.

## Selected Architecture (Approach 2)

Use a canonical quick-ingest remote job orchestration layer shared by:
- extension/background runtime
- direct web runtime

### Why
- Avoid duplicated poll/cancel/result-mapping logic.
- Keep cancellation semantics identical across extension and webui.
- Reduce drift risk as backend contracts evolve.

## Data Flow

### Start
1. UI requests session start and receives immediate `sessionId` ack.
2. Runtime starts async processing keyed by `sessionId`.

### StoreRemote Execution
1. Submit each URL/file item (or grouped item payload) through `POST /media/ingest/jobs`.
2. Track returned `batch_id` and `job_id` values under the active session.
3. Poll `GET /media/ingest/jobs/{job_id}` until terminal.
4. Emit progress and terminal results keyed by session id.

### Cancel
1. User confirms cancel in modal.
2. UI transitions immediately to terminal cancelled state.
3. Runtime marks session cancelled and aborts in-flight request/upload controllers.
4. Runtime sends best-effort backend batch cancel for all tracked `batch_id`s.
5. Late completion/failed events do not override cancelled terminal UI.

## State and Result Semantics

Terminal state priority:
1. `cancelled` (user initiated)
2. `failed`
3. `completed`

Job status normalization:
- backend `completed` -> item `ok`
- backend `cancelled` -> item `error` with cancelled message + cancelled outcome
- backend `failed|quarantined` -> item `error` with backend error message
- timeout -> item `error` timeout message

## Error Handling

- Cancel request failures are non-fatal once UI is already terminal-cancelled.
- Auth failures while polling mark affected item as error; run continues for other items where possible.
- Missing `batch_id`/`job_id` from submit is treated as contract failure for that item.
- Session cleanup is always performed in `finally` to avoid stale tracking maps.

## Testing Strategy

Unit:
- Shared orchestration helper behavior (job id extraction, batch tracking, polling terminal mapping, cancel dispatch).
- Direct runtime cancel path calls batch-cancel endpoint for tracked session batches.
- Session terminal lock keeps cancelled state against late completions.

UI/Integration:
- Modal cancel confirmation gate:
  - misclick path does not send cancel
  - confirmed path sends cancel and shows cancelled terminal copy

E2E:
- Web quick-ingest cancel mid-process with confirmation.
- Assert terminal cancelled copy remains stable after delay (late event guard).
- Verify test interception aligns with jobs endpoint usage (`/media/ingest/jobs`, not `/media/add`).

Backend contract confidence:
- Keep media ingest backend integration tests in runbook for regression checks.

## Rollout and Risk

Rollout:
- Incremental, no backend deploy dependency.
- Land helper + direct runtime + background runtime + tests in small commits.

Primary risks:
- Hidden divergence between direct and background implementations if helper extraction is incomplete.
- Polling churn if timeout/poll-interval defaults are inconsistent.
- Existing baseline TypeScript noise can hide regressions unless scoped test commands are used.

Mitigations:
- Single shared helper module.
- Scoped tests first, then broader runs.
- Explicit cancellation and terminal-state assertions in unit + e2e tests.

