## Stage 1: LLM Throttling + Config Wiring
**Goal**: Add extraction-specific LLM throttling (per-provider concurrency, delay/jitter) and config/env plumbing for LLM knobs.
**Success Criteria**: LLM extraction honors `LLM_MAX_CONCURRENCY`/`LLM_DELAY_MS` (or YAML overrides); settings are parsed into pipeline `llm_settings`.
**Tests**: `tldw_Server_API/tests/WebScraping/test_llm_throttling.py`, `tldw_Server_API/tests/WebScraping/test_scraper_router_llm_settings.py`
**Status**: Complete

## Stage 2: LLM-Assisted Schema + Regex Pattern Generation
**Goal**: Add LLM helpers to generate schema DSL from sample HTML and one-off regex patterns per page, with strict JSON parsing.
**Success Criteria**: Schema generator returns valid DSL with selectors; regex generator returns a compiled pattern; both are safely parsed and validated.
**Tests**: `tldw_Server_API/tests/WebScraping/test_schema_llm_generation.py`, `tldw_Server_API/tests/WebScraping/test_regex_pattern_generation.py`
**Status**: Complete

## Stage 3: Clustering Enhancements
**Goal**: Implement hierarchical clustering (when available), cluster tagging, and tunables (linkage, similarity threshold, word-count threshold, top-k tags).
**Success Criteria**: Clustering returns stable groups and tags for representative inputs; tunables adjust grouping outcomes; fallback remains available when deps are missing.
**Tests**: `tldw_Server_API/tests/WebScraping/test_clustering_hierarchical.py`, `tldw_Server_API/tests/WebScraping/test_clustering_tags.py`
**Status**: Complete

## Stage 4: Caching + Observability + Fast Paths
**Goal**: Add selector/result LRU caches with clear hooks, retry/backoff with jitter for extraction stages, and richer per-strategy metrics/trace detail (latency, content length, selector match counts).
**Success Criteria**: Cache stats are reported/cleared; metrics include per-strategy latency and outcomes; trace exposes selector counts and applied rules.
**Tests**: `tldw_Server_API/tests/WebScraping/test_extraction_caches.py`, `tldw_Server_API/tests/WebScraping/test_extraction_observability.py`
**Status**: Complete
