# Search_and_Research

## 1. Descriptive of Current Feature Set

- Purpose: Umbrella for research-oriented capabilities: general web search with optional LLM aggregation and paper/preprint discovery across providers (arXiv, Semantic Scholar, PubMed/PMC, OSF, Zenodo, etc.).
- Capabilities:
  - Web search pipeline (multi-provider) with subquery generation, relevance scoring, article scraping, and final-answer synthesis. See WebSearch README for provider details.
  - Paper search endpoints under `/api/v1/paper-search/*` for domain-specific sources (arXiv, Semantic Scholar, BioRxiv, PubMed/PMC, OSF, Zenodo, and others), with pagination and normalization.
  - Optional ingestion of paper content into Media DB for later RAG and downstream analysis.
- Inputs/Outputs:
  - Web search request/response models: `tldw_Server_API/app/api/v1/schemas/websearch_schemas.py:14`, `tldw_Server_API/app/api/v1/schemas/websearch_schemas.py:62`, `tldw_Server_API/app/api/v1/schemas/websearch_schemas.py:67`.
  - Paper search request/response models: `tldw_Server_API/app/api/v1/schemas/research_schemas.py:20`, `tldw_Server_API/app/api/v1/schemas/research_schemas.py:30`, `tldw_Server_API/app/api/v1/schemas/research_schemas.py:84`, `tldw_Server_API/app/api/v1/schemas/research_schemas.py:112`.
- Related Endpoints:
  - Web search: `POST /api/v1/research/websearch` — `tldw_Server_API/app/api/v1/endpoints/research.py:279`.
  - Paper search (preferred): `GET /api/v1/paper-search/arxiv` — `tldw_Server_API/app/api/v1/endpoints/paper_search.py:24` and subsequent handlers; see file for additional providers.
  - Deprecated research shims: `GET /api/v1/research/arxiv-search` and `GET /api/v1/research/semantic-scholar-search` — `tldw_Server_API/app/api/v1/endpoints/research.py:59`, `tldw_Server_API/app/api/v1/endpoints/research.py:210`.

## 2. Technical Details of Features

- Architecture & Data Flow
  - Web search flow: generate_and_search (subqueries + provider calls) → analyze_and_aggregate (relevance LLM + scraping + final answer). Implementation currently lives in `core/Web_Scraping/WebSearch_APIs.py` and is delegated by the `research` endpoint.
  - Paper search flow: per-provider handlers under `paper_search.py` call into `core/Third_Party/*` modules, normalize to Pydantic schemas, and support pagination.
  - Optional ingestion path: arXiv example uses `MediaDatabase.add_media_with_keywords` to persist parsed/summarized content — `tldw_Server_API/app/api/v1/endpoints/research.py:131`.
- Key Functions/Modules
  - Web search endpoint glue: `tldw_Server_API/app/api/v1/endpoints/research.py:279` delegates phase 1 to a thread pool and phase 2 to async aggregation with disconnect-aware cancellation.
  - Web search orchestration and providers: `tldw_Server_API/app/core/Web_Scraping/WebSearch_APIs.py:154` (generate), `tldw_Server_API/app/core/Web_Scraping/WebSearch_APIs.py:254` (aggregate), plus `search_web_*`/`parse_*` for each provider.
  - Paper providers (selection): `tldw_Server_API/app/core/Third_Party/Arxiv.py`, `Semantic_Scholar.py`, `BioRxiv.py`, `PubMed.py`, `PMC_OA.py`, `PMC_OAI.py`, etc.
- Dependencies
  - LLM stack for subquery generation and relevance/aggregation: `tldw_Server_API/app/core/Chat/chat_orchestrator.py:77`, `tldw_Server_API/app/core/LLM_Calls/Summarization_General_Lib.py:312`.
  - Article scraping for evidence: `tldw_Server_API/app/core/Web_Scraping/Article_Extractor_Lib.py:335`.
  - DB persistence: legacy media DB module via the media database adapter.
- Configuration
  - Provider API keys and URLs are loaded from `Config_Files/config.txt` (section `search_engines` and third-party sections). For web search engines, see the WebSearch README.
  - Per-provider throttling/limits vary by upstream API; tests favor mocking.
- Concurrency & Performance
  - Web search provider calls are offloaded to a `ThreadPoolExecutor` to keep the event loop responsive — `tldw_Server_API/app/api/v1/endpoints/research.py:321`.
  - Aggregate stage is async and supports cancellation if the client disconnects.
- Security
  - All outbound HTTP calls are expected to honor centralized egress/SSRF policy via `evaluate_url_policy` — `tldw_Server_API/app/core/Security/egress.py:146`. This is explicitly enforced in the web search providers and the article scraper.
- Error Handling
  - Endpoint returns structured HTTP errors on upstream failures and safe fallbacks in aggregation when LLM output is malformed or unavailable.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure
  - `core/Search_and_Research`: umbrella docs (this README). Active implementations are split across `core/Web_Scraping` (web search orchestration/providers) and `core/Third_Party` (paper sources), with API glue in `app/api/v1/endpoints/research.py` and `paper_search.py`.
- Adding a Paper Provider
  - Implement provider-specific fetch/normalize logic in `core/Third_Party/<Provider>.py`.
  - Add an endpoint to `paper_search.py` returning the appropriate Pydantic response model; mirror query params used by provider.
  - Ensure egress policy checks precede any network calls; prefer `httpx` clients with `trust_env=False`.
- Tests
  - Web search endpoint and aggregation: `tldw_Server_API/tests/WebSearch/integration/test_websearch_endpoint.py:1`.
  - Engine routing and provider stubs: `tldw_Server_API/tests/WebSearch/integration/test_websearch_engines_endpoint.py:1`.
  - Paper search external integrations: `tldw_Server_API/tests/PaperSearch/integration/test_paper_search_external.py:1` and provider-specific tests under the same folder (e.g., `.../test_arxiv_external.py`, `.../test_zenodo_external.py`).
  - Egress guard: `tldw_Server_API/tests/Security/test_websearch_egress_guard.py:1`.
- Local Dev Tips
  - Start with small page sizes and low `result_count` to avoid quotas. Configure provider keys/URLs in `config.txt` and `.env`.
  - Use the deprecated research shims only for backward compatibility; prefer `/paper-search/*`.
- Pitfalls & Gotchas
  - Provider quotas, pagination semantics, and schema drift can vary (e.g., Semantic Scholar `next` offset). Keep parsers defensive and tests mocked.
  - Web search “Bing” is present in legacy code but is not part of the supported engine set exposed by the public schema.
- Roadmap/TODOs
  - Consolidate web search orchestration into `core/WebSearch` (currently delegated to `core/Web_Scraping`).
  - Add caching for frequently repeated paper queries and search results.
  - Expand standardized evidence capture for aggregated answers.
