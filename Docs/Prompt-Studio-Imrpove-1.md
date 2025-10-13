# Prompt Studio – Improve Track 1

Goal: Incrementally harden Prompt Studio for reliability, safety, and observability while keeping behavior close to production. This tracker documents phases, success criteria, and current progress.

## Phase 1: Reliability + Observability
**Goal**: Guard against duplicate submits, prevent job loss via leasing, and surface basic health/metrics.

**Deliverables**
- Idempotency-Key support for create endpoints (projects, prompts, optimizations)
- Job leasing (visibility timeout) + heartbeat renewal with env overrides
- Per‑strategy validation (lightweight, optional knobs only)
- Status/health endpoint for queue + leases
- Prometheus gauges for queue/lease stats
- Keep tests prod‑close; prevent backend mixing in heavy tests; fast Postgres probe

**Success Criteria**
- Duplicate create requests return canonical entity and do not enqueue twice
- Processing jobs have a lease renewed periodically; expired leases reclaimable
- Strategy validation rejects clearly invalid configs when knobs are provided
- `/api/v1/prompt-studio/status` returns queue/lease stats
- Prometheus export contains Prompt Studio gauges

**Status**: Completed

**What shipped (files)**
- Idempotency map + endpoint wiring
  - Projects: `tldw_Server_API/app/api/v1/endpoints/prompt_studio_projects.py`
  - Prompts: `tldw_Server_API/app/api/v1/endpoints/prompt_studio_prompts.py`
  - Optimizations: `tldw_Server_API/app/api/v1/endpoints/prompt_studio_optimization.py`
  - Database: `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py`
