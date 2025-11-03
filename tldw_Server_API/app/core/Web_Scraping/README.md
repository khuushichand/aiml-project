# Web_Scraping

## 1. Descriptive of Current Feature Set

- Purpose: Production-grade web scraping utilities and the multi-provider web search implementation used by the research endpoint. Provides realistic browser headers, egress/SSRF enforcement, scraping engines, cookie/session management, deduplication, and an optional worker-queue service.
- Capabilities:
  - Article extraction: Async scraping via Trafi­latura, Playwright, and BeautifulSoup with cookies and custom headers.
  - Enhanced scraper service: Concurrent job queue with rate limiting, progress tracking, cookie storage, and content deduplication.
  - Web search orchestration: Subquery generation (LLM), provider calls, normalization, optional user review, relevance analysis (LLM), and final-answer aggregation.
  - Browser-like headers and UA profiles for provider and site requests.
  - Egress/SSRF policy checks for all outbound HTTP requests.
- Inputs/Outputs:
  - Scrape result: Dict including `url`, `title`, `author`, `date`, `content`, `extraction_successful`, and `error` on failure.
  - Web search result: Normalized `web_search_results_dict` with `results`, totals, and timing, or `processing_error` on failure.
- Related Endpoints:
  - Web search: `POST /api/v1/research/websearch` (delegates to this module) — tldw_Server_API/app/api/v1/endpoints/research.py:279
  - Scraper management (optional; not mounted by default): tldw_Server_API/app/api/v1/endpoints/web_scraping.py:1
    - `GET /web-scraping/status`, `GET/DELETE /web-scraping/job/{id}`, `POST /web-scraping/service/*`, cookies helpers, duplicate check
    - Include via `app.include_router(router, prefix="/api/v1")` if needed
- Related Schemas:
  - WebSearch request/response: tldw_Server_API/app/api/v1/schemas/websearch_schemas.py:14 (request), :52 (final answer), :62 (raw), :67 (aggregate)

## 2. Technical Details of Features

- Architecture & Data Flow
  - Headers: UA profiles and browser-like header construction — tldw_Server_API/app/core/Web_Scraping/ua_profiles.py:1
  - Web search Phase 1 (Generate + Search): `generate_and_search` — tldw_Server_API/app/core/Web_Scraping/WebSearch_APIs.py:154
  - Web search Phase 2 (Analyze + Aggregate): `analyze_and_aggregate` — tldw_Server_API/app/core/Web_Scraping/WebSearch_APIs.py:254
  - Result selection helper: `review_and_select_results` (selector-aware) — tldw_Server_API/app/core/Web_Scraping/WebSearch_APIs.py:576
  - Article scraping (standalone): `scrape_article` — tldw_Server_API/app/core/Web_Scraping/Article_Extractor_Lib.py:335
  - Enhanced scraper: `EnhancedWebScraper` with `RateLimiter`, `CookieManager`, `ContentDeduplicator`, and `ScrapingJobQueue` — tldw_Server_API/app/core/Web_Scraping/enhanced_web_scraping.py:1, :580
  - Service integration: `WebScrapingService` — tldw_Server_API/app/services/enhanced_web_scraping_service.py:1
- Provider Adapters (selected)
  - Google: `search_web_google` — tldw_Server_API/app/core/Web_Scraping/WebSearch_APIs.py:1542; `parse_google_results` — :1713
  - Brave: `search_web_brave` — :1199; `parse_brave_results` — :1269
  - DuckDuckGo: `search_web_duckduckgo` — :1339; `parse_duckduckgo_results` — :1459
  - Kagi: `search_web_kagi` — :1820; `parse_kagi_results` — :1861
  - Searx: `search_web_searx` — :1925; `parse_searx_results` — :2021
  - Tavily: `search_web_tavily` — :2085; `parse_tavily_results` — :2134
- Dependencies
  - HTTP: `aiohttp`, `httpx`
  - Parsing/Extraction: `BeautifulSoup`, `trafilatura`, `lxml`
  - Browser automation (optional): `playwright`
  - LLM/relevance/aggregation: `chat_orchestrator` and `LLM_Calls.Summarization_General_Lib.analyze`
