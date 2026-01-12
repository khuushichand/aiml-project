## Stage 1: Router + Handler Wiring
**Goal**: Introduce a handler pipeline and wire it into the scraping flows.
**Success Criteria**: Handlers resolve safely; default handler used when invalid; Article_Extractor_Lib uses handler output.
**Tests**: Unit tests for handler resolution and handler invocation.
**Status**: Not Started

## Stage 2: Backend Selection + Enhanced Scraper Integration
**Goal**: Enforce backend selection for curl/playwright and feed router into EnhancedWebScraper.
**Success Criteria**: backend=playwright skips httpx path; backend=curl uses curl_cffi when available; enhanced scraper applies router plan.
**Tests**: Unit tests covering backend selection and enhanced scraper routing behavior.
**Status**: Not Started

## Stage 3: Config + Docs Alignment
**Goal**: Add missing config keys to load_and_log_configs and update docs/tests.
**Success Criteria**: Config keys exposed via load_and_log_configs; docs updated; tests added/updated.
**Tests**: Unit test for config key exposure.
**Status**: Not Started
