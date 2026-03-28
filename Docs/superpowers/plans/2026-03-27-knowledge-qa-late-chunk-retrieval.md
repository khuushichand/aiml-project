# Knowledge QA Late Chunk Retrieval Implementation Plan

## Stage 1: Reproduce Missing Late-Chunk Behavior
**Goal**: Lock in the expected behavior for chunk-level media retrieval when a matched media item has no stored chunk rows.
**Success Criteria**: A unit test fails because the retriever falls back to a whole-media document instead of chunking the matched media item.
**Tests**: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -k late_chunk -v`
**Status**: Complete

## Stage 2: Implement Media-Level Match Rechunking
**Goal**: Update the media retriever so `fts_level="chunk"` performs media-level retrieval first when stored chunk FTS misses, then chunks those matched media items and returns relevant chunks.
**Success Criteria**: Chunk-level retrieval returns chunk documents with parent media metadata even when `UnvectorizedMediaChunks` has no rows for the matched media item.
**Tests**: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -k late_chunk -v`
**Status**: Complete

## Stage 3: Verify and Document Residual Ingest Findings
**Goal**: Confirm the retrieval fix passes targeted tests and capture the remaining ingest-side evidence without overstating the root cause.
**Success Criteria**: Targeted pytest passes and Bandit reports no new findings on touched files.
**Tests**: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -v`; `python -m bandit -r tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py -f json -o /tmp/bandit_knowledge_qa_late_chunk.json`
**Status**: Complete
