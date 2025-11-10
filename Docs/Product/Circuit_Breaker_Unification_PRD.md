Circuit Breaker Unification PRD

  - Title: Circuit Breaker Unification
  - Author: [your name]
  - Status: Draft
  - Owners: Core (Infrastructure), Embeddings, Evaluations, RAG, MCP
  - Related Code: tldw_Server_API/app/core/Embeddings/circuit_breaker.py:1, tldw_Server_API/app/core/Evaluations/circuit_breaker.py:1, tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:505,
    tldw_Server_API/app/core/RAG/rag_service/resilience.py:1, tldw_Server_API/app/core/MCP_unified/modules/base.py:242, tldw_Server_API/app/core/Chat/provider_manager.py:1

  Overview

  - Problem: Multiple, duplicative circuit breaker (CB) implementations diverge in behavior and metrics, increasing maintenance risk.
  - Unifying Principle: All are the same CircuitBreaker with different labels.
  - Goal: One unified CB in Infrastructure with per-category config, consistent metrics, and sync/async decorators. Modules inject names/labels only.

  Problem Statement

  - Duplicates and drift:
      - Embeddings CB with Prometheus metrics: tldw_Server_API/app/core/Embeddings/circuit_breaker.py:1
      - Evaluations CB with async locks, timeouts, and per-provider configs: tldw_Server_API/app/core/Evaluations/circuit_breaker.py:1
      - RAG resilience’s own CB and coordinator: tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:505, tldw_Server_API/app/core/RAG/rag_service/resilience.py:1
      - MCP base embeds CB/backoff semantics: tldw_Server_API/app/core/MCP_unified/modules/base.py:242
      - Additional duplication (noted): Chat provider CB: tldw_Server_API/app/core/Chat/provider_manager.py:1
  - Symptoms: Inconsistent states, thresholds, timeouts, backoff, and metrics across domains; redundant tests and config.

  Goals

  - Single CB implementation under Infrastructure used by Embeddings, Evaluations, RAG, MCP (and optionally Chat).
  - Consistent behavior: CLOSED/OPEN/HALF_OPEN, failure thresholds, half-open probe limits, recovery timeouts.
  - Optional modes: count threshold and rolling-window failure-rate (RAG).
  - First-class async/sync usage with decorators and call wrappers (with optional per-call timeout).
  - Unified metrics (Prometheus) with consistent labels: category, service/name, operation/outcome.
  - Backward-compatible shims and non-breaking migration of tests/config.

  Non-Goals

  - Rewriting retry/fallback/health-monitor logic (keep in their modules; integrate only via consistent CB hooks).
  - Overhauling provider selection logic or load balancing.
  - Adding new external dependencies.

  Users And Stakeholders

  - Embeddings team (provider reliability, metrics).
  - Evaluations/LLM Calls (per-provider CB configs, timeouts).
  - RAG (resilience coordinator; rolling-window option).
  - MCP Unified (module backoff semantics, concurrency guard).
  - Observability/Infra (unified metrics).

  In Scope

  - New tldw_Server_API/app/core/Infrastructure/circuit_breaker.py.
  - Config unification and adapter: Embeddings, Evaluations, RAG, MCP (and optional Chat).
  - Metrics standardization and registry.
  - Back-compat shims in legacy module paths.
  - Tests and docs updates.

  Out Of Scope

  - Changing existing retry/fallback APIs and semantics.
  - Replacing health-monitoring subsystems.

  Functional Requirements

  - Provide CircuitBreaker with:
      - States: CLOSED, OPEN, HALF_OPEN with success threshold and half-open max concurrent probes.
      - Failure policy: count threshold and optional rolling window (size + failure_rate_threshold).
      - Recovery policy: recovery timeout with optional exponential backoff (factor, max_timeout).
      - Error classification: expected_exceptions (count toward CB), unexpected errors pass through.
      - Optional per-call timeout enforcement for both sync/async calls.
  - Provide CircuitBreakerConfig with superset of fields:
      - failure_threshold, success_threshold, recovery_timeout, half_open_max_calls, expected_exceptions, timeout_seconds (per-call), window_size, failure_rate_threshold, backoff_factor, max_recovery_timeout.
  - Provide simple APIs:
      - call(func, *args, **kwargs) and call_async(func, *args, **kwargs).
      - Decorator @circuit_breaker(name=..., category=..., config=...) auto-detects sync/async.
      - Registry: get_or_create(name, category, config_overrides); status(); reset().
  - Metrics:
      - Prometheus counters/gauges: state, trips, failures, successes, rejections, timeouts.
      - Labels: category, service (name), operation (optional).
      - Safe re-registration across processes/tests.

  Non-Functional Requirements

  - Thread/async safety: locks around state transitions; no deadlocks; low contention.
  - Performance: O(1) hot-path operations; rolling-window operations amortized.
  - Observability: metrics exposed; structured state in get_status().
  - Compatibility: no breaking changes to public endpoints; shims for legacy imports.
  - Testing: >80% coverage for new module; integration tests continue to pass.

  Design Overview

  - File: tldw_Server_API/app/core/Infrastructure/circuit_breaker.py
  - Core types:
      - CircuitState (Enum)
      - CircuitBreakerConfig (dataclass)
      - CircuitBreaker (class) with state machine and optional rolling-window and backoff.
      - CircuitBreakerRegistry with thread-safe access.
      - Decorator factory circuit_breaker(...) (sync/async support).
  - Configuration resolution:
      - Accept explicit config from call site; otherwise resolve via per-category sources:
          - Embeddings: tldw_Server_API/Config_Files/embeddings_production_config.yaml (circuit_breaker block)
          - Evaluations: tldw_Server_API/Config_Files/evaluations_config.yaml (circuit_breakers.providers)
          - MCP: tldw_Server_API/Config_Files/mcp_modules.yaml (circuit_breaker_* keys)
          - RAG: defaults from RAG resilience, mapped to unified config
      - Override order: kwargs > env vars > category config > sensible defaults.
      - Key mapping table:
          - circuit_breaker_threshold -> failure_threshold
          - circuit_breaker_timeout -> recovery_timeout
          - circuit_breaker_backoff_factor -> backoff_factor
          - circuit_breaker_max_timeout -> max_recovery_timeout
          - half_open_requests -> half_open_max_calls
          - timeout/timeout_seconds -> timeout_seconds
  - Metrics:
      - Gauges: circuit_breaker_state{category,service} (0=closed,1=open,2=half_open)
      - Counters: circuit_breaker_trips_total, circuit_breaker_failures_total, circuit_breaker_successes_total, circuit_breaker_rejections_total, circuit_breaker_timeouts_total
  - Backward compatibility:
      - Keep modules exporting shims that import the Infrastructure CB and emit a deprecation warning:
          - tldw_Server_API/app/core/Embeddings/circuit_breaker.py
          - tldw_Server_API/app/core/Evaluations/circuit_breaker.py
          - tldw_Server_API/app/core/RAG/rag_service/resilience.py (CB only; keep retry/fallback/health)
          - tldw_Server_API/app/core/Chat/provider_manager.py (optional shim or direct call migration)
      - Replace MCP base’s inline logic with unified CB calls; keep its semaphore guard local.

  API Sketch

  - CircuitBreakerConfig(...)
  - CircuitBreaker(name, category, config)
      - await call_async(func, *args, **kwargs)
      - call(func, *args, **kwargs)
      - get_status() -> Dict[str, Any]
      - reset()
  - get_or_create_breaker(name, category, config_overrides=None)
  - @circuit_breaker(name, category, config_overrides=None)

  Module Integration Plan

  - Embeddings: Replace direct CircuitBreaker usage with Infrastructure CB; map config; keep Prometheus metrics through unified hooks. Update tests that import tldw_Server_API.app.core.Embeddings.circuit_breaker
    to work via shim.
  - Evaluations: Replace LLMCircuitBreaker with per-provider get_or_create_breaker(name=f"llm:{provider}", category="evaluations"); keep timeouts via per-call timeout_seconds. Preserve closed-state concurrency
    semaphore out of CB if truly needed, or enable opt-in through config.
  - RAG: Update unified_pipeline.py:505 and resilience.py to use Infrastructure CB; keep RetryPolicy/FallbackChain/HealthMonitor as-is.
  - MCP: Replace base’s internal CB counters with Infrastructure CB; map backoff fields; keep module semaphore; preserve metrics via unified labels category="mcp".
  - Chat (optional): Replace provider_manager.CircuitBreaker with unified CB or shim.

  Migration And Deletions

  - Deletions after migration (or convert to shims for 1 release):
      - tldw_Server_API/app/core/Embeddings/circuit_breaker.py
      - tldw_Server_API/app/core/Evaluations/circuit_breaker.py
      - CB portions of tldw_Server_API/app/core/RAG/rag_service/resilience.py
      - Inline CB logic in tldw_Server_API/app/core/MCP_unified/modules/base.py
      - Optional: CB in tldw_Server_API/app/core/Chat/provider_manager.py
  - Update config docs and examples to reference unified fields and mappings.

  Testing

  - Unit tests (new):
      - State transitions: thresholds, half-open probes, reset.
      - Rolling-window failure rate mode (RAG parity).
      - Backoff open-window growth and cap (MCP parity).
      - Timeout handling (Evaluations parity) for sync/async.
      - Metrics: state transitions increment expected counters/gauges.
      - Registry: idempotent get_or_create, concurrent access safety.
  - Integration tests (existing):
      - Embeddings production and unit test paths must pass unchanged (import via shim).
      - Evaluations unified tests must pass; provider configs honored.
      - RAG unified pipeline resiliency path preserved.
      - MCP module operations respect open/half-open and backoff.

  Risks And Mitigations

  - Behavior drift due to policy differences (count vs window): expose both modes; default per-category to match prior behavior; add explicit mappings.
  - Metric cardinality growth (labels): constrain label set to category, service, optional operation.
  - Backoff interaction with timeouts: document mapping and defaults; add tests mirroring MCP behavior.
  - Concurrency limits baked into CB: keep concurrency guards outside CB unless explicitly configured.

  Rollout Plan

  - Phase 1: Implement Infrastructure CB + metrics + registry; add adapters/shims; land tests and docs; no module behavior change.
  - Phase 2: Migrate modules sequentially (Embeddings → Evaluations → RAG → MCP → Chat). Update config mapping and tests per module.
  - Phase 3: Remove duplicate implementations; keep import shims for one release cycle; announce deprecation in release notes.

  Acceptance Criteria

  - Single, shared CB used by Embeddings, Evaluations, RAG, MCP (and optionally Chat).
  - All tests pass: python -m pytest -v and coverage unchanged or improved.
  - Metrics exported under unified names with expected labels; no duplicate metric registration errors.
  - Config overrides resolve correctly from each category’s existing config files.
  - No API regressions; same error semantics for open/rejected calls.

  Open Questions

  - Should CB own per-call timeout universally, or leave it to call sites with a helper? (Current plan: optional timeout_seconds in CB wrapper to preserve Evaluations/MCP behavior.)
  - Do we migrate Chat provider CB now or backlog it?
  - Do we want per-category defaults in code, or only in config files?

  Timeline

  - Phase 1: 1–2 days (Infra CB, metrics, basic tests, shims).
  - Phase 2: 2–4 days (module migrations + tests).
  - Phase 3: 0.5 day (cleanup, docs, deprecations).

  Appendix: File References

  - Embeddings CB: tldw_Server_API/app/core/Embeddings/circuit_breaker.py:1
  - Evaluations CB: tldw_Server_API/app/core/Evaluations/circuit_breaker.py:1
  - RAG use: tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:505
  - RAG CB/coordinator: tldw_Server_API/app/core/RAG/rag_service/resilience.py:1
  - MCP inline CB: tldw_Server_API/app/core/MCP_unified/modules/base.py:242
  - Chat CB (optional): tldw_Server_API/app/core/Chat/provider_manager.py:1
  - Configs:
      - tldw_Server_API/Config_Files/embeddings_production_config.yaml:150
      - tldw_Server_API/Config_Files/evaluations_config.yaml:80
      - tldw_Server_API/Config_Files/mcp_modules.yaml:12
