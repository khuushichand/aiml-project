## Stage 1: Reproduce Stored-Chunk Override Gap
**Goal**: Add a regression test proving a late-chunking query should bypass stored chunk retrieval and return transient chunk docs.
**Success Criteria**: The new retriever test fails against current behavior while stored chunk rows remain unchanged.
**Tests**: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -k text_late_chunking -v`
**Status**: Complete

## Stage 2: Wire Per-Query Text Late Chunking
**Goal**: Add an explicit query setting from UI/API through `RetrievalConfig` into the media retriever.
**Success Criteria**: When enabled, media retrieval late-chunks matched media in memory for that query and does not persist or overwrite stored chunks.
**Tests**: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -k text_late_chunking -v`
**Status**: Complete

## Stage 3: Verify End-to-End Setting Surface
**Goal**: Ensure the new setting is carried by the unified RAG request builder and exposed in KnowledgeQA settings.
**Success Criteria**: Targeted Python and UI tests pass, and Bandit reports no new findings in touched Python files.
**Tests**: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py -v`; `bunx vitest run src/services/rag/unified-rag.test.ts`
**Status**: Complete
