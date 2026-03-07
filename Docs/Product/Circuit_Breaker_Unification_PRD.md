# Circuit Breaker Unification PRD

Status: Implemented (core unification complete; distributed persistence/leases and unified admin endpoint delivered)
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Unify all circuit breaker implementations under a single Infrastructure module so resilience behavior, metrics, and configuration are consistent across Embeddings, Evaluations, RAG, MCP Unified, TTS, Chat, and Web Scraping.

## 2. Problem Statement
Circuit breakers are implemented multiple times with divergent semantics:
- Embeddings breaker usage now routed to unified Infrastructure breaker: `tldw_Server_API/app/core/Embeddings/connection_pool.py`
- Evaluations breaker with async timeouts and per-provider configs: `tldw_Server_API/app/core/Evaluations/circuit_breaker.py`
- RAG resilience breaker and coordinator: `tldw_Server_API/app/core/RAG/rag_service/resilience.py`
- MCP Unified inline breaker logic: `tldw_Server_API/app/core/MCP_unified/modules/base.py`
- TTS breaker with backoff and health checks: `tldw_Server_API/app/core/TTS/circuit_breaker.py`
- Chat provider manager breaker: `tldw_Server_API/app/core/Chat/provider_manager.py`
- Web Scraping simple breaker: `tldw_Server_API/app/core/Web_Scraping/WebSearch_APIs.py`

This duplication increases maintenance cost and creates subtle behavioral drift across services.

## 3. Unifying Principle (Simplification Cascade)
All circuit breakers are the same state machine with different labels. One shared implementation eliminates half a dozen bespoke breakers and their tests.

**Expected deletions**: Embeddings breaker, Evaluations breaker, RAG breaker, MCP inline logic, TTS breaker core, Chat breaker, Web Scraping simple breaker.

## 4. Goals & Success Criteria
- One shared circuit breaker implementation under `app/core/Infrastructure`.
- Consistent states (CLOSED/OPEN/HALF_OPEN), thresholds, and backoff behavior.
- Unified metrics via the Metrics manager with a compatibility shim for existing dashboards.
- Sync and async call support with a single decorator-based API.

Success metrics:
- No runtime module defines its own circuit breaker class.
- All circuit breaker metrics are emitted via the Metrics manager with shared labels.
- Existing tests continue to pass with shims or adapters.
- Parity tests cover each domain before legacy tests are removed.

## 5. Non-Goals
- Rewriting retry logic or fallback logic outside circuit breaker boundaries.
- Changing API response schemas or rate-limiting behavior.
- Introducing new dependencies.

## 6. In Scope
- New shared circuit breaker module in Infrastructure.
- Configuration mapping from existing per-module settings.
- Shims for legacy import paths during migration.
- Metrics standardization and legacy label mapping.

## 7. Out of Scope
- Replacing domain-specific health monitors (keep in their modules).
- Reworking provider selection logic or load balancing.

## 8. Functional Requirements
### 8.1 Core API
- `CircuitBreaker(name, category, config)` with:
  - States: CLOSED, OPEN, HALF_OPEN.
  - Failure threshold and success threshold.
  - Half-open probe limits.
  - Half-open probes may run in parallel for async contexts, up to `half_open_max_calls`.
  - In HALF_OPEN, `success_threshold` successes transition to CLOSED; any failure transitions to OPEN and resets the success counter.
  - When probes run in parallel, any single failure transitions to OPEN immediately; remaining probe results do not affect state transitions (but still emit metrics).
  - Recovery timeout with optional exponential backoff and cap.
  - Optional rolling-window failure rate mode (needed by RAG):
    - Config: `window_size`, `min_calls`, `failure_rate_threshold`.
    - Transition to OPEN when `min_calls` is reached and failure rate >= `failure_rate_threshold`.
    - In HALF_OPEN, probe calls count toward `success_threshold`; any failure reopens and resets the window.
    - Window resets on transition to CLOSED.
    - When rolling-window mode is enabled, `failure_threshold` does not control CLOSED->OPEN transitions.
  - `window_size` is a count of most recent calls (not time-based).
  - Optional per-call timeout for sync/async calls; timeouts count as failures and are included in rolling-window failure rate.
- `call()` / `call_async()` methods and a `@circuit_breaker(...)` decorator.
- Registry helpers: `get_or_create(name, category, config_overrides)` and `get_status()`.
  - Registry key is `(category, name)`; `name` must be namespaced as `{service}.{operation}[.{provider}]`.
  - Config resolution order: defaults < module config < `config_overrides`.
  - `config_overrides` apply only at creation time; subsequent calls must match existing config or raise `ValueError` (no silent overrides).
  - Registry is shared across workers/processes via shared storage using existing DB_Management (no new dependencies); in-memory registry is only for single-worker dev/tests.

