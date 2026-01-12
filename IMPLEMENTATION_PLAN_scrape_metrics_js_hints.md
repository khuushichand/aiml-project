## Stage 1: Scope + Baseline Review
**Goal**: Identify scraping paths that need metrics, JS heuristics, and Accept-Encoding fixes.
**Success Criteria**: Key call sites and metric names cataloged; plan ready for edits.
**Tests**: N/A (review step).
**Status**: Complete

## Stage 2: Instrumentation + Heuristics
**Goal**: Add metrics across scraping paths, refine JS-required detection, and update Accept-Encoding handling.
**Success Criteria**: Scrape metrics emitted for Article_Extractor_Lib + EnhancedWebScraper; JS heuristics updated with domain hints; Accept-Encoding sanitized for non-httpx clients.
**Tests**: Unit tests for JS heuristics and router/backend flows remain green.
**Status**: Complete

## Stage 3: Validation + Docs
**Goal**: Ensure metrics registry includes any new scrape metrics and update docs/PRD status if needed.
**Success Criteria**: Metrics registry updated; tests added/updated; optional doc note adjusted.
**Tests**: Targeted pytest runs for new/affected tests.
**Status**: In Progress
