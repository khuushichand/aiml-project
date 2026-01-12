## Stage 1: Code Fixes
**Goal**: Address Local_LLM handler issues (ports, payload filtering, completions support, timeouts, IPv6 ports, asset selection).
**Success Criteria**: Code changes compile and handlers behave as intended.
**Tests**: Existing unit tests pass; new tests added in Stage 2.
**Status**: Complete

## Stage 2: Tests
**Goal**: Add coverage for missing-port defaulting and timeout-key filtering.
**Success Criteria**: New tests pass and fail on old behavior.
**Tests**: New unit tests under `tldw_Server_API/tests/Local_LLM/`.
**Status**: Complete

## Stage 3: Review & Cleanup
**Goal**: Ensure changes are consistent with project patterns and docs.
**Success Criteria**: No unresolved TODOs; plan updated to Complete.
**Tests**: Optional targeted pytest runs if requested.
**Status**: Complete
