## Stage 1: Reproduce and Trace
**Goal**: Reproduce the failing `docling` normalization test and identify whether the failure is in parser logic or test setup.
**Success Criteria**: Root cause is identified with evidence from the parser-selection path.
**Tests**: `python -m pytest tldw_Server_API/tests/Media/test_process_code_and_uploads.py -k "docling and normalization" -q`
**Status**: Complete

## Stage 2: Fix the Root Cause
**Goal**: Apply the smallest correct change so the test exercises the intended `docling` branch rather than the fallback path.
**Success Criteria**: The `docling` normalization test passes without weakening the runtime dependency guard.
**Tests**: `python -m pytest tldw_Server_API/tests/Media/test_process_code_and_uploads.py -k "docling and normalization" -q`
**Status**: Complete

## Stage 3: Verify the Surrounding Slice
**Goal**: Confirm the broader PDF/code-processing slice still passes and that no new security findings are introduced.
**Success Criteria**: Focused relevant pytest suites pass and Bandit on touched production/test scope is clean.
**Tests**: `python -m pytest tldw_Server_API/tests/Media/test_process_code_and_uploads.py -q`
**Status**: Complete

## Notes
- Root cause: the `docling` normalization parameterization only mocked `find_spec("docling.document_converter")`, but production also gates the `docling` path behind `_is_usable_torch_module_for_docling()`. In the test environment that guard returned `False`, so the code intentionally fell back to `pymupdf4llm`, bypassing the mocked `docling_parse_pdf`.
- Fix: keep the runtime guard intact and make the test explicitly satisfy it for the `docling` case by monkeypatching `_is_usable_torch_module_for_docling()` to return `True`.
