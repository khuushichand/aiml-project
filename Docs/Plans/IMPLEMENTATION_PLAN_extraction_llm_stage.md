## Stage 1: LLM Extraction Core
**Goal**: Implement LLM extraction stage in the pipeline with chunking knobs, robust JSON parsing, and usage metrics.
**Success Criteria**: LLM stage can parse JSON output (including code fences/extra text) and produces structured extraction results with usage metrics.
**Tests**: `tldw_Server_API/tests/WebScraping/test_llm_extraction.py`
**Status**: Complete

## Stage 2: Pipeline + Router Integration
**Goal**: Wire LLM settings through scraper router and enhanced pipeline entrypoints.
**Success Criteria**: Per-domain LLM settings reach the extraction pipeline and drive provider/model selection.
**Tests**: `tldw_Server_API/tests/WebScraping/test_llm_extraction.py`
**Status**: Complete

## Stage 3: Validation + Cleanup
**Goal**: Finalize tests, update status, and ensure docs/plan reflect completion.
**Success Criteria**: Tests pass; plan status updated.
**Tests**: `tldw_Server_API/tests/WebScraping/test_llm_extraction.py`
**Status**: Complete
