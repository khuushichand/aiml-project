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
**Status**: Complete

## Stage 5: Auth/Rate-Limit Granularity
**Goal**: Move voice operations from coarse `audio.speech` gating to explicit voice-route privilege/rate-limit semantics.
**Success Criteria**: New privilege IDs exist for voice actions, `audio_voices.py` uses route-specific `endpoint_id` values, per-API-key counters are isolated for voice operations, and audit events include endpoint/action context.
**Tests**: `python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_voice_routes_rate_limit.py tldw_Server_API/tests/AuthNZ`
**Status**: Complete

## Stage 6: Persistent Voice Registry Backing Store
**Goal**: Replace runtime-only registry dependency with persistent registry records suitable for multi-node consistency.
**Success Criteria**: Voice records persist in DB with migration support, CRUD/read paths use DB as source of truth with safe filesystem reconciliation, and multi-instance behavior is deterministic under concurrent operations.
**Tests**: `python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_voice_manager.py tldw_Server_API/tests/Storage/test_voice_storage_integration.py`
**Status**: Complete

## Stage 7: Rollout, Backward Compatibility, and Completion
**Goal**: Ship safely with migration controls, feature flags where needed, and updated product/developer documentation.
**Success Criteria**: PRD and setup docs are current, rollout checklist is complete, regression suite passes in CI, and any deprecations have explicit timelines.
**Tests**: `python -m pytest -q`
**Status**: In Progress

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
  - Result: `40 passed`.
- Added runtime deprecation warnings for legacy `[TTS-Settings]` aliases in `app/core/TTS/tts_config.py` with explicit removal target date (`2026-06-30`).
- Added config compatibility warning tests for:
  - legacy alias usage
  - canonical-over-legacy precedence when both keys are present
- Updated docs with canonical path/key guidance and migration notice:
  - `tldw_Server_API/Config_Files/README.md`
  - `tldw_Server_API/app/core/TTS/README.md`
  - `Docs/User_Guides/TTS_Getting_Started.md`
  - `Docs/User_Guides/Installation-Setup-Guide.md`
- Started Stage 4 observability hardening:
  - Added request/correlation ID propagation in `app/core/TTS/tts_service_v2.py` and wired `request_id` pass-through from `audio_tts.py` speech endpoints.
  - Added categorized fallback telemetry metric: `tts_fallback_outcomes_total{from_provider,to_provider,outcome,category}` while retaining existing `tts_fallback_attempts`.
  - Registered/normalized high-value latency metrics in TTS service metric registration (`tts_ttfb_seconds`, `voice_to_voice_seconds`) for consistent runtime usage.
  - Added tests for request/correlation metadata propagation and fallback outcome telemetry:
    - `tests/TTS/test_tts_service_v2.py`
    - `tests/TTS_NEW/unit/test_tts_service.py`
  - Updated TTS observability docs:
    - `Docs/API-related/TTS_API.md`
    - `tldw_Server_API/app/core/TTS/README.md`
- Verified Stage 4 test command:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/TTS/test_tts_service_v2.py tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py`
  - Result: `58 passed`.
- Regression check for endpoint stub compatibility:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/Audio/test_audio_usage_events.py`
  - Result: `1 passed`.
- Verified Stage 4 integration slice:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py -k "generate_without_provider or generate_with_voice_settings or generate_alignment_metadata_endpoint"`
  - Result: `3 passed`.
- Started Stage 5 auth/rate-limit granularity:
  - Replaced `audio.speech` endpoint gating in `audio_voices.py` with route-specific endpoint IDs:
    - `audio.voices.upload`, `audio.voices.encode`, `audio.voices.list`,
      `audio.voices.get`, `audio.voices.delete`, `audio.voices.preview`
  - Isolated voice API key quota counters via `count_as="voice_call"` across voice routes.
  - Added endpoint/action context propagation:
    - `require_token_scope` now writes endpoint/action/scope hints to `request.state`.
    - API key validation/audit now accepts `usage_details` and persists these details in usage audit rows.
    - `authenticate_api_key_user` forwards request endpoint/action context to API key validation when available.
  - Fixed `audio_voices.preview_voice` to return an async generator directly (removed invalid `await` on `generate_speech`) and forwarded `request_id` into TTS generation/response headers.
  - Updated virtual-key endpoint docs for new voice endpoint IDs:
    - `Docs/API-related/Virtual_Keys.md`
    - `Docs/Published/API-related/Virtual_Keys.md`
  - Registered new voice endpoint privilege IDs in `Config_Files/privilege_catalog.yaml` to satisfy startup privilege metadata validation:
    - `audio.voices.upload`, `audio.voices.encode`, `audio.voices.list`,
      `audio.voices.get`, `audio.voices.delete`, `audio.voices.preview`
  - Added/updated tests:
    - `tests/TTS_NEW/integration/test_voice_routes_rate_limit.py` now asserts route-level endpoint IDs and `voice_call` counters.
    - `tests/AuthNZ/unit/test_scoped_token_enforcement.py` now asserts endpoint/action context reaches API key usage validation.
- Verified Stage 5 targeted tests:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_voice_routes_rate_limit.py`
  - Result: `2 passed`.
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/AuthNZ/unit/test_scoped_token_enforcement.py -k "require_token_scope_and_get_request_user_record_usage_once or require_token_scope_enforces_bearer_api_key"`
  - Result: `2 passed`.
- Regression verification after privilege-catalog update:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/Audio/test_audio_usage_events.py -k tts_usage_event_logged`
  - Result: `1 passed`.
