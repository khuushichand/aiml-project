## Stage 1: Reproduce And Isolate
**Goal**: Produce a deterministic, testable reproduction of the import-time abort path.
**Success Criteria**: A test fails because importing `media_processing_deps` crashes/returns non-zero in a subprocess.
**Tests**: `python -m pytest tldw_Server_API/tests/unit/test_media_processing_deps_lazy_imports.py -v`
**Status**: Complete

## Stage 2: Remove Eager STT Import Coupling
**Goal**: Ensure `stt_provider_adapter` does not import `Audio_Transcription_Lib` at module import time.
**Success Criteria**: Top-level import is removed and provider/model parsing remains functionally equivalent.
**Tests**: Same unit test file plus related parser/default-model tests.
**Status**: Complete

## Stage 3: Verify Endpoint Import Stability
**Goal**: Confirm media endpoint import path no longer aborts and legacy/deprecation tests still pass.
**Success Criteria**: Subprocess import test and media deprecation test suite pass.
**Tests**: `python -m pytest tldw_Server_API/tests/unit/test_media_processing_deps_lazy_imports.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_deprecation_signals.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_process_deprecation_headers.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_compat_patchpoints.py tldw_Server_API/tests/Media_Ingestion_Modification/test_input_contracts.py tldw_Server_API/tests/Media_Ingestion_Modification/test_process_endpoints_contract_parity.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_shim_contract.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_docs_contract.py -v`
**Status**: Complete
