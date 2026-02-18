# Circuit Breaker Distributed Semantics + Admin Endpoint Implementation Plan

## Context

This plan covers three remaining long-term hardening items for the unified circuit breaker system:

1. Add merge/retry semantics on optimistic-lock conflicts.
2. Persist or lease half-open probe slots across workers.
3. Add a single RBAC-protected `/api/v1/admin/circuit-breakers` endpoint.

Primary code areas:
- `tldw_Server_API/app/core/Infrastructure/circuit_breaker.py`
- `tldw_Server_API/app/core/DB_Management/Circuit_Breaker_Registry_DB.py`
- `tldw_Server_API/app/api/v1/endpoints/admin/`
- `tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- `tldw_Server_API/tests/Infrastructure/`
- `tldw_Server_API/tests/AuthNZ/integration/` and/or `tldw_Server_API/tests/integration/`

---

## Stage 1: Persistence Contracts + API Design Freeze
**Goal**: Define the merge policy, distributed half-open lease contract, and admin endpoint response schema before code path changes.

**Implementation Tasks**:
- Define a local mutation representation for breaker persistence writes (e.g., `success`, `failure`, `transition`, `slot_acquire`, `slot_release`, `reset`).
- Define conflict-merge rules and precedence:
  - `OPEN` transition cannot be silently lost by stale writers.
  - Counter deltas are merged deterministically (not overwritten by stale snapshots).
  - `last_state_change_time` and `last_failure_time` use monotonic/most-recent semantics.
- Define lease-table schema and methods for distributed half-open probes.
- Define admin endpoint schema for breaker status listing and filtering.

**Success Criteria**:
- Merge/lease/admin contracts are documented in code comments or module docstrings where implemented.
- No runtime behavior changes yet; existing tests still pass unchanged.

**Tests**:
- None new in this stage; run smoke baseline:
  - `python -m pytest tldw_Server_API/tests/Infrastructure/test_circuit_breaker.py -q`

**Status**: Complete

---

## Stage 2: Merge + Retry Semantics for Optimistic Lock Conflicts
**Goal**: Ensure local breaker mutations are not dropped on DB version conflicts.

**Implementation Tasks**:
- Refactor `_persist_state_locked()` to support retry with bounded attempts (e.g., 3-5).
- On `CircuitBreakerOptimisticLockError`:
  - Load latest persisted state.
  - Merge pending local mutation into latest state (not just adopt latest).
  - Retry write with new expected version.
- Add conflict telemetry/logging (counter + debug context) so contention is observable.
- Keep behavior deterministic under contention and preserve existing lock scope guarantees.

**Success Criteria**:
- Concurrent state writes no longer silently discard local mutations.
- If retry budget is exhausted, behavior degrades safely (warning + consistent state), without crashing request path.

**Tests**:
- Extend `tldw_Server_API/tests/Infrastructure/test_circuit_breaker.py`:
  - conflict on success path merges counts correctly.
  - conflict on failure path preserves trip semantics.
  - conflict during transition preserves newer transition ordering.
  - retry exhaustion path logs and remains consistent.

**Status**: Complete

---

## Stage 3: Distributed Half-Open Probe Leases (Cross-Worker)
**Goal**: Enforce `half_open_max_calls` globally across workers/processes.

**Implementation Tasks**:
- Add persisted lease support in `Circuit_Breaker_Registry_DB.py`:
  - `acquire_probe_lease(name, max_calls, ttl_seconds, owner_id) -> lease_id | None`
  - `release_probe_lease(name, lease_id)`
  - `cleanup_expired_probe_leases(name)`
  - Optional `count_active_probe_leases(name)` for diagnostics.
- Introduce lease row TTL so abandoned slots self-heal.
- Update breaker call paths:
  - In half-open state, acquire distributed lease when persistence is enabled.
  - Release lease in `finally` blocks.
  - Retain current in-memory slot logic when persistence is disabled.
- On transitions to `OPEN`/`CLOSED`, clear stale leases for that breaker name.

**Success Criteria**:
- Across two registries sharing the DB, active half-open probes never exceed configured limit.
- Slot leakage from crashed/abandoned probes is bounded by TTL and self-recovers.

**Tests**:
- Add infra tests for shared DB behavior:
  - two registries race for half-open probe, only up to `half_open_max_calls` succeed.
  - expired lease allows later probe acquisition.
  - release path always frees lease on success/failure.

**Status**: Complete

---

## Stage 4: RBAC-Protected Unified Admin Endpoint
**Goal**: Expose one consolidated admin endpoint for all unified circuit breaker statuses.

**Implementation Tasks**:
- Add new admin endpoint module, recommended path:
  - `tldw_Server_API/app/api/v1/endpoints/admin/admin_circuit_breakers.py`
- Add endpoint:
  - `GET /api/v1/admin/circuit-breakers`
  - Reads from unified `registry.get_all_status()`.
  - Supports optional filters (`state`, `category`, `service`, `name_prefix`) and deterministic sort.
- Protect with RBAC dependency:
  - Router already enforces admin role; add permission gate such as `require_permissions(SYSTEM_LOGS)` for read access.
- Add response schemas in `admin_schemas.py`.
- Wire router include in `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py`.

**Success Criteria**:
- Endpoint returns all known breaker states (in-memory + persisted-only rows surfaced by registry).
- Non-admin/non-permitted principals receive auth errors consistent with existing admin endpoints.

**Tests**:
- Add endpoint tests (integration):
  - admin + required permission returns `200` with expected payload shape.
  - missing admin role returns `403`.
  - missing required permission returns `403`.
  - filtered queries return expected subset.

**Status**: Complete

---

## Stage 5: Hardening, Rollout, and Documentation
**Goal**: Ship safely with clear operator guidance and regression protection.

**Implementation Tasks**:
- Document configuration knobs:
  - conflict retry attempts/backoff
  - probe lease TTL
  - persistence mode interactions
- Add/refresh docs in Product/Operations docs and update circuit-breaker unification status text.
- Add regression notes for multi-worker deployment caveats and observability.

**Success Criteria**:
- Operators can tune contention/lease behavior without code changes.
- CI test matrix covers optimistic conflicts, distributed half-open limits, and admin endpoint auth.

**Tests**:
- Full targeted runs:
  - `python -m pytest tldw_Server_API/tests/Infrastructure/ -v`
  - `python -m pytest tldw_Server_API/tests/AuthNZ/integration/ -k "admin and circuit" -v`
  - `ruff check tldw_Server_API/app/core/Infrastructure/circuit_breaker.py tldw_Server_API/app/core/DB_Management/Circuit_Breaker_Registry_DB.py tldw_Server_API/app/api/v1/endpoints/admin/`

**Status**: Complete

---

## Delivery Order and Risk Notes

1. Implement Stage 2 before Stage 3 so conflict handling exists prior to introducing distributed slot leases.
2. Keep Stage 3 behind explicit persistence checks to avoid changing non-persistent runtime semantics.
3. Ship Stage 4 in the same PR set as Stage 2/3 or immediately after, so ops has immediate visibility into new behavior.
4. Prefer additive schema migration for lease table; do not break existing persisted registry rows.
