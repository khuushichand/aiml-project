## Stage 1: Reproduce Missing Chunk Persistence
**Goal**: Add a regression test for AV persistence when chunking was requested but `chunk_options` is missing at persistence time.
**Success Criteria**: A unit test fails against current behavior and proves chunks should still be persisted.
**Tests**: `python -m pytest tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_chunk_consistency.py -k requested_chunking_without_chunk_options -v`
**Status**: Complete

## Stage 2: Harden AV Persistence
**Goal**: Ensure `persist_primary_av_item()` recomputes effective chunk options when `perform_chunking=True` and no chunk options were provided.
**Success Criteria**: The regression test passes and persisted repository kwargs include chunk rows.
**Tests**: `python -m pytest tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_chunk_consistency.py -k requested_chunking_without_chunk_options -v`
**Status**: Complete

## Stage 3: Verify Touched Scope
**Goal**: Run focused verification for the modified ingestion code.
**Success Criteria**: Targeted ingestion unit tests pass and Bandit reports no new findings in touched files.
**Tests**: `python -m pytest tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_chunk_consistency.py -v`; `python -m bandit -r tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py -f json -o /tmp/bandit_media_ingest_chunking_hardening.json`
**Status**: Complete
