## Stage 1: Llamafile Startup Cleanup + Asset Selection
**Goal**: Ensure failed startup cleans up processes and downloads pick platform-appropriate binaries.
**Success Criteria**: Failed readiness terminates process; .exe/.zip selection logic handles Windows assets; tests cover both.
**Tests**: `tldw_Server_API/tests/Local_LLM/test_llamafile_handler.py::test_llamafile_start_server_not_ready_terminates_process`, `tldw_Server_API/tests/Local_LLM/test_llamafile_handler.py::test_llamafile_download_selects_exe_asset`, `tldw_Server_API/tests/Local_LLM/test_llamafile_handler.py::test_llamafile_download_extracts_zip_asset`.
**Status**: Complete

## Stage 2: Retry Semantics Normalization
**Goal**: Align retry behavior with "attempts = 1 + retries" in all paths.
**Success Criteria**: `retries=0` produces a single attempt; behavior consistent across http_utils helpers.
**Tests**: `tldw_Server_API/tests/Local_LLM/test_http_utils.py::test_request_json_retries_zero_makes_single_attempt`.
**Status**: Complete

## Stage 3: Input Hardening + Stream Guarding
**Goal**: Harden start_server input handling and prevent misuse of non-streaming inference with stream enabled.
**Success Criteria**: Invalid host/port handled gracefully; `stream=True` ignored in non-streaming inference.
**Tests**: `tldw_Server_API/tests/Local_LLM/test_llamacpp_handler.py::test_llamacpp_inference_forces_non_streaming`.
**Status**: Complete
