Last Updated: 2026-01-12

## Stage 1: Persistence + Migrations Alignment
**Goal**: Close the persistence/migration gap for the SQLAlchemy A/B repository and document the fallback path.
**Success Criteria**:
- A documented migration strategy exists for SQLite/Postgres (or a clear, reviewed rationale for the current `create_all` approach).
- Postgres CRUD coverage is added for the A/B repository (create/update/delete + list results).
- Documentation clarifies when the SQLAlchemy repo is used vs. the legacy adapter.
**Tests**:
- Integration: repository CRUD on Postgres (uses existing test fixtures).
- Unit: repository CRUD on SQLite (ensure no regressions).
**Status**: Not Started

## Stage 2: Collection Build Status + Retry Semantics
**Goal**: Make build/run status transitions explicit and ensure failures propagate to Jobs retries.
**Success Criteria**:
- Arm statuses include `building` and `failed` states with error details recorded.
- A/B run failures surface as retryable errors when appropriate (Jobs backoff engaged).
- The worker updates A/B status to `failed` with error details when retries exhaust.
**Tests**:
- Integration: enqueue -> handler fails -> retry/backoff -> terminal failure path.
- Unit: status transitions for per-arm build errors.
**Status**: Not Started

## Stage 3: Governance Enforcement (Allowlists + Quotas)
**Goal**: Enforce provider allowlists and quotas at API and worker levels.
**Success Criteria**:
- Provider allowlist is enforced for A/B arms (configurable via env/config).
- Quota checks block excessive A/B jobs pre-queue and at worker execution time.
- Errors are surfaced with consistent HTTP status + audit metadata.
**Tests**:
- Integration: reject disallowed provider during create/run.
- Integration: quota exceeded blocks run (API + worker).
**Status**: Not Started

## Stage 4: Observability Enhancements
**Goal**: Add A/B-specific metrics and structured logs for collection builds and runs.
**Success Criteria**:
- Metrics capture collection build duration/count, run duration, and success/failure per arm/test.
- Logs include structured fields for test_id/arm_id/job_id + error context.
- Metrics are documented in the evaluations observability docs.
**Tests**:
- Unit: metrics emitted on build/run success + failure.
**Status**: Not Started

## Stage 5: Testing Hardening (Property-Based + Export Schema)
**Goal**: Improve test coverage for invariants and export payload stability.
**Success Criteria**:
- Property-based tests validate collection hashing determinism and invariants.
- Export schema test ensures stable fields for JSON/CSV exports.
- Existing A/B tests remain deterministic in CI.
**Tests**:
- Property-based: hashing determinism and sensitivity.
- Integration: export payload schema contract.
**Status**: Not Started
