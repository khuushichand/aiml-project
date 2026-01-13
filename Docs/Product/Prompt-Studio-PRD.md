# Prompt Studio Module PRD

Status: Phase 1 complete; Phase 2 complete; Phase 3 in progress
Owner: Prompt Studio maintainers
Audience: Backend contributors, infra/testing owners

## 1. Summary
Prompt Studio lets users manage prompt projects, run optimization jobs, and orchestrate experiments across multiple strategies. The module exposes REST endpoints for project/prompt CRUD, queues asynchronous optimization jobs, and surfaces telemetry for monitoring. This PRD captures current capabilities, technical architecture, and the roadmap toward a fully reliable, observable, and CI-backed Prompt Studio experience.

## 2. Problem Statement
Prior iterations of Prompt Studio suffered from duplicate submissions, job loss under worker failures, and limited visibility into queue health. Contributors lacked a single source of truth describing constraints, data flows, or the rollout plan for reliability and observability improvements. We need a cohesive product/engineering spec so that future work (multi-user support, strategy expansion, CI parity) builds on a shared foundation without regressing the guarantees we recently introduced.

## 3. Goals & Non-Goals
### Goals
1. Deliver reliable prompt/project management with idempotent create flows and consistent status reporting.
2. Ensure optimization jobs are safely processed via leasing, heartbeat renewal, and advisory locking (Postgres).
3. Provide actionable observability: status endpoint, Prometheus gauges, metrics on leases/locks/idempotency.
4. Support SQLite (default) and Postgres backends with aligned behavior for single and multi-user deployments.
5. Document phased roadmap (reliability → correctness → performance/CI) with acceptance criteria.

### Non-Goals
- Designing advanced strategy semantics or UI/UX (handled separately).
- Replacing the job orchestration framework beyond current leasing/heartbeat scopes.
- Implementing distributed tracing or external workflow schedulers (future exploration).
- Large-scale performance benchmarking (Phase 3 only covers test/CI efficiency).

## 4. Personas
- **Prompt Engineer:** Creates projects, versions prompts, and runs optimization jobs iteratively.
- **Research Engineer:** Tunes strategy knobs (beam search, simulated annealing, genetic algorithms) and needs validation feedback.
- **Operations/Infra:** Monitors queue health, job throughput, and backend load.
- **QA/CI Owner:** Runs deterministic suites on SQLite and Postgres without backend mixing.

## 5. Current Capabilities (2025-10 snapshot)
| Area | Details |
| --- | --- |
| Idempotent Creates | `POST /prompt-studio/projects`, `/prompts`, `/optimizations` accept `Idempotency-Key` (scoped by user). Duplicate requests return canonical entities without requeueing. |
| Job Leasing & Heartbeat | Core Jobs entries use `leased_until`; WorkerSDK renews leases and expired leases are reclaimable. |
| Postgres Advisory Locks | `pg_try_advisory_lock(id)` guards acquire operations; locks release on terminal job states. Metrics count attempts/acquisitions. |
| Strategy Validation | Optional knob validation for supported strategies (beam search, anneal, genetic). Rejects invalid configs when params are provided. |
| Status Endpoint | `GET /api/v1/prompt-studio/status` reports core Jobs queue depth, lease health, and per-status counts. |
| Metrics | Gauges/counters exported via metrics registry (queue size, leases, advisory lock attempts, idempotency hits). |
| Test Harness | Split unit/integration suites, SQLite default with Postgres-only tests guarded by availability probe. Concurrency + leasing regression tests included. |

