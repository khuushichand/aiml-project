## Stage 1: Pipeline Skeleton + Routing
**Goal**: Embed an extraction pipeline in `Article_Extractor_Lib` and `EnhancedWebScraper` with default strategy order, per-domain overrides, and structured reason codes/trace output.
**Success Criteria**: Scrape results include `extraction_trace` with strategy order + fallback reasons; per-domain `strategy_order` override is honored.
**Tests**: `tldw_Server_API/tests/WebScraping/test_extraction_pipeline_router.py`
**Status**: In Progress

## Stage 2: Schema-Driven Extraction (Watchlist Selectors)
**Goal**: Reuse watchlist selector logic to implement schema-driven extraction (CSS/XPath selectors, base selectors, and safe transforms) inside the pipeline.
**Success Criteria**: Schema extraction returns structured fields for representative HTML inputs; selector validation catches invalid/fragile selectors.
**Tests**: `tldw_Server_API/tests/WebScraping/test_schema_extraction.py`, `tldw_Server_API/tests/WebScraping/test_selector_validation.py`
**Status**: Not Started

## Stage 3: Regex Fallback + PII Masking
**Goal**: Add the regex catalog fallback with optional PII masking/redaction and output spans; include credit-card Luhn validation before output.
**Success Criteria**: Regex matches return `{url, label, value, span}`; masking toggles apply to email/phone/credit_card outputs.
**Tests**: `tldw_Server_API/tests/WebScraping/test_regex_catalog.py`, `tldw_Server_API/tests/WebScraping/test_pii_masking.py`
**Status**: Not Started

## Stage 4: LLM Extraction Stage
**Goal**: Integrate LLM extraction using existing orchestration (usage tracking + rate limits), chunking knobs, and robust JSON parsing/repair with strict mode.
**Success Criteria**: LLM extraction returns structured outputs for mocked responses; token usage is emitted via existing metrics hooks.
**Tests**: `tldw_Server_API/tests/WebScraping/test_llm_extraction.py`, `tldw_Server_API/tests/WebScraping/integration/test_llm_extraction_pipeline.py`
**Status**: Not Started

## Stage 5: Clustering Fallback + Caching + Observability
**Goal**: Add embedding-based prefiltering + clustering fallback, bounded caches, and per-strategy metrics/trace fields.
**Success Criteria**: Clustering groups relevant chunks for small inputs; cache hooks clear after runs; metrics counters record strategy success/fallbacks.
**Tests**: `tldw_Server_API/tests/WebScraping/test_clustering_fallback.py`, `tldw_Server_API/tests/WebScraping/test_extraction_metrics.py`
**Status**: Not Started