- Configuration
  - Web search: Provider keys/URLs under `search_engines` in `Config_Files/config.txt` (e.g., `google_search_api_key`, `google_search_engine_id`, `brave_search_api_key`, `searx_search_api_url`, `tavily_search_api_key`).
  - Relevance/aggregation tuning in `Web-Scraping` config section (e.g., `relevance_llm_timeout_s`, `relevance_jitter_ms`).
  - Enhanced scraper (section `web_scraper`): `max_rps`, `max_rpm`, `max_rph`, `connector_limit`, `connector_limit_per_host`, `web_scraper_respect_robots`, `web_crawl_max_pages`, `web_crawl_include_external`, `web_crawl_keywords`, `web_crawl_enable_keyword_scorer`, `web_crawl_allowed_domains`, `web_crawl_blocked_domains`.
- Concurrency & Performance
  - Web search Phase 1 is executed in a thread pool to avoid blocking the event loop — tldw_Server_API/app/api/v1/endpoints/research.py:321
  - Enhanced scraper maintains a bounded async worker pool with rate limiting and per-host connection caps — tldw_Server_API/app/core/Web_Scraping/enhanced_web_scraping.py:420
- Error Handling
  - Provider adapters and parsers populate `processing_error` on failures; endpoint wraps unexpected exceptions as HTTP 500.
  - Aggregation returns a safe fallback when the final-answer LLM is not configured.
- Security
  - Centralized egress/SSRF policy enforced before all outbound requests: `evaluate_url_policy` — tldw_Server_API/app/core/Security/egress.py:146
  - Browser-like headers help reduce bot detection; robots.txt honoring is configurable.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure
  - `WebSearch_APIs.py`: Web search orchestration, provider adapters, relevance/aggregation helpers.
  - `Article_Extractor_Lib.py`: Direct article scraping and HTML→text/markdown utilities.
  - `enhanced_web_scraping.py`: Queue-based scraper (rate limits, cookies, dedup, Playwright/Trafi­latura/BS4).
  - `ua_profiles.py`: UA/header profiles; helper for browser-like headers.
  - `filters.py`, `scoring.py`, `url_utils.py`, `scraper_router.py`: Crawl heuristics, filters, and routing utilities.
- Extension Points
  - Add a provider by implementing `search_web_<provider>` and `parse_<provider>_results` to append standardized items into `web_search_results_dict` and enforcing `evaluate_url_policy` before HTTP.
  - Add a scraping strategy by extending `EnhancedWebScraper` and exposing it via `WebScrapingService` and the optional endpoints.
- Tests
  - Headers shape: tldw_Server_API/tests/Web_Scraping/test_websearch_headers.py:1
  - Egress guard + scraper basics: tldw_Server_API/tests/WebScraping/test_scraping_module.py:1
  - Review selector (selector param): tldw_Server_API/tests/WebScraping/test_review_selector.py:1
  - Websearch endpoint integration (delegation to this module): tldw_Server_API/tests/WebSearch/integration/test_websearch_endpoint.py:1
  - Engine routing stubs: tldw_Server_API/tests/WebSearch/integration/test_websearch_engines_endpoint.py:1
- Local Dev Tips
  - For scraper endpoints, explicitly include the router in `main.py` if desired (see file reference above). Keep `TEST_MODE=true` during dev to avoid rate limiter issues.
  - Configure provider keys and Searx/Tavily URLs in `config.txt` before running real queries.
- Pitfalls & Gotchas
  - Provider quotas and per-request result caps; favor small `result_count` and pagination.
  - Some providers require self-hosted endpoints (Searx) or keys (Tavily). Bing is present in legacy code, but not exposed in the public schema.
  - Playwright requires a browser install; the service gracefully degrades when unavailable.
- Roadmap/TODOs
  - Consolidate duplicate web search logic with `core/WebSearch` and preserve unified tests.
  - Optional on-disk cache for search results and scraping responses to reduce egress and cost.
  - Expand structured relevance output to reduce regex-based parsing.

