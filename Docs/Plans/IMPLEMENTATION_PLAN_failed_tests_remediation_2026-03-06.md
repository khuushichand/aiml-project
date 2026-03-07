## Stage 1: Stabilize Core API/Test Contract Breaks
**Goal**: Fix deterministic contract regressions causing immediate failures in media references, ingest jobs, and Postgres role setup test SQL.
**Success Criteria**: No failures from `KeyError: 'PARSED_REFERENCES_CACHE_TABLE'`, ingest job mock signature mismatch, or `%I` placeholder error.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Media/test_document_references.py`
- `python -m pytest -q tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_endpoint.py::test_submit_media_ingest_jobs_creates_one_job_per_item`
- `python -m pytest -q tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py::test_media_rls_enforces_scope_postgres`
**Status**: Complete

## Stage 2: Fix Buffered Transcription Merge Robustness
**Goal**: Make token merge algorithms robust to malformed/None timestamps in overlap regions.
**Success Criteria**: Longest contiguous and LCS merge tests pass for missing timestamp overlap tokens.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_buffered_transcription.py::TestBufferedTranscription::test_merge_longest_contiguous_ignores_missing_timestamp_overlap_tokens`
- `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_buffered_transcription.py::TestBufferedTranscription::test_merge_lcs_ignores_missing_timestamp_overlap_tokens`
**Status**: Complete

## Stage 3: Remove Environment-Sensitive Torch/ONNX Fragility
**Goal**: Ensure Whisper/Nemo ONNX tests don’t crash or fail due to brittle torch/cuda assumptions.
**Success Criteria**: Whisper custom vocabulary tests and Nemo/Parakeet ONNX integration tests pass under mocked/stubbed conditions.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_custom_vocabulary.py`
- `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_nemo_transcription.py::TestNemoTranscription::test_load_parakeet_onnx`
- `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_parakeet_onnx.py::TestParakeetONNXIntegration::test_integration_with_nemo_module`
**Status**: Complete

## Stage 4: Align Documentation and PDF Contract Tests
**Goal**: Resolve failing docs contract paths and PDF docling assertion mismatch while preserving intended behavior.
**Success Criteria**: Docs contract tests locate expected docs targets; PDF docling-related tests assert current valid status semantics.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Media_Ingestion_Modification/test_media_docs_contract.py`
- `python -m pytest -q 'tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py::TestProcessPdfs::test_process_pdf_upload_success[docling]'`
- `python -m pytest -q 'tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py::TestProcessPdfs::test_process_pdf_multi_status_mixed[docling]'`
**Status**: Complete

## Stage 5: Security and Verification
**Goal**: Verify touched scope correctness and run required security scan.
**Success Criteria**: Targeted pytest commands pass or are explicitly reported as environment-blocked with rationale; Bandit run on touched paths completes with no new findings in changed code.
**Tests**:
- Targeted pytest commands for all changed failure clusters
- `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/media/document_references.py tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Buffered_Transcription.py tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Nemo.py tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_endpoint.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_docs_contract.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py`
**Status**: Complete
