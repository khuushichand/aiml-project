# IMPLEMENTATION_PLAN_job_system_unification.md

## Stage 0: Inventory and Baseline (PRD Phase 0)
**Goal**: Publish an accurate mapping matrix and capture baseline throughput/latency before cutover.
**Success Criteria**: Mapping matrix doc exists; baseline benchmark results are recorded; remaining legacy job artifacts are inventoried.
**Tests**: N/A (documentation + benchmark run).
**Status**: In Progress
**Owner**: Core Maintainers (primary), Embeddings Maintainers (benchmark)
**Gap -> Plan Checklist**:
- [x] Publish per-domain status/field mapping matrix doc.
- [ ] Run embeddings Redis vs Jobs benchmark and store results under `Docs/Performance/`.
- [x] Inventory remaining legacy job artifacts (Embeddings_Jobs_DB, in-process fallback) and confirm removal targets.

## Stage 1: Adapters and Public API Convergence (PRD Phase 1)
**Goal**: Make core Jobs the single system-of-record for Embeddings/Chatbooks/Prompt Studio APIs.
**Success Criteria**: Embeddings endpoints default to core Jobs; adapter mappings match documented matrix; priority mapping is applied.
**Tests**: Update/extend adapter unit tests; run API integration tests for embeddings/chatbooks/prompt-studio job endpoints.
**Status**: Complete
**Owner**: Embeddings Maintainers (primary), Core Maintainers
**Gap -> Plan Checklist**:
- [x] Flip `EMBEDDINGS_JOBS_BACKEND` default to Jobs and remove in-process fallback in `/api/v1/media/embeddings`.
- [x] Align embeddings status mapping (preserve `queued` vs `processing`) and document any intentional deviation.
- [x] Apply embedding priority mapping (0-100 -> 1-10) when creating Jobs entries.
- [x] Ensure public job list/detail endpoints read from Jobs only (already true, validate behavior).

## Stage 2: Worker Migration and Pipeline Chaining (PRD Phase 2)
**Goal**: Run domain workers exclusively via Jobs Worker SDK and implement staged pipelines with idempotency.
**Success Criteria**: Embeddings, chatbooks, and prompt studio workers operate on Jobs; stage chaining and idempotency keys are in place.
**Tests**: Add unit tests for stage idempotency + chaining; integration tests for worker processing.
**Status**: In Progress
**Owner**: Embeddings Maintainers (primary), Prompt Studio Maintainers, Chatbooks Maintainers
**Gap -> Plan Checklist**:
- [x] Implement stage job_types or queues for embeddings pipeline and root/stage lineage updates.
- [x] Add idempotency keys for base embeddings job creation (media_id + config + stage).
- [x] Add idempotency keys for stage transitions and ensure handlers are no-op if already completed.
- [ ] Validate workers (embeddings/chatbooks/prompt studio) run through Worker SDK in target deployments.

## Stage 3: Legacy Removal and Quotas Unification (PRD Phase 3)
**Goal**: Remove legacy job backends and unify quotas on core Jobs.
**Success Criteria**: `Embeddings_Jobs_DB` removed; billing uses Jobs counts/quotas; tests updated.
**Tests**: Update billing tests; remove `Embeddings_Jobs_DB` tests; run jobs quota tests.
**Status**: Complete
**Owner**: Core Maintainers (primary), Billing Maintainers
**Gap -> Plan Checklist**:
- [x] Replace org-level concurrent job aggregation with Jobs-based counts.
- [x] Delete `tldw_Server_API/app/core/DB_Management/Embeddings_Jobs_DB.py` and dependent tests.
- [x] Remove any remaining legacy job flags or shims tied to embeddings jobs DB.

## Stage 4: DAG Dependencies (PRD Phase 4)
**Goal**: Add explicit dependency edges and acquisition gating.
**Success Criteria**: `job_dependencies` table exists; acquisition respects dependencies; failure cascades are enforced.
**Tests**: Unit tests for dependency eligibility + cycles; integration tests for fan-out/fan-in pipelines.
**Status**: Not Started
**Owner**: Core Maintainers

---

## Embeddings_Jobs_DB Migration Path (Proposed)
**Owner**: Core Maintainers (primary), Billing Maintainers

1. **Introduce Jobs-based concurrency accounting**
   - Add a Jobs-based org aggregation helper in billing using `JobManager.summarize_by_owner_and_status(domain="embeddings")` and sum `status="processing"` for org members.
   - Add a feature flag (e.g., `BILLING_JOBS_CONCURRENCY_SOURCE=jobs|embeddings_db`) to compare results during rollout.

2. **Cutover billing to Jobs quotas**
   - Switch billing enforcement to Jobs aggregation by default after parity checks.
   - Remove any reads from `Embeddings_Jobs_DB` in billing and replace with Jobs count queries.

3. **Retire Embeddings_Jobs_DB**
   - Remove `Embeddings_Jobs_DB` module and its tests.
   - Delete DB file creation from docs/config if referenced; ensure runtime no longer creates `Databases/embeddings_jobs.db`.

4. **Validate quotas behavior**
   - Ensure Jobs quota envs (`JOBS_QUOTA_MAX_INFLIGHT`, `JOBS_QUOTA_MAX_QUEUED`, `JOBS_QUOTA_SUBMITS_PER_MIN`) cover prior concurrency limits.
   - Document any feature gaps (e.g., daily chunk quotas) and plan future replacements if needed.