### 8.2 Error Classification
- Support explicit `expected_exceptions`, optional `error_classifier`, and optional `result_classifier` (non-exception outcomes).
- `result_classifier` is a callable applied to the returned value: `result -> bool` where `True` means failure and `False` means success.
- By default, all exceptions count toward breaker failure thresholds.
- If `expected_exceptions` is provided, only those exception types (plus timeouts) count toward the threshold; other exceptions are raised but do not affect breaker state.
- If `error_classifier` is provided, it takes precedence and returns `failure` or `ignore` for exceptions; timeouts always count as failures.
- `result_classifier` (if provided) can mark non-exception results as failures; default is no result-based failures.
- Timeouts always count as failures and are included in rolling-window failure rate and timeout metrics.

### 8.3 Metrics
Emit standard metrics via Metrics manager:
- `circuit_breaker_state{category,service,operation}`
- `circuit_breaker_failures_total{category,service,operation,outcome}`
- `circuit_breaker_successes_total{category,service,operation}`
- `circuit_breaker_timeouts_total{category,service,operation}`
- `circuit_breaker_rejections_total{category,service,operation}`
- `circuit_breaker_trips_total{category,service,reason}`

Legacy label mapping (migration-only):
- Emit an alias where `service` is prefixed as `{category}:{service}` for the following metrics:
  - `circuit_breaker_state`
  - `circuit_breaker_failures_total`
  - `circuit_breaker_successes_total`
  - `circuit_breaker_rejections_total`
  - `circuit_breaker_trips_total`

Cardinality constraints:
- `category`, `service`, `operation`, `outcome`, and `reason` must be bounded to a small, config-defined set.
- Do not include user IDs, request IDs, URLs, or other per-request values in labels.

Provide a compatibility shim for legacy label formats during migration; remove once fully implemented (see Phase 2 definition).

### 8.4 Migration Shims
- Legacy modules re-export Infrastructure breaker with a deprecation warning.
- MCP Unified replaces inline breaker logic with the shared breaker.

## 9. Design Overview
### 9.1 Location
- `tldw_Server_API/app/core/Infrastructure/circuit_breaker.py`

### 9.2 Configuration Mapping
Map existing settings to shared config fields:
- `circuit_breaker_threshold` -> `failure_threshold`
- `circuit_breaker_timeout` -> `recovery_timeout`
- `circuit_breaker_backoff_factor` -> `backoff_factor`
- `circuit_breaker_max_timeout` -> `max_recovery_timeout`
- `half_open_requests` -> `half_open_max_calls`
- TTS legacy fields (`circuit_failure_threshold`, `circuit_recovery_timeout`, etc.) map directly.

### 9.3 Registry & Storage
- Breaker state is global (not per-user) and persisted in a shared table in the AuthNZ DB (`DATABASE_URL`) via DB_Management.
- Proposed schema (SQLite/Postgres): `category` (text), `name` (text), `state` (text), `failure_count` (int), `success_count` (int), `half_open_attempts` (int), `opened_at` (timestamp), `last_failure_at` (timestamp), `last_success_at` (timestamp), `recovery_timeout_at` (timestamp), `rolling_window` (text/json), `version` (int), `updated_at` (timestamp); unique key on `(category, name)`.
- Use optimistic locking on `version` to avoid cross-process races; updates must be compare-and-swap with retry on conflict.
- Create/migrate the table using existing DB_Management initialization hooks (no new dependencies).
- In-memory registry is acceptable only for single-worker dev/tests.

### 9.4 Concurrency Guards
- Existing concurrency gates (e.g., MCP module semaphores, Evaluations call bounds) remain outside the breaker.

## 10. Migration Plan
### Phase 0: Introduce Shared Module
- Implement Infrastructure circuit breaker with metrics and registry.

### Phase 1: Adapters and Shims
- Replace Embeddings, Evaluations, RAG, MCP, TTS, Chat, and Web Scraping breakers with shared adapter calls.
- Keep legacy imports as thin shims with warnings.
- Emit legacy metric labels only during this phase.
- Add parity tests per domain before removing legacy tests.

### Phase 2: Cleanup
- Remove legacy circuit breaker implementations and related tests.
- Update docs to point to the Infrastructure breaker.
- Remove legacy metric label shim.

Definition: "Fully implemented" means all domains are migrated to the shared breaker, parity tests are green in CI, and no legacy breaker imports are used in runtime code.

## 11. Risks & Mitigations
- Risk: Behavior differences cause subtle regressions.
  - Mitigation: define parity tests for each domain and match thresholds/timeouts.
- Risk: Metrics dashboards break due to label changes.
  - Mitigation: emit legacy labels until fully implemented.

## 12. Testing Plan
- Unit tests for state transitions, backoff, rolling-window behavior, and timeouts.
- Integration tests for each domain to confirm existing behavior.
- Metrics tests to ensure correct counters/gauges and legacy label emission.

