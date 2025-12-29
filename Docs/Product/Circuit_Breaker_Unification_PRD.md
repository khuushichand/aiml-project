Circuit Breaker Unification PRD

  - Title: Circuit Breaker Unification
  - Author: [your name]
  - Status: Draft
  - Owners: Core (Infrastructure), Embeddings, Evaluations, RAG, MCP, TTS
  - Related Code: tldw_Server_API/app/core/Embeddings/circuit_breaker.py:1, tldw_Server_API/app/core/Evaluations/circuit_breaker.py:1, tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:505,
    tldw_Server_API/app/core/RAG/rag_service/resilience.py:1, tldw_Server_API/app/core/MCP_unified/modules/base.py:242, tldw_Server_API/app/core/Chat/provider_manager.py:1,
    tldw_Server_API/app/core/TTS/circuit_breaker.py:1

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
      - TTS CB with backoff/health monitoring: tldw_Server_API/app/core/TTS/circuit_breaker.py:1
      - Additional duplication (noted): Chat provider CB: tldw_Server_API/app/core/Chat/provider_manager.py:1
  - Symptoms: Inconsistent states, thresholds, timeouts, backoff, and metrics across domains; redundant tests and config.

  Goals

  - Single CB implementation under Infrastructure used by Embeddings, Evaluations, RAG, MCP, TTS (and optionally Chat).
  - Consistent behavior: CLOSED/OPEN/HALF_OPEN, failure thresholds, half-open probe limits, recovery timeouts.
  - Optional modes: count threshold and rolling-window failure-rate (RAG).
  - First-class async/sync usage with decorators and call wrappers (with optional per-call timeout).
  - Unified metrics registered via Metrics subsystem (Metrics manager) with consistent labels and compatibility shims for legacy dashboards.
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
  - Config unification and adapter: Embeddings, Evaluations, RAG, MCP, TTS (and optional Chat).
  - Metrics standardization via Metrics subsystem (Metrics manager) and registry.
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
      - Error classification accepts exception classes or string names resolved via per-category registry; optional error_classifier hook for TTS error categories.
      - Optional per-call timeout enforcement for both sync/async calls.
      - Timeout semantics: timeout_seconds is per-call; recovery_timeout controls open -> half-open.
  - Provide CircuitBreakerConfig with superset of fields:
      - failure_threshold, success_threshold, recovery_timeout, half_open_max_calls, expected_exceptions, timeout_seconds (per-call), window_size, failure_rate_threshold, backoff_factor, max_recovery_timeout.
  - Provide simple APIs:
      - call(func, *args, **kwargs) and call_async(func, *args, **kwargs).
      - Decorator @circuit_breaker(name=..., category=..., config=...) auto-detects sync/async.
      - Registry: get_or_create(name, category, config_overrides); status(); reset().
  - Metrics:
      - Registered via Metrics subsystem (MetricsRegistry) as the single registry.
      - Metrics names/labels:
          - circuit_breaker_state{category,service,operation}
          - circuit_breaker_failures_total{category,service,operation,outcome}
          - circuit_breaker_successes_total{category,service,operation}
          - circuit_breaker_rejections_total{category,service,operation}
          - circuit_breaker_trips_total{category,service,reason}
      - Legacy shim: for one release, MetricsRegistry also emits circuit breaker metrics with legacy label values (e.g., service="category:name") to keep existing dashboards working.

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
          - Embeddings: tldw_Server_API/Config_Files/embeddings_production_config.yaml:161 (retry.circuit_breaker block)
          - Evaluations: tldw_Server_API/Config_Files/evaluations_config.yaml:87 (circuit_breakers.providers)
          - MCP: tldw_Server_API/Config_Files/mcp_modules.yaml:12 (circuit_breaker_* keys)
          - RAG: defaults from RAG resilience, mapped to unified config
          - TTS: tldw_Server_API/Config_Files/tts_providers_config.yaml (planned; add a circuit_breaker block for providers)
      - Decision (required): choose one TTS config source before implementation:
          - Option A: add circuit_* keys to tldw_Server_API/Config_Files/config.txt [TTS-Settings]
          - Option B: implement TTS circuit settings exclusively in the new tldw_Server_API/Config_Files/tts_providers_config.yaml block
      - Override order: kwargs > env vars > category config > sensible defaults.
      - Key mapping table:
          - circuit_breaker_threshold -> failure_threshold
          - circuit_breaker_timeout -> recovery_timeout
          - circuit_breaker_backoff_factor -> backoff_factor
          - circuit_breaker_max_timeout -> max_recovery_timeout
          - half_open_requests -> half_open_max_calls
          - timeout_seconds -> timeout_seconds
          - recovery_timeout_seconds -> recovery_timeout
          - timeout -> recovery_timeout (RAG legacy)
          - circuit_failure_threshold -> failure_threshold (TTS legacy)
          - circuit_recovery_timeout -> recovery_timeout (TTS legacy)
          - circuit_half_open_calls -> half_open_max_calls (TTS legacy)
          - circuit_success_threshold -> success_threshold (TTS legacy)
          - {provider}_circuit_* -> per-provider overrides (TTS legacy)
  - Timeout semantics:
      - timeout_seconds (or call_timeout_seconds alias) is per-call.
      - recovery_timeout (or recovery_timeout_seconds/circuit_breaker_timeout) controls open -> half-open.
  - Concurrency guards:
      - Keep module semaphores outside CB (Evaluations closed-state gate, MCP module semaphore, TTS health/monitoring).
      - Optional Infrastructure ConcurrencyGate helper to preserve Evaluations gating behavior.
  - Error classification:
      - expected_exceptions accepts types or string names; resolve via registry and module maps.
      - TTS error categories map to exception classes (e.g., TTSTimeoutError, TTSNetworkError) for counting.
  - Metrics:
      - Registered via Metrics subsystem (Metrics manager) to avoid duplicate Prometheus registrations.
      - Gauges: circuit_breaker_state{category,service,operation} (0=closed,1=open,2=half_open)
      - Counters: circuit_breaker_trips_total{category,service,reason}, circuit_breaker_failures_total{category,service,operation,outcome}, circuit_breaker_successes_total{category,service,operation}, circuit_breaker_rejections_total{category,service,operation}, circuit_breaker_timeouts_total{category,service,operation}
      - Legacy compatibility: emit circuit_breaker_state{service} and circuit_breaker_failures_total{service,reason} for one release via Metrics manager mapping.
  - Backward compatibility:
      - Keep modules exporting shims that import the Infrastructure CB and emit a deprecation warning:
          - tldw_Server_API/app/core/Embeddings/circuit_breaker.py
          - tldw_Server_API/app/core/Evaluations/circuit_breaker.py
          - tldw_Server_API/app/core/RAG/rag_service/resilience.py (CB only; keep retry/fallback/health)
          - tldw_Server_API/app/core/Chat/provider_manager.py (optional shim or direct call migration)
          - tldw_Server_API/app/core/TTS/circuit_breaker.py (CB core shim; keep manager API)
      - Replace MCP base’s inline logic with unified CB calls; keep its semaphore guard local.
      - Remove module-level Prometheus registrations for circuit_breaker_* in favor of Metrics manager updates.

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

  - Embeddings: Replace direct CircuitBreaker usage with Infrastructure CB; map config from retry.circuit_breaker; update metrics via Metrics manager. Update tests that import tldw_Server_API.app.core.Embeddings.circuit_breaker
    to work via shim.
  - Evaluations: Replace LLMCircuitBreaker with per-provider get_or_create_breaker(name=f"llm:{provider}", category="evaluations"); keep timeouts via per-call timeout_seconds. Preserve closed-state concurrency
    semaphore outside CB via a ConcurrencyGate helper or existing semaphore. Update evaluation metrics to use Metrics manager.
  - RAG: Update unified_pipeline.py:505 and resilience.py to use Infrastructure CB; map timeout -> recovery_timeout; keep RetryPolicy/FallbackChain/HealthMonitor as-is.
  - MCP: Replace base’s internal CB counters with Infrastructure CB; map backoff fields; keep module semaphore; preserve metrics via unified labels category="mcp".
  - TTS: Replace CircuitBreaker core with Infrastructure CB; keep CircuitBreakerManager and health monitoring/backoff scheduling. Map TTS error categories to expected_exceptions/error_classifier. Load config from config.txt [TTS-Settings]
    and add circuit_breaker block to tts_providers_config.yaml.
  - Chat (optional): Replace provider_manager.CircuitBreaker with unified CB or shim.

  Migration And Deletions

  - Deletions after migration (or convert to shims for 1 release):
      - tldw_Server_API/app/core/Embeddings/circuit_breaker.py
      - tldw_Server_API/app/core/Evaluations/circuit_breaker.py
      - CB portions of tldw_Server_API/app/core/RAG/rag_service/resilience.py
      - Inline CB logic in tldw_Server_API/app/core/MCP_unified/modules/base.py
      - tldw_Server_API/app/core/TTS/circuit_breaker.py (CB core; keep manager interface)
      - Optional: CB in tldw_Server_API/app/core/Chat/provider_manager.py
  - Update config docs and examples to reference unified fields and mappings.

  Testing

  - Unit tests (new):
      - State transitions: thresholds, half-open probes, reset.
      - Rolling-window failure rate mode (RAG parity).
      - Backoff open-window growth and cap (MCP parity).
      - Timeout handling (Evaluations parity) for sync/async.
      - Metrics: state transitions increment expected counters/gauges via Metrics manager; legacy label shim emits expected values.
      - Registry: idempotent get_or_create, concurrent access safety.
      - Error classification: string-to-exception resolution; TTS error category mapping.
  - Integration tests (existing):
      - Embeddings production and unit test paths must pass unchanged (import via shim).
      - Evaluations unified tests must pass; provider configs honored.
      - RAG unified pipeline resiliency path preserved.
      - MCP module operations respect open/half-open and backoff.

  Risks And Mitigations

  - Behavior drift due to policy differences (count vs window): expose both modes; default per-category to match prior behavior; add explicit mappings.
  - Metric label collisions across modules: centralize registration in Metrics manager; remove per-module registrations; provide one-release compatibility shims.
  - Metric cardinality growth (labels): constrain label set to category, service, optional operation.
  - Backoff interaction with timeouts: document mapping and defaults; add tests mirroring MCP behavior.
  - Concurrency limits baked into CB: keep concurrency guards outside CB unless explicitly configured.
  - Config mapping gaps (TTS/Embeddings): explicitly map config keys; add TTS circuit_breaker block support in tts_providers_config.yaml.
  - Exception mapping drift: maintain per-category exception maps and tests to avoid silent behavior changes.

  Rollout Plan

  - Phase 1: Implement Infrastructure CB + Metrics manager integration + registry; add adapters/shims; land tests and docs; no module behavior change.
  - Phase 2: Migrate modules sequentially (Embeddings → Evaluations → RAG → MCP → TTS → Chat). Update config mapping and tests per module.
  - Phase 3: Remove duplicate implementations; keep import shims for one release cycle; announce deprecation in release notes.

  Acceptance Criteria

  - Single, shared CB used by Embeddings, Evaluations, RAG, MCP, TTS (and optionally Chat).
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
  - TTS CB: tldw_Server_API/app/core/TTS/circuit_breaker.py:1
  - Configs:
      - tldw_Server_API/Config_Files/embeddings_production_config.yaml:141
      - tldw_Server_API/Config_Files/evaluations_config.yaml:87
      - tldw_Server_API/Config_Files/mcp_modules.yaml:12
      - tldw_Server_API/Config_Files/config.txt:811
      - tldw_Server_API/Config_Files/tts_providers_config.yaml:1

  Implementation Plan

  ## Stage 1: Infrastructure CB + Metrics Schema
  **Goal**: Implement unified CB in Infrastructure with Metrics manager registration and explicit timeout/error semantics.
  **Success Criteria**: Infrastructure CB supports count and rolling-window modes, backoff, timeout_seconds, and error classification; Metrics manager exports canonical circuit_breaker_* metrics with category/service labels.
  **Tests**: Unit tests for state transitions, timeouts, rolling-window failure rate, backoff growth/cap, metrics updates.
  **Status**: Not Started

  ## Stage 2: Shims + Metrics Compatibility
  **Goal**: Add shims in legacy modules and stop per-module Prometheus registrations to avoid label collisions.
  **Success Criteria**: Embeddings/Evaluations/RAG/MCP/TTS/Chat shims import Infrastructure CB, emit deprecation warnings, and update Metrics manager; legacy metric labels are exported via compatibility shim.
  **Tests**: Unit tests for shim imports; metrics registry tests to ensure no duplicate registration errors.
  **Status**: Not Started

  ## Stage 3: Module Migrations (Behavior Parity)
  **Goal**: Migrate Embeddings, Evaluations, RAG, MCP, and TTS to the unified CB with preserved concurrency and timeout behaviors.
  **Success Criteria**: Existing module integration tests pass; RAG timeout maps to recovery_timeout; Evaluations keeps closed-state concurrency gate; MCP backoff matches prior behavior; TTS error categorization preserved.
  **Tests**: Integration tests for embeddings, evaluations, rag, mcp, tts; targeted regression tests for concurrency and timeouts.
  **Status**: Not Started

  ## Stage 4: Cleanup + Docs
  **Goal**: Remove legacy CB implementations after one release and update docs/config examples.
  **Success Criteria**: Legacy CB files removed or reduced to shims, docs updated to unified config keys, release notes include deprecations.
  **Tests**: Full test suite (python -m pytest -v) and lint/format checks if applicable.
  **Status**: Not Started
