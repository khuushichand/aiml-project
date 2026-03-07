# Provider Probe Logging and Scheduler Dedup Implementation Plan

## Stage 1: Add Regression Tests (Red)
**Goal**: Capture current bugs as failing tests before implementation.
**Success Criteria**:
- Access-log middleware test asserts uppercase Loguru level names.
- SessionManager tests assert no inline cleanup scheduler by default and fallback scheduling when AuthNZ scheduler is disabled.
- Google tokenizer adapter tests assert query-param API key fallback is opt-in and disabled by default.
**Tests**:
- `tldw_Server_API/tests/Logging/test_access_log_json.py`
- `tldw_Server_API/tests/AuthNZ/unit/test_session_manager_scheduler_dedup.py`
- `tldw_Server_API/tests/Writing/test_tokenizer_resolver_unit.py`
**Status**: Complete

## Stage 2: Implement Fixes (Green)
**Goal**: Apply minimal code changes to satisfy the new regression tests.
**Success Criteria**:
- AccessLogMiddleware emits uppercase levels (`INFO`/`WARNING`).
- SessionManager no longer schedules duplicate cleanup in normal startup path; inline scheduler only runs in explicit fallback mode.
- Google tokenizer query-param key fallback is gated behind explicit opt-in env configuration to prevent secret leakage in URLs by default.
**Tests**:
- Re-run stage 1 tests until all pass.
**Status**: Complete

## Stage 3: Verify and Security Scan
**Goal**: Validate touched scope and run required security checks.
**Success Criteria**:
- Focused pytest targets pass for modified files.
- Bandit run completes for touched modules/tests scope with no new issues in changed code.
**Tests**:
- `python -m pytest -v` on targeted files
- `python -m bandit -r <touched_paths> -f json -o /tmp/bandit_provider_probe_logging_scheduler.json`
**Status**: Complete