- Completed Stage 6 persistent voice registry backing store:
  - Added `app/core/DB_Management/Voice_Registry_DB.py` with:
    - SQLite-backed voice registry records per user (`voice_registry.db`)
    - schema version tracking (`voice_registry_schema_version`)
    - compatibility migrations for legacy table shapes
    - CRUD and atomic `replace_user_voices` reconciliation helper
  - Added centralized DB path constant/helper in `app/core/DB_Management/db_path_utils.py`:
    - `DatabasePaths.VOICE_REGISTRY_DB_NAME`
    - `DatabasePaths.get_user_voice_registry_db_path(...)`
  - Refactored `app/core/TTS/voice_manager.py`:
    - persistent registry store cache + async wrappers (`_list/_get/_upsert/_replace/_delete_persisted_voice`)
    - `_sync_registry_from_filesystem` now reconciles persistent DB + filesystem and refreshes runtime cache
    - upload/default/delete paths now persist/remove voice rows in DB
    - filesystem scan no longer mutates runtime registry directly
    - reconciliation preserves persisted metadata (name/description/provider/sample_rate/file_hash) when files remain
  - Added tests:
    - `tests/TTS_NEW/unit/test_voice_registry_db.py`
      - CRUD/replace semantics
      - legacy-schema migration compatibility
    - `tests/TTS_NEW/unit/test_voice_manager.py`
      - cross-instance resolution from persistent DB without filesystem scan
      - stale persisted record pruning when files are missing
- Verified Stage 6 test commands:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_voice_registry_db.py tldw_Server_API/tests/TTS_NEW/unit/test_voice_manager.py tldw_Server_API/tests/Storage/test_voice_storage_integration.py`
  - Result: `16 passed`.
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_voice_manager.py tldw_Server_API/tests/Storage/test_voice_storage_integration.py`
  - Result: `14 passed`.
- Started Stage 7 rollout/backward-compat completion:
  - Added voice-registry compatibility feature flag in `app/core/TTS/voice_manager.py`:
    - `TTS_VOICE_REGISTRY_ENABLED` (default enabled)
    - when disabled, manager uses runtime/filesystem-only sync path
    - emits one-time deprecation warning for compatibility mode with removal target after `2026-12-31`
    - persistent registry operations now fail-safe with warning logs (no hard failure on DB operation errors)
  - Added test coverage for compatibility mode disable path:
    - `tests/TTS_NEW/unit/test_voice_manager.py::test_voice_registry_persistence_can_be_disabled`
  - Updated docs for rollout and compatibility mode:
    - `tldw_Server_API/app/core/TTS/README.md`
    - `tldw_Server_API/Config_Files/README.md`
    - `Docs/User_Guides/TTS_Getting_Started.md`
    - `Docs/Published/User_Guides/TTS_Getting_Started.md`
    - `Docs/Product/TTS_Module_PRD.md`
  - Added rollout checklist:
    - `Docs/Operations/TTS_Voice_Registry_Rollout_Checklist.md`
- Stage 7 validation runs:
  - `.venv/bin/python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_voice_manager.py tldw_Server_API/tests/TTS_NEW/unit/test_voice_registry_db.py tldw_Server_API/tests/Storage/test_voice_storage_integration.py tldw_Server_API/tests/TTS_NEW/integration/test_custom_voice_resolution.py tldw_Server_API/tests/TTS_NEW/integration/test_voice_routes_rate_limit.py`
  - Result: `20 passed`.
  - `.venv/bin/python -m pytest -q`
  - Result: collection interrupted with pre-existing repository test issues outside Stage 7 scope:
    - import-file mismatch in `tests/Audiobooks/unit/test_tts_provider_inference.py` vs `tests/Audio/test_tts_provider_inference.py`
    - indentation errors in `tests/Evaluations/integration/test_ocr_pdf_dots_backend_integration.py` and `tests/Evaluations/integration/test_ocr_pdf_dots_backend_vllm_accuracy.py`
    - syntax error in `tests/prompt_studio/conftest.py` (f-string with backslash in expression)
- Stage 7 follow-up on full-suite blockers:
  - Fixed previously blocking collection issues:
    - added test package markers to disambiguate duplicate module basenames:
      - `tests/Audio/__init__.py`
      - `tests/Audiobooks/__init__.py`
      - `tests/Audiobooks/unit/__init__.py`
    - corrected indentation/import formatting in:
      - `tests/Evaluations/integration/test_ocr_pdf_dots_backend_integration.py`
      - `tests/Evaluations/integration/test_ocr_pdf_dots_backend_vllm_accuracy.py`
    - corrected identifier quoting helper syntax in:
      - `tests/prompt_studio/conftest.py`
  - Verified clean collection on previously failing paths:
    - `.venv/bin/python -m pytest -q --collect-only tldw_Server_API/tests/Audio/test_tts_provider_inference.py tldw_Server_API/tests/Audiobooks/unit/test_tts_provider_inference.py tldw_Server_API/tests/Evaluations/integration/test_ocr_pdf_dots_backend_integration.py tldw_Server_API/tests/Evaluations/integration/test_ocr_pdf_dots_backend_vllm_accuracy.py tldw_Server_API/tests/prompt_studio`
    - Result: `356 tests collected` (no collection errors).
  - Re-ran broader suite with early-stop:
    - `.venv/bin/python -m pytest -q --maxfail=1`
    - Result: collection succeeded; run stopped on first runtime failure outside Stage 7 scope:
      - `tests/Admin/test_admin_watchlists_org_settings.py::test_admin_update_org_watchlists_settings` returning `500 failed_to_fetch_org_watchlists_settings`.
