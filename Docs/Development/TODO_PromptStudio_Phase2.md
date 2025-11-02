# Prompt Studio - Phase 2 TODOs

This file enumerates follow-up tasks for Prompt Studio Phase 2 (Correctness + Concurrency). Each task includes an ID, scope, and acceptance criteria.

## PS-LOCKS: Advisory Locks for Postgres Acquire
- Scope: `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py` (Postgres backend)
- Summary: Complement leased_until with `pg_try_advisory_lock(id)` in `acquire_next_job()` selection; ensure unlock on terminal states and retries.
- Acceptance:
  - Concurrent workers do not double-acquire the same job under contention (tests simulate concurrent acquire)
  - Locks are released on completion/failure/retry
  - Expired leases can be reclaimed even if an advisory lock was held previously

## PS-IDEMPOTENCY-PG: Postgres Idempotency Helpers
- Scope: Postgres backend in `PromptStudioDatabase`
- Summary: Implement `_idem_lookup/_idem_record` analogous to SQLite.
- Acceptance:
  - `lookup_idempotency()` returns the canonical entity id on duplicate key
  - `record_idempotency()` inserts idempotency mapping exactly once (idempotent on retries)

## PS-IDEMPOTENCY-SCOPE: Scope Idempotency by User
- Scope: SQLite + Postgres idempotency helpers and call sites
- Summary: Scope idempotency lookups by `(entity_type, idempotency_key, user_id)` to avoid cross-user collisions.
- Acceptance:
  - Duplicate keys for different users do not collide
  - Updated endpoints/tests use scoped lookups; unit/integration coverage exists

## PS-LEASE-HB: Heartbeat Override Tests
- Scope: `job_manager.py` and tests
- Summary: Add tests for `TLDW_PS_HEARTBEAT_SECONDS` to validate lease renewal cadence and no premature reclaims.
- Acceptance:
  - Long-running job remains leased with override shorter than default
  - No reclaim while heartbeat is active; reclaim after heartbeat stops

## PS-CONCURRENCY: Multi-Worker Acquire/Renew Tests
- Scope: DB acquire/renew paths (SQLite + Postgres)
- Summary: Add concurrency tests for multiple workers acquiring jobs; validate no double-processing and proper lease behavior.
- Acceptance:
  - Under parallel acquire calls, only one worker gets a job
  - Expired leases allow another worker to reclaim
  - Renewals extend leases correctly (no race leak)

## PS-VALIDATION-EXPAND: Strategy Knobs Expansion
- Scope: `prompt_studio_optimization.py` + unit tests
- Summary: Extend optional validation for new knobs as they’re defined (beam pruning policies, anneal schedules, genetic crossover variants).
- Acceptance:
  - New knobs validated when present; tests added for negative/positive cases
