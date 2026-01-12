## Stage 1: Metrics audit
**Goal**: Identify scraping paths lacking scrape_* metrics and align labels to Metrics Manager.
**Success Criteria**: Map of functions to update with scrape_fetch_* instrumentation.
**Tests**: None.
**Status**: In Progress

## Stage 2: JS-required heuristics
**Goal**: Add domain hints and refine detection thresholds while keeping false positives low.
**Success Criteria**: Updated heuristics and tests for new signals.
**Tests**: tldw_Server_API/tests/Web_Scraping/test_js_required_heuristics.py
**Status**: Not Started

## Stage 3: Accept-Encoding compatibility
**Goal**: Ensure requests-only paths do not advertise unsupported encodings.
**Success Criteria**: Headers sanitized for requests paths; http_client sanitization updated.
**Tests**: tldw_Server_API/tests/Web_Scraping/test_http_client_fetch.py
**Status**: Not Started
