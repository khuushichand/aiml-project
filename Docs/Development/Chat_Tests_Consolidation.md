# Chat Tests Consolidation

Purpose: consolidate Chat and Chat_NEW tests under a single folder, reduce duplication, and make coverage clearer.

Date: 2025-10-16

## What Changed
- Moved unique tests from `tldw_Server_API/tests/Chat_NEW` into `tldw_Server_API/tests/Chat/`:
  - Added `tldw_Server_API/tests/Chat/unit/test_chat_processing_unit.py` with:
    - `TestProcessUserInput` (simple/empty/multiline/special/json inputs)
    - `TestUpdateChatContent` (basic/summary/none/all)
    - `TestErrorHandling` (error object property sanity checks)
    - `TestMessageFormatting` (basic JSON formatting checks)
  - Added `tldw_Server_API/tests/Chat/integration/test_stream_disconnect.py` (endpoint-level early disconnect).
- Removed now-duplicated files:
  - `tldw_Server_API/tests/Chat_NEW/unit/test_chat_functions.py`
  - `tldw_Server_API/tests/Chat_NEW/integration/test_stream_disconnect.py`

No existing Chat tests were modified.

## Overlap Summary

### Provider routing and exception mapping
- Duplicate coverage:
  - `Chat_NEW/unit/test_chat_functions.py::TestChatAPICall.*`
  - `Chat/test_chat_functions.py` (more comprehensive param mapping and exception mapping)
- Resolution: Kept `Chat/test_chat_functions.py` as source of truth; removed duplicates from Chat_NEW.

### Input processing and content update
- Unique to Chat_NEW:
  - `TestProcessUserInput` and `TestUpdateChatContent`
- Resolution: Preserved as `Chat/unit/test_chat_processing_unit.py`.

### Error object properties
- Unique to Chat_NEW:
  - Property checks for `ChatAPIError`, `ChatRateLimitError`, `ChatAuthenticationError`, `ChatProviderError`.
- Resolution: Preserved in `test_chat_processing_unit.py` (non-overlapping with exception mapping tests).

### Streaming early-disconnect
- Conceptual overlap:
  - Chat_NEW endpoint-level disconnect (`Chat_NEW/integration/test_stream_disconnect.py`)
  - Existing generator-level tests in `Chat/test_streaming_utils.py` (e.g., async generator close without RuntimeError, single stream_start).
- Resolution: Kept endpoint-level scenario as `Chat/integration/test_stream_disconnect.py` to complement lower-level generator tests.

## Normalized Layout
- `tldw_Server_API/tests/Chat/`
  - `unit/`
    - `test_chat_functions.py`
    - `test_streaming_utils.py`
    - `test_chat_request_schemas.py`
    - `test_prompt_template_manager.py`
    - `test_chat_helpers.py`
    - `test_chat_metrics_integration.py` (unit despite name)
    - `test_chat_orchestrator_bedrock.py`
    - `test_error_handling.py`
    - `test_document_generator.py`
    - `test_chat_dictionary_endpoints.py`
    - `test_chat_processing_unit.py` (migrated)
    - `test_chat_service_fallback.py` (migrated)
  - `integration/`
    - `test_chat_endpoint.py`
    - `test_chat_endpoint_integration.py`
    - `test_chat_endpoint_simplified.py`
    - `test_chat_endpoint_streaming_normalization.py`
    - `test_chat_integration.py`
    - `test_chat_integration_isolated.py` (+ `conftest_isolated.py`)
    - `test_chat_completions_integration.py`
    - `test_chat_fixes_integration.py`
    - `test_chat_simple.py`
    - `test_chat_unit.py` (endpoint-level “unit” retained under integration)
    - `test_stream_disconnect.py` (migrated)

## Notes
- Pytest discovery picks up subfolders automatically; root `conftest.py` applies to both.
- `conftest_isolated.py` was moved under `integration/` to keep relative imports intact.
- Remaining root files:
  - `load_test_chat_endpoint.py` (utility script)
  - `test_fixtures.py` (legacy fixtures helper; kept at root to avoid surprise fixture scoping changes)
