## Stage 1: Export Route Compatibility
**Goal**: Eliminate frontend/backend markdown-export path mismatch and preserve backward compatibility.
**Success Criteria**:
- Backend accepts both `/export` and legacy `/export/markdown` for markdown dictionary export.
- Frontend client uses canonical markdown export route.
- Regression test asserts route availability.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_dictionary_endpoints.py`
**Status**: Complete

## Stage 2: Global Usage Tracking Correctness
**Goal**: Ensure dictionary usage stats (`usage_count`, `last_used`) update when processing runs without explicit `dictionary_id`.
**Success Criteria**:
- Processing across active dictionaries records usage for all participating dictionaries.
- Existing explicit-dictionary behavior remains unchanged.
- Regression test validates usage updates for global processing.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_dictionary_endpoints.py`
**Status**: Complete

## Stage 3: Recent Activity Pagination in Stats UI
**Goal**: Add user-visible pagination controls for dictionary recent activity.
**Success Criteria**:
- Stats modal supports next/previous paging over activity records.
- Paging fetches subsequent offsets from activity API.
- UI test validates pagination fetch and rendering.
**Tests**:
- `cd apps/packages/ui && bunx vitest run src/components/Option/Dictionaries/__tests__/Manager.chatIntegrationStage3.test.tsx`
**Status**: Complete

## Stage 4: Verification and Closeout
**Goal**: Validate all remediation changes and close implementation.
**Success Criteria**:
- Targeted backend and UI tests pass.
- No regressions in existing dictionary stage-3 integrations.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_dictionary_endpoints.py`
- `cd apps/packages/ui && bunx vitest run src/components/Option/Dictionaries/__tests__/Manager.chatIntegrationStage3.test.tsx`
**Status**: Complete