- Job leasing + heartbeat
  - Lease columns, acquire/renew/clear: `.../PromptStudioDatabase.py`
  - Heartbeat override: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/job_manager.py`
  - Envs: `TLDW_PS_JOB_LEASE_SECONDS`, `TLDW_PS_HEARTBEAT_SECONDS`
- Strategy validation (optional knobs)
  - Base + extended validations (beam_search, anneal, genetic): `tldw_Server_API/app/api/v1/endpoints/prompt_studio_optimization.py`
  - Schema support for knobs: `optimization_config.strategy_params` in `tldw_Server_API/app/api/v1/schemas/prompt_studio_optimization.py`
- Status/health + Prometheus hooks
  - Status endpoint: `tldw_Server_API/app/api/v1/endpoints/prompt_studio_status.py`
  - Router wiring: `tldw_Server_API/app/main.py`
  - Lease stats (DB): `.../PromptStudioDatabase.py` (both SQLite & Postgres)
  - Metrics registry (gauges): `tldw_Server_API/app/core/Metrics/metrics_manager.py`
  - Docs: `Docs/API-related/Prompt_Studio_API.md`
- Test stability
  - Fast PG availability probe + CI fail-fast toggle in fixture: `tldw_Server_API/tests/prompt_studio/conftest.py`
  - Heavy tests demoted and no backend mixing (via env) [previous change]

**Tests**
- Idempotency integration: `tldw_Server_API/tests/prompt_studio/integration/test_idempotency.py`
- Leasing integration: `tldw_Server_API/tests/prompt_studio/integration/test_job_leasing.py`
- Strategy validation (base): `tldw_Server_API/tests/prompt_studio/unit/test_strategy_validation.py`
- Strategy validation (extended): `tldw_Server_API/tests/prompt_studio/unit/test_strategy_validation_extended.py`
- Status endpoint (integration): `tldw_Server_API/tests/prompt_studio/integration/test_status_endpoint.py`
- Metrics hook (unit): `tldw_Server_API/tests/prompt_studio/unit/test_status_metrics_hook.py`
 - Concurrency: `tldw_Server_API/tests/prompt_studio/integration/test_concurrency_jobs.py`
 - PG locks: `tldw_Server_API/tests/prompt_studio/integration/test_pg_advisory_locks.py`
 - Scoped idempotency (PG): `tldw_Server_API/tests/prompt_studio/integration/test_idempotency_scoped_lookup_postgres.py`
 - Strategy validation (more knobs): `tldw_Server_API/tests/prompt_studio/unit/test_strategy_validation_more.py`

## Phase 2: Correctness + Concurrency
**Goal**: Tighten correctness under contention and multi-user mode.

**Deliverables**
- Postgres advisory locks on acquire (pg_try_advisory_lock) to complement leased_until
- Scope idempotency lookups by user_id to avoid cross-user collisions
- Expand validation matrix as strategy knobs solidify (beam search pruning policy details, anneal schedules, genetic crossover variants)
- Add focused concurrency tests (multi-worker acquire/renew/race)
- Add lease-heartbeat override tests (TLDW_PS_HEARTBEAT_SECONDS)

**Status**: In Progress

**Open Items**
- [ ] Add `pg_try_advisory_lock` in Postgres acquire path (and verify unlock paths) — see TODO PS-LOCKS and Docs/TODO_PromptStudio_Phase2.md
- [x] Include `user_id` in idempotency lookups on DB layer; adjust endpoints/tests — implemented
- [x] Enforce per-user uniqueness for idempotency (composite unique index)
- [x] Implement Postgres idempotency helpers `_idem_lookup/_idem_record` — implemented
- [ ] Extend validation cases + unit tests as knob semantics are finalized — see TODO PS-VALIDATION-EXPAND
- [x] Concurrency tests for acquire/renew under load (sqlite + postgres) — initial coverage added; consider process-level tests — see TODO PS-CONCURRENCY
- [x] Heartbeat override long‑run test ensuring no premature reclaims — added initial short-run test — see TODO PS-LEASE-HB

### Current Test Status (local harness)
- Fixed migration ordering for SQLite/Postgres (003 iterations before 002 indexes)
- Implemented SQLite `create_optimization` (was missing, returned 500)
- Fixed rate-limit DI for projects/optimizations (avoid un-awaited coroutine)
- Normalized rate-limit DI across Prompt Studio endpoints (projects, optimizations, test-cases)
- Unit suite (Prompt Studio) passes under TEST_MODE with FTS skipped; warnings and skips expected
- Integration (SQLite path): status and concurrency basic tests pass; heartbeat override passes

Next
- Expand process-level concurrency tests (optional)
- Enable PG path in CI to run PG-only tests (`test_pg_advisory_locks.py`, idempotency scoped lookup for PG)

### Test Results (local)
- Environment: `DISABLE_HEAVY_STARTUP=1`, `TEST_MODE=true`, `SKIP_PROMPT_STUDIO_FTS=true`
- Unit: `tldw_Server_API/tests/prompt_studio/unit` — all tests passed (some skipped), no failures observed
- Integration (SQLite):
  - Status endpoint: pass (`test_status_endpoint.py`)
  - Concurrency (parallel acquire): pass (`test_concurrency_jobs.py::test_parallel_acquire_distinct_jobs_dual_backend`)
  - Heartbeat override: pass (`test_heartbeat_override.py`)

## Phase 3: Performance + CI
**Goal**: Reduce startup/test overhead and ensure credible CI coverage.

**Deliverables**
- Trim heavy app startup for Prompt Studio tests (keep prod‑like behavior via env gates)
- Reuse DB/session scope where safe to cut migrations churn
- Run Prompt Studio integration suites (sqlite+pg) in CI without backend mixing

**Status**: Planned

**Open Items**
- [ ] Add GH Actions jobs: matrix on `TLDW_PS_BACKEND=sqlite|postgres`; set `TLDW_TEST_POSTGRES_REQUIRED=1`
- [ ] Consider session/module‑scoped DB for heavy suites where isolation permits

## New/Relevant Environment Variables
- `TLDW_PS_BACKEND=sqlite|postgres` — choose a single backend for heavy tests
- `TLDW_TEST_POSTGRES_REQUIRED=1` — fail fast if PG probe fails
- `TLDW_PS_SQLITE_WAL=1` — opt‑in WAL for sqlite per‑test DBs
- `DISABLE_HEAVY_STARTUP=1` or `TEST_MODE=true` — skip unrelated heavy modules in tests
- `TLDW_PS_JOB_LEASE_SECONDS` — processing job lease window (default 60)
- `TLDW_PS_HEARTBEAT_SECONDS` — lease heartbeat interval override

## New/Updated Endpoints
- `GET /api/v1/prompt-studio/status?warn_seconds=30` — queue depth + lease health

## Notes & Rationale
- Validations are optional: only enforced when the knob is provided. This keeps existing clients working while improving guardrails for power‑users.
- Status endpoint is intentionally lightweight. Prometheus gauges update on read, avoiding extra background threads.
- Advisory locks are additive to leased_until and improve multi‑process robustness on Postgres.

---

Maintainer checklist
- [x] Phase 1 done
- [ ] Phase 2 in progress
- [ ] Phase 3 planned
