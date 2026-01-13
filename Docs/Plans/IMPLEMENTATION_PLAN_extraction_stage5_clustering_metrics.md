## Stage 1: Test Design for Clustering + Metrics
**Goal**: Define failing tests that capture clustering fallback behavior, cache clearing hooks, and strategy metrics emission.
**Success Criteria**: New tests in `tldw_Server_API/tests/WebScraping/` fail prior to implementation and describe expected outputs.
**Tests**: `tldw_Server_API/tests/WebScraping/test_clustering_fallback.py`, `tldw_Server_API/tests/WebScraping/test_extraction_metrics.py`
**Status**: Complete

## Stage 2: Implement Clustering Fallback + Caches + Metrics
**Goal**: Add clustering extraction strategy with embedding-prefilter + clustering selection, bounded caches, and metrics/trace details.
**Success Criteria**: Cluster strategy returns content for representative HTML, caches are bounded and clearable, metrics counters are emitted.
**Tests**: `tldw_Server_API/tests/WebScraping/test_clustering_fallback.py`, `tldw_Server_API/tests/WebScraping/test_extraction_metrics.py`
**Status**: Complete

## Stage 3: Cleanup + Plan Updates
**Goal**: Refactor for clarity, update plan statuses, and ensure tests pass.
**Success Criteria**: All Stage 5 tests pass; plan files reflect completed work.
**Tests**: `python -m pytest tldw_Server_API/tests/WebScraping/test_clustering_fallback.py tldw_Server_API/tests/WebScraping/test_extraction_metrics.py`
**Status**: Complete
