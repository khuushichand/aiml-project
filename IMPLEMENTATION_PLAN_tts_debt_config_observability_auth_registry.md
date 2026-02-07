## Stage 1: Baseline & Design Decisions
**Goal**: Lock scope, ownership, and sequencing across testing debt, config consolidation, observability, auth granularity, and persistent registry work.
**Success Criteria**: Agreed design decisions for canonical config source, trace/metric schema, privilege model granularity, and registry persistence approach.
**Tests**: N/A (design stage).
**Status**: In Progress

## Stage 2: TTS Test Debt Closure
**Goal**: Eliminate open testing debt for validation edge cases, resource manager/circuit breaker behavior, and provider smoke coverage.
**Success Criteria**: New tests cover dangerous input validation paths, provider-specific limits, resource manager bounds, circuit breaker transitions, and smoke contracts for key providers.
**Tests**: `python -m pytest -q tldw_Server_API/tests/TTS tldw_Server_API/tests/TTS_NEW`
**Status**: In Progress

## Stage 3: Config Consolidation (YAML vs config.txt)
**Goal**: Remove duplication ambiguity by defining a single canonical TTS config model with explicit precedence rules and compatibility mapping.
**Success Criteria**: Loader enforces schema validation, precedence is documented and test-verified, compatibility shim for legacy `config.txt` is deterministic, and migration/deprecation notices are in docs.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Config/test_module_yaml_integration.py tldw_Server_API/tests/Config/test_effective_config_api.py tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py`
**Status**: In Progress

## Stage 4: Observability & Tracing Hardening
**Goal**: Close TTS observability debt with structured tracing and provider/fallback diagnostics.
**Success Criteria**: Request-level correlation IDs propagate through TTS/voice flows, fallback outcomes are categorized, high-value metrics and logs are emitted consistently, and dashboards/alerts are documented.
**Tests**: `python -m pytest -q tldw_Server_API/tests/TTS/test_tts_service_v2.py tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py`
**Status**: Not Started

## Stage 5: Auth/Rate-Limit Granularity
**Goal**: Move voice operations from coarse `audio.speech` gating to explicit voice-route privilege/rate-limit semantics.
**Success Criteria**: New privilege IDs exist for voice actions, `audio_voices.py` uses route-specific `endpoint_id` values, per-API-key counters are isolated for voice operations, and audit events include endpoint/action context.
**Tests**: `python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_voice_routes_rate_limit.py tldw_Server_API/tests/AuthNZ`
**Status**: Not Started

## Stage 6: Persistent Voice Registry Backing Store
**Goal**: Replace runtime-only registry dependency with persistent registry records suitable for multi-node consistency.
**Success Criteria**: Voice records persist in DB with migration support, CRUD/read paths use DB as source of truth with safe filesystem reconciliation, and multi-instance behavior is deterministic under concurrent operations.
**Tests**: `python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_voice_manager.py tldw_Server_API/tests/Storage/test_voice_storage_integration.py`
**Status**: Not Started

## Stage 7: Rollout, Backward Compatibility, and Completion
**Goal**: Ship safely with migration controls, feature flags where needed, and updated product/developer documentation.
**Success Criteria**: PRD and setup docs are current, rollout checklist is complete, regression suite passes in CI, and any deprecations have explicit timelines.
**Tests**: `python -m pytest -q`
**Status**: Not Started

---

## Progress Log

### 2026-02-07
- Stage 2 baseline is green again after fixing TTS/TTS_NEW regressions and a collection-blocking indentation error in `tests/TTS_NEW/integration/test_audio_auth.py`.
- Verified Stage 2 command:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/TTS tldw_Server_API/tests/TTS_NEW`
  - Result: `526 passed, 21 skipped, 1 xfailed, 1 xpassed`.
- Started Stage 3 compatibility shim work in `app/core/TTS/tts_config.py`:
  - Added deterministic key alias handling for config.txt `[TTS-Settings]` values (`default_provider/default_tts_provider`, `default_voice/default_tts_voice`, `default_speed/default_tts_speed`, `local_device/local_tts_device/tts_device`).
  - Added tests to validate legacy alias mapping and deterministic precedence in `tests/Config/test_module_yaml_integration.py`.
- Verified Stage 3 slice:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/Config/test_module_yaml_integration.py tldw_Server_API/tests/Config/test_effective_config_api.py tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py`
  - Result: `38 passed`.
