## Stage 1: PRD And Plan Synchronization
**Goal**: Align product/design docs with current repository reality and explicitly track the remaining gaps.
**Success Criteria**:
- `PRD_TTS_History_Model.md` no longer reports Stage 1-5 as `Not Started`.
- PRD includes a short "Known Gaps" section listing only unresolved items.
- `Docs/Design/IMPLEMENTATION_PLAN_tts_history.md` and PRD statuses are consistent.
**Tests**:
- Manual doc review for consistency across PRD and implementation plan files.
**Status**: Complete

## Stage 2: Job History Artifact Linking + Request Correlation In Logs
**Goal**: Close backend behavior gaps for job history linkage and failure observability.
**Success Criteria**:
- Job worker writes `artifact_ids` for successful long-form TTS runs (in addition to `job_id` and `output_id`).
- History insert failure logs include `request_id` (or job request correlation id) in both non-job and job write paths.
- Existing non-fatal behavior is preserved: history insert failures do not fail TTS responses/jobs.
**Tests**:
- Unit/integration: job run creates history row with `artifact_ids` populated.
- Unit/integration: history write failure log path includes request correlation field.
**Status**: Complete

## Stage 3: Cleanup Configuration Source Consistency
**Goal**: Ensure TTS history cleanup uses the same config source semantics as the rest of the app.
**Success Criteria**:
- Cleanup service resolves retention/row-cap/interval from `settings` with env override behavior matching project patterns.
- Behavior remains unchanged for default values (`90`, `10000`, `24`).
- Existing disable semantics (`<=0` checks) remain intact.
**Tests**:
- Unit tests for cleanup config resolution precedence and disable behavior.
**Status**: Complete

## Stage 4: Test Coverage For Remaining PRD Expectations
**Goal**: Add explicit tests for the currently unverified PRD requirements.
**Success Criteria**:
- Unit tests cover segment truncation policy (`64KB`, failed-segment retention, `truncated=true`).
- Unit/integration tests cover `voice_id` and `voice_name` filters on `GET /api/v1/audio/history`.
- Integration test covers end-to-end `speech/jobs` flow -> output artifact -> history row linkage.
**Tests**:
- `tests/TTS/test_tts_history_utils.py` (segment truncation cases).
- `tests/TTS_NEW/unit/test_tts_history_endpoints.py` (voice filter cases).
- `tests/TTS_NEW/integration/` new job-history integration test.
**Status**: Complete

## Stage 5: Validation, Performance Sanity, And Closeout
**Goal**: Verify all changes and close out the gap list with evidence.
**Success Criteria**:
- Targeted TTS history test suites pass locally.
- Cursor pagination and `include_total` behavior remain unchanged.
- PRD "Known Gaps" section is cleared or reduced to explicit deferred items with rationale.
**Tests**:
- `python -m pytest -v tldw_Server_API/tests/TTS/test_tts_history_utils.py`
- `python -m pytest -v tldw_Server_API/tests/TTS_NEW/unit/test_tts_history_endpoints.py`
- `python -m pytest -v tldw_Server_API/tests/TTS_NEW/integration/test_tts_history_perf_sanity.py`
- `python -m pytest -v tldw_Server_API/tests/TTS_NEW/integration/test_tts_history_artifact_purge.py`
- New/updated integration test(s) from Stage 4.
**Status**: Not Started