## 6. System Architecture
```
┌─────────────┐     ┌────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│ REST Clients│ ──► │ FastAPI Endpoints   │ ──► │ PromptStudioDatabase ORM │ ──► │ Content DB (SQLite/PG)│
└─────────────┘     └────────────────────┘     └────────────┬─────────────┘     └─────────┬──────────┘
                                      │                     │
                                      │                     ▼
                                      │               Idempotency layer
                                      │
                                      ▼
                             Core Jobs (JobManager) ──► Jobs DB (SQLite/PG)
                                      │
                                      ▼
                               Metrics & status
```
- **API Layer:** `tldw_Server_API/app/api/v1/endpoints/prompt_studio_*` handles CRUD, optimization submissions, and status queries. Rate-limiting deps now await properly.
- **Database Layer:** `PromptStudioDatabase` abstracts SQLite/Postgres differences for Prompt Studio CRUD and idempotency; execution status lives in core Jobs.
- **Jobs Orchestration:** Core Jobs (`app/core/Jobs/manager.py`) handles leasing/retries; `prompt_studio/jobs_adapter.py` bridges core Jobs status to Prompt Studio.
- **Monitoring:** `prompt_studio/monitoring.py` registers counters/gauges. Status endpoint reads core Jobs, with metrics emitted on idempotency reuse, advisory lock attempts/acquisitions, and lease health.

## 7. Data Model (simplified)
- `prompt_studio_projects`: projects with metadata, soft-delete flag, uniqueness scoped to user.
- `prompt_studio_prompts`: prompt entries linked to projects; includes versioning data.
- `prompt_studio_prompt_versions`: stored prompt variants and metadata snapshots.
- `prompt_studio_optimizations`: optimization runs referencing prompts/projects, capturing strategy config and status.
- `prompt_studio_job_queue`: legacy queue table retained for backward compatibility; core Jobs is the source of truth for execution and lease state.
- Core Jobs tables (`jobs`, `job_events`, `job_counters`, `job_queue_controls`, `job_attachments`) are the orchestration/execution layer for Prompt Studio workers and the `/status` endpoint.
- `prompt_studio_idempotency`: `(entity_type, idempotency_key, user_id) → entity_id` mapping for duplicate detection.
- Additional support tables: evaluation/test case records, metrics history, audit snapshots.

## 8. API Surface (core endpoints)
- `POST /api/v1/prompt-studio/projects` (Idempotency-Key aware)
- `POST /api/v1/prompt-studio/prompts`
- `POST /api/v1/prompt-studio/optimizations`
- `GET /api/v1/prompt-studio/status?warn_seconds=30`
- `PATCH/DELETE` counterparts for project/prompt lifecycle
- Background worker interface (internal) consumes core Jobs entries via the Jobs worker SDK.

## 9. Observability & Metrics
- `prompt_studio.queue.length` gauge per backend/user.
- `prompt_studio.leases.active_total` and `prompt_studio.leases.expired_total`.
- `prompt_studio.pg_advisory.lock_attempts_total` / `locks_acquired_total`.
- `prompt_studio.idempotency.hit_total` / `miss_total`.
- Status endpoint summarizes core Jobs queue size, processing counts, lease health, and success rate.
- Metrics are registered through `core/Metrics/metrics_manager.py` and exposed via Prometheus exporter.

## 10. Configuration
- `TLDW_PS_BACKEND=sqlite|postgres`
- `JOBS_DB_URL` (optional; core Jobs backend, Postgres when set)
- `PROMPT_STUDIO_JOBS_QUEUE` (default `default`)
- `PROMPT_STUDIO_JOBS_LEASE_SECONDS` (WorkerSDK lease length)
- `PROMPT_STUDIO_MAX_CONCURRENT_JOBS` (maps to `JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO`)
- `PROMPT_STUDIO_JOBS_MAX_QUEUED` (maps to `JOBS_QUOTA_MAX_QUEUED_PROMPT_STUDIO`)
- `PROMPT_STUDIO_JOBS_SUBMITS_PER_MIN` (maps to `JOBS_QUOTA_SUBMITS_PER_MIN_PROMPT_STUDIO`)
- Per-user overrides via `JOBS_QUOTA_*_PROMPT_STUDIO_USER_<user_id>` (optional)
- AuthNZ profile overrides: `limits.prompt_studio_max_concurrent_jobs`, `limits.prompt_studio_max_queued_jobs`, `limits.prompt_studio_submits_per_min`
- `TLDW_PS_JOB_LEASE_SECONDS` (legacy prompt_studio_job_queue)
- `TLDW_PS_HEARTBEAT_SECONDS` (legacy prompt_studio_job_queue)
- `TLDW_PS_SQLITE_WAL=1` (optional per-test WAL)
- `TLDW_TEST_POSTGRES_REQUIRED=1` to fail fast if PG unavailable
- `TEST_MODE=true` to enable CI-friendly shortcuts (skips heavy FTS, reduces retries)

