Last Updated: 2026-01-12

## Stage 1: Jobs Architecture & Contracts
**Goal**: Define the Jobs-backed A/B test run contract (domain/queue/job_type, payload schema, status mapping, idempotency) with reuse scoped to a single test lifecycle.
**Success Criteria**:
- Jobs domain `evaluations` and job_type `embeddings_abtest_run` are documented with payload fields.
- `reuse_existing` is explicitly scoped to reuse within the same test_id only.
- AB test status transitions are defined: `pending -> queued -> running -> completed|failed`.
- Idempotency strategy for `run` is defined (Jobs idempotency key + Evaluations DB mapping).
**Tests**: N/A (design/contract stage)
**Status**: Not Started

## Stage 2: Jobs-Backed Run Execution
**Goal**: Replace `BackgroundTasks` with Jobs backend execution using WorkerSDK.
**Success Criteria**:
- `POST /embeddings/abtest/{test_id}/run` enqueues a Jobs row and returns a job reference.
- WorkerSDK processes jobs with lease renewals and retry/backoff on failure.
- AB test status and progress are updated from worker execution, and state survives restarts.
**Tests**:
- Integration: enqueue + worker processes a minimal A/B test with TESTING mode.
- Integration: failed handler retries until `max_retries` exhausted.
**Status**: Not Started

## Stage 3: Collection Reuse + Cleanup
**Goal**: Implement per-test reuse and cleanup of collections and DB rows.
**Success Criteria**:
- Reuse checks only re-use collections for the same test_id + arm + hash.
- Cleanup deletes Chroma collections, A/B DB rows, and idempotency entries.
- TTL sweeper is Jobs-backed and removes expired collections for abandoned tests.
**Tests**:
- Unit: reuse hash determinism and per-test reuse behavior.
- Integration: cleanup removes collections + DB rows.
**Status**: Not Started

## Stage 4: Observability + CI Guard
**Goal**: Add Jobs-backed metrics/audit events for A/B runs and enforce plan freshness in CI.
**Success Criteria**:
- Prometheus metrics for queue depth, durations, and success/failure per job_type.
- Audit events emitted on create/run/delete/export.
- CI guard fails when this plan is missing or stale.
**Tests**:
- Unit: metrics/audit hooks invoked on job lifecycle.
- CI: plan freshness check runs in workflow.
**Status**: Not Started