## 13. Acceptance Criteria
- All domains use the shared breaker.
- No module defines its own circuit breaker class in runtime code.
- Consistent metrics and configuration mapping across domains.
- Parity tests cover each domain's breaker behavior.

## 14. Decisions
- Web Scraping will fully use the shared module (no lighter-weight wrapper).
- Breaker state is global (not per-user) and stored in a shared DB table.
- Timeouts count as failures and are included in rolling-window failure rate.
- HALF_OPEN allows parallel probes up to `half_open_max_calls`; any failure reopens immediately.
- Result-based failures are opt-in via `result_classifier` (default is off).

## 15. Implementation Plan
Status update (February 16, 2026): stages 1-10 are implemented; circuit breaker registry persistence and cleanup/deprecation removal are complete. Follow-on hardening delivered in `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_circuit_breaker_distributed_semantics_admin_endpoint_2026_02_16.md`:
- optimistic-lock merge/retry persistence semantics
- distributed HALF_OPEN probe lease coordination across workers
- unified RBAC-protected admin endpoint `GET /api/v1/admin/circuit-breakers`

## Stage 1: Core Breaker + Shared Registry Storage
**Goal**: Implement the Infrastructure circuit breaker with sync/async support, rolling-window mode, and shared registry persistence using existing DB_Management.
**Success Criteria**: New module compiles; breaker states and transitions match spec; registry state is shared across workers/processes with optimistic locking; DB schema/migrations are in place; in-memory registry only used for dev/tests.
**Tests**: Unit tests for state transitions, rolling-window rules, timeouts, exception classification, registry persistence, and optimistic locking; integration test simulating multi-worker updates.
**Status**: Complete

## Stage 2: Metrics + Legacy Shim
**Goal**: Wire metrics to Metrics manager and implement legacy label aliasing with cardinality constraints.
**Success Criteria**: Standard metrics emitted with required labels; legacy alias emitted only during migration; no unbounded labels.
**Tests**: Metrics unit tests for each counter/gauge and legacy alias mapping behavior.
**Status**: Complete

## Stage 3: Embeddings Migration + Parity Tests
**Goal**: Migrate Embeddings to the shared breaker with config mapping and parity tests.
**Success Criteria**: Embeddings uses shared breaker; legacy import is shim-only; parity tests cover embeddings behavior.
**Tests**: Embeddings integration tests for breaker parity and config mapping.
**Status**: Complete

## Stage 4: Evaluations Migration + Parity Tests
**Goal**: Migrate Evaluations to the shared breaker with config mapping and parity tests.
**Success Criteria**: Evaluations uses shared breaker; legacy import is shim-only; parity tests cover evaluation behavior.
**Tests**: Evaluations integration tests for breaker parity and config mapping.
**Status**: Complete

## Stage 5: RAG Migration + Parity Tests
**Goal**: Migrate RAG resilience to the shared breaker with rolling-window mode and parity tests.
**Success Criteria**: RAG uses shared breaker; legacy import is shim-only; parity tests cover rolling-window behavior.
**Tests**: RAG integration tests for rolling-window parity and config mapping.
**Status**: Complete

## Stage 6: MCP Unified Migration + Parity Tests
**Goal**: Replace MCP inline breaker logic with the shared breaker and parity tests.
**Success Criteria**: MCP uses shared breaker; legacy import is shim-only; parity tests cover module breaker behavior.
**Tests**: MCP integration tests for breaker parity and concurrency interaction.
**Status**: Complete

## Stage 7: TTS Migration + Parity Tests
**Goal**: Migrate TTS to the shared breaker with config mapping and parity tests.
**Success Criteria**: TTS uses shared breaker; legacy import is shim-only; parity tests cover TTS breaker behavior.
**Tests**: TTS integration tests for breaker parity and config mapping.
**Status**: Complete

## Stage 8: Chat Migration + Parity Tests
**Goal**: Migrate Chat provider manager to the shared breaker with config mapping and parity tests.
**Success Criteria**: Chat uses shared breaker; legacy import is shim-only; parity tests cover provider breaker behavior.
**Tests**: Chat integration tests for breaker parity and config mapping.
**Status**: Complete

## Stage 9: Web Scraping Migration + Parity Tests
**Goal**: Migrate Web Scraping to the shared breaker with config mapping and parity tests.
**Success Criteria**: Web Scraping uses shared breaker; legacy import is shim-only; parity tests cover web scraping breaker behavior.
**Tests**: Web Scraping integration tests for breaker parity and config mapping.
**Status**: Complete

## Stage 10: Cleanup + Deprecation Removal
**Goal**: Remove legacy breaker implementations, shims, and legacy metric labels after migration is complete.
**Success Criteria**: Legacy breaker shims in migrated runtime paths are removed; legacy metrics aliases are removed; docs updated.
**Tests**: Full test suite green; parity tests remain.
**Status**: Complete
