# Prompt Studio Module PRD

Status: Phase 1 complete; Phase 2 in progress; Phase 3 planned
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
| Job Leasing & Heartbeat | Queue entries use `leased_until` with configurable heartbeat (`TLDW_PS_JOB_LEASE_SECONDS`, `TLDW_PS_HEARTBEAT_SECONDS`). Workers renew leases; expired leases are reclaimable. |
| Postgres Advisory Locks | `pg_try_advisory_lock(id)` guards acquire operations; locks release on terminal job states. Metrics count attempts/acquisitions. |
| Strategy Validation | Optional knob validation for supported strategies (beam search, anneal, genetic). Rejects invalid configs when params are provided. |
| Status Endpoint | `GET /api/v1/prompt-studio/status` returns queue depth, lease health, and warnings for stale jobs. |
| Metrics | Gauges/counters exported via metrics registry (queue size, leases, advisory lock attempts, idempotency hits). |
| Test Harness | Split unit/integration suites, SQLite default with Postgres-only tests guarded by availability probe. Concurrency + leasing regression tests included. |

## 6. System Architecture
```
┌─────────────┐     ┌────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│ REST Clients│ ──► │ FastAPI Endpoints   │ ──► │ PromptStudioDatabase ORM │ ──► │ Storage (SQLite/PG) │
└─────────────┘     └────────────────────┘     └────────────┬─────────────┘     └─────────┬──────────┘
                                      ▲                     │                           │
                                      │                     ▼                           ▼
                             Idempotency layer       Job manager / leasing        Metrics & status
                                      │                     │                           │
                                      └──────── Worker heartbeats & advisory locks ─────┘
```
- **API Layer:** `tldw_Server_API/app/api/v1/endpoints/prompt_studio_*` handles CRUD, optimization submissions, and status queries. Rate-limiting deps now await properly.
- **Database Layer:** `PromptStudioDatabase` abstracts SQLite/Postgres differences, providing CRUD, queue leasing, idempotency helpers, and metrics-friendly status methods.
- **Job Manager:** `prompt_studio/job_manager.py` fetches queued jobs, renews leases, and respects heartbeat overrides.
- **Monitoring:** `prompt_studio/monitoring.py` registers counters/gauges. Metrics emitted on idempotency reuse, advisory lock attempts/acquisitions, queue depth, and lease expirations.

## 7. Data Model (simplified)
- `prompt_studio_projects`: projects with metadata, soft-delete flag, uniqueness scoped to user.
- `prompt_studio_prompts`: prompt entries linked to projects; includes versioning data.
- `prompt_studio_prompt_versions`: stored prompt variants and metadata snapshots.
- `prompt_studio_optimizations`: optimization runs referencing prompts/projects, capturing strategy config and status.
- `prompt_studio_job_queue`: background job entries with fields `status`, `leased_until`, `lease_owner`, metrics for reclaims.
- `prompt_studio_idempotency`: `(entity_type, idempotency_key, user_id) → entity_id` mapping for duplicate detection.
- Additional support tables: evaluation/test case records, metrics history, audit snapshots.

## 8. API Surface (core endpoints)
- `POST /api/v1/prompt-studio/projects` (Idempotency-Key aware)
- `POST /api/v1/prompt-studio/prompts`
- `POST /api/v1/prompt-studio/optimizations`
- `GET /api/v1/prompt-studio/status?warn_seconds=30`
- `PATCH/DELETE` counterparts for project/prompt lifecycle
- Background worker interface (internal) consumes job queue entries.

## 9. Observability & Metrics
- `prompt_studio.queue.length` gauge per backend/user.
- `prompt_studio.leases.active_total` and `prompt_studio.leases.expired_total`.
- `prompt_studio.pg_advisory.lock_attempts_total` / `locks_acquired_total`.
- `prompt_studio.idempotency.hit_total` / `miss_total`.
- Status endpoint summarises queue size, in-flight leases, oldest job age, and warnings.
- Metrics are registered through `core/Metrics/metrics_manager.py` and exposed via Prometheus exporter.

## 10. Configuration
- `TLDW_PS_BACKEND=sqlite|postgres`
- `TLDW_PS_JOB_LEASE_SECONDS` (default 60)
- `TLDW_PS_HEARTBEAT_SECONDS` (default 30)
- `TLDW_PS_SQLITE_WAL=1` (optional per-test WAL)
- `TLDW_TEST_POSTGRES_REQUIRED=1` to fail fast if PG unavailable
- `TEST_MODE=true` to enable CI-friendly shortcuts (skips heavy FTS, reduces retries)

## 11. Testing & QA
- **Unit Tests:** Strategy validation, status metrics hook, job manager helpers.
- **Integration (SQLite):** Idempotency, concurrency, leasing (reclaim paths), heartbeat override.
- **Integration (Postgres):** Advisory lock stress tests, scoped idempotency, dual-backend parity checks.
- **Fixtures:** PG availability probe ensures Postgres-specific suites are skipped or hard-failed based on env.

## 12. Roadmap
### Phase 1 - Reliability & Observability (Completed)
- Idempotency keys across create endpoints.
- Leasing/heartbeat with env overrides.
- Strategy knob validation (optional).
- `/status` endpoint + Prometheus gauges.
- Test harness adjustments to keep suites stable.

### Phase 2 - Correctness & Concurrency (In Progress)
- ✅ Postgres advisory locks in acquire path + metrics.
- ✅ Scoped idempotency mapping by user with composite unique index.
- ✅ Concurrency/heartbeat regression suites.
- ☐ Expand strategy validation matrix (PS-VALIDATION-EXPAND).
- Optional follow-up: process-level concurrency stress where safe.

### Phase 3 - Performance & CI (Planned)
- CI matrix for SQLite/Postgres suites (`TLDW_PS_BACKEND`).
- Shared DB/session scopes to cut migration churn in tests (where isolation allows).
- Documentation and tooling for running Prompt Studio suites locally (make targets, Docker instructions).

## 13. Risks & Open Questions
1. Strategy knob validation coverage still lags new features; risk of invalid configs slipping through (mitigation: PS-VALIDATION-EXPAND).
2. Advisory locks rely on Postgres-specific behavior; ensure fallback logic on SQLite remains correct.
3. Multi-tenant rate limiting/per-user quotas aren’t fully defined-future product work may require additional schema changes.
4. Need to confirm long-running jobs maintain leases under high latency heartbeat scenarios (potential stress tests).

## 14. References
- API doc: `Docs/API-related/Prompt_Studio_API.md`
- Database implementation: `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py`
- Job manager: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/job_manager.py`
- Monitoring: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/monitoring.py`
- Metrics registry: `tldw_Server_API/app/core/Metrics/metrics_manager.py`
- Tests: `tldw_Server_API/tests/prompt_studio/`
- Phase 2 TODOs: `Docs/Development/TODO_PromptStudio_Phase2.md`

---

Maintainer Checklist
- [x] Phase 1 delivered and documented
- [~] Phase 2: advisory locks + scoped idempotency done; validation expansion outstanding
- [ ] Phase 3: CI & performance tuning pending