## 11. Testing & QA
- **Unit Tests:** Strategy validation, status metrics hook, job manager helpers.
- **Integration (SQLite):** Idempotency, concurrency, leasing (reclaim paths), heartbeat override.
- **Integration (Postgres):** Advisory lock stress tests, scoped idempotency, dual-backend parity checks.
- **Fixtures:** PG availability probe ensures Postgres-specific suites are skipped or hard-failed based on env.
- **AuthNZ Integration:** Prompt Studio user context and permissions are wired through the unified AuthNZ stack:
  - `get_prompt_studio_user` uses `get_request_user` to obtain a normalized `User` (with roles/permissions/is_admin claims) and derives `user_context.is_admin` / `user_context.permissions` from those claims rather than from `AUTH_MODE`/`is_single_user_mode()`.
  - HTTP-level tests in `tldw_Server_API/tests/AuthNZ_Unit/test_prompt_studio_user_claims.py` validate that admin vs non-admin principals produce the expected `user_context` (including permissions), and `tldw_Server_API/tests/prompt_studio/unit/test_prompt_studio_deps_headers.py` verifies header forwarding and 401 semantics when credentials are missing.

## 12. Roadmap
### Phase 1 - Reliability & Observability (Completed)
- Idempotency keys across create endpoints.
- Leasing/heartbeat with env overrides.
- Strategy knob validation (optional).
- `/status` endpoint + Prometheus gauges.
- Test harness adjustments to keep suites stable.

### Phase 2 - Correctness & Concurrency (Completed)
- ✅ Postgres advisory locks in acquire path + metrics.
- ✅ Scoped idempotency mapping by user with composite unique index.
- ✅ Concurrency/heartbeat regression suites.
- ✅ Expand strategy validation matrix (PS-VALIDATION-EXPAND).
- ✅ SQLite fallback acquire/reclaim coverage for advisory-lock path.
- ✅ Prompt Studio quota defaults mapped to core Jobs per-user quotas.
- ✅ Process-level concurrency stress coverage (process-level parallel acquire tests).

### Phase 3 - Performance & CI (In Progress)
- ✅ Shared DB/session scopes to cut migration churn in tests (where isolation allows).
- CI matrix for SQLite/Postgres suites (`TLDW_PS_BACKEND`).
- ✅ Documentation and tooling for running Prompt Studio suites locally (make targets, Docker instructions).

## 13. Risks & Open Questions
1. Per-user inflight limits depend on `owner_user_id` being populated on jobs; ensure all Prompt Studio job creation paths continue to set it.

## 14. References
- API doc: `Docs/API-related/Prompt_Studio_API.md`
- Database implementation: `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py`
- Jobs adapter: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/jobs_adapter.py`
- Jobs worker: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/services/jobs_worker.py`
- Monitoring: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/monitoring.py`
- Metrics registry: `tldw_Server_API/app/core/Metrics/metrics_manager.py`
- Tests: `tldw_Server_API/tests/prompt_studio/`
- Phase 2 TODOs: `Docs/Development/TODO_PromptStudio_Phase2.md`

---

Maintainer Checklist
- [x] Phase 1 delivered and documented
- [x] Phase 2: advisory locks + scoped idempotency + validation expansion + quota mapping + lease stress + AuthNZ quota policy + per-user inflight guard + concurrency stress done
- [ ] Phase 3: CI & performance tuning pending
