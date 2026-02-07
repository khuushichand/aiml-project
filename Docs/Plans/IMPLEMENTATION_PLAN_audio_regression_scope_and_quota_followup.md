## Stage 1: Failure Reproduction and Triage
**Goal**: Reproduce current Audio regressions and isolate shared root causes.
**Success Criteria**:
- Failing tests are reproducible locally with clear failure classes.
- Shared auth/quota regression points identified.
**Tests**:
- Targeted pytest invocations for failing Audio tests.
**Status**: Complete

## Stage 2: Auth Scope Compatibility Fix
**Goal**: Restore single-user API key compatibility inside token-scope dependency checks.
**Success Criteria**:
- `require_token_scope` accepts configured single-user API key path (including IP allowlist checks).
- Audio HTTP endpoint tests no longer fail with `401 Could not validate credentials` due scope dependency.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Audio/test_audio_chat_endpoint.py`
- `python -m pytest -q tldw_Server_API/tests/Audio/test_audio_transcriptions_adapter_path.py`
**Status**: Complete

## Stage 3: Quota/WS Regression Alignment
**Goal**: Fix remaining quota and WS failure paths after auth compatibility is restored.
**Success Criteria**:
- Quota-focused HTTP/WS tests pass with expected payload/close semantics.
- Fail-open runtime and compatibility tests pass consistently.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Audio/test_http_quota_validation.py`
- `python -m pytest -q tldw_Server_API/tests/Audio/test_ws_failopen_runtime.py`
- `python -m pytest -q tldw_Server_API/tests/Audio/test_ws_quota.py`
- `python -m pytest -q tldw_Server_API/tests/Audio/test_ws_quota_close_toggle.py`
- `python -m pytest -q tldw_Server_API/tests/Audio/test_ws_quota_compat_and_close.py`
**Status**: Complete

## Stage 4: Regression Verification and Closeout
**Goal**: Re-run affected Audio tests as a group and confirm no Stage 4 voice-chat regressions.
**Success Criteria**:
- Previously failing Audio tests are green.
- Stage 4 WS persistence tests remain green.
**Tests**:
- `./.venv/bin/python -m pytest -q tldw_Server_API/tests/Audio/test_audio_chat_endpoint.py tldw_Server_API/tests/Audio/test_audio_transcriptions_adapter_path.py tldw_Server_API/tests/Audio/test_http_quota_validation.py tldw_Server_API/tests/Audio/test_ws_failopen_runtime.py tldw_Server_API/tests/Audio/test_ws_quota.py tldw_Server_API/tests/Audio/test_ws_quota_close_toggle.py tldw_Server_API/tests/Audio/test_ws_quota_compat_and_close.py tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py tldw_Server_API/tests/Audio/test_ws_diarization_persistence_status.py`
- Result: `17 passed` (Python `3.11.13`, pytest `9.0.2`).
**Status**: Complete

## Stage 5: Final Hardening and PR Readiness
**Goal**: Execute a final confidence sweep across Audio tests, align documentation, and produce a PR-ready closure summary.
**Success Criteria**:
- Full Audio test suite passes (or failures are isolated and documented with root-cause notes).
- Voice chat streaming docs and compatibility notes reflect the final implementation behavior.
- A concise PR summary is prepared with scope, risks, and validation evidence.
**Tests**:
- `./.venv/bin/python -m pytest -q tldw_Server_API/tests/Audio/`
- Result: `171 passed, 4 skipped` (Python `3.11.13`, pytest `9.0.2`).
- Regression confirmation: `./.venv/bin/python -m pytest -q tldw_Server_API/tests/Audio/test_ws_concurrent_streams.py tldw_Server_API/tests/Audio/test_ws_failopen_runtime.py tldw_Server_API/tests/Audio/test_ws_idle_metrics_audio.py tldw_Server_API/tests/Audio/test_ws_invalid_json_error.py tldw_Server_API/tests/Audio/test_ws_metrics_audio.py tldw_Server_API/tests/Audio/test_ws_pings_audio.py tldw_Server_API/tests/Audio/test_ws_quota.py tldw_Server_API/tests/Audio/test_ws_quota_close_toggle.py tldw_Server_API/tests/Audio/test_ws_quota_compat_and_close.py` -> `11 passed`.
**PR Summary (Stage 5 Closeout)**:
- Fixed WS startup fragility in `/api/v1/audio/stream/transcribe`: Nemo availability probing now degrades to Whisper on `ImportError` instead of aborting the connection path.
- Confirmed full Audio suite stability after fix and prior Stage 2-4 changes.
- Updated protocol docs to capture the fail-safe fallback behavior.
**Status**: Complete
