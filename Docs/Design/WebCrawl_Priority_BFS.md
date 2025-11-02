# Web Crawl: Best-First Priority BFS

This document describes the implemented crawling strategy, link discovery pipeline, configuration, and operational guidance for the enhanced web scraper.

## Summary

- Traversal uses a best-first priority queue (heap) ordered by composite score and depth, with batching for throughput.
- Link discovery normalizes and filters candidates, optionally enforces robots.txt, scores, thresholds, and enqueues.
- Central egress guard runs before any fetch/robots to honor network safety policy.
- Per-result metadata includes `depth`, `parent_url`, and `score`, persisted alongside content.
- Metrics and debug logs expose crawl progress, queue depth, candidate scores, and skip reasons.

## Strategy

- Queue item shape: `(-score, depth, url, parent_url)`; lower (more negative) values pop first.
- Batch: pops up to `BEST_FIRST_BATCH_SIZE` per loop; calls `scrape_multiple` concurrently.
- Score: `CompositeScorer(PathDepth, ContentType, Freshness[, Keywords][, DomainAuthority])` normalized average.
- Depth: current depth gauge and per-result metadata are maintained; cap by `max_depth` and `max_pages`.

## Link Discovery Pipeline

1. Extract anchors from the fetched page (fallback fetches HTML if content lacks tags).
2. For each `href`:
   - Normalize via `normalize_for_crawl(source, href)`: lowercase scheme/host, strip fragments, drop tracking params, remove default ports, normalize slashes.
   - Deduplicate against `visited` and `seen` sets.
   - Apply `FilterChain`: `DomainFilter` (allowed/blocked), `ContentTypeFilter` (binary/doc rejects), `URLPatternFilter` (default excludes like `/tag/`, `wp-content`, common image/doc extensions).
   - Optional `RobotsFilter.allowed(url)`: per-domain cached robots.txt, only if egress allows the host; fails open on robots errors.
   - Score with CompositeScorer; drop if `< score_threshold`.
   - Enqueue with `depth+1` and set parent.

## Configuration

Flags are read from environment or `[Web-Scraper]` in `Config_Files/config.txt`. Explicit API params override both.

- Traversal
  - `WEB_CRAWL_STRATEGY` / `web_crawl_strategy`: `default|best_first` (current engine uses best-first; value recorded in metadata).
  - `WEB_CRAWL_INCLUDE_EXTERNAL` / `web_crawl_include_external`: bool; include off-domain links.
  - `WEB_CRAWL_SCORE_THRESHOLD` / `web_crawl_score_threshold`: float; drop candidates below threshold (e.g., `0.2`).
  - `WEB_CRAWL_MAX_PAGES` / `web_crawl_max_pages`: int; cap total pages per crawl.
  - `web_crawl_allowed_domains` (csv): restrict to allowed domains (subdomains included). Base host is always included when `include_external=false`.
  - `web_crawl_blocked_domains` (csv): domains to exclude.

- Scorers
  - `WEB_CRAWL_ENABLE_KEYWORD_SCORER` / `web_crawl_enable_keyword_scorer`: bool.
  - `WEB_CRAWL_KEYWORDS` / `web_crawl_keywords`: csv (e.g., `ai,ml,python`).
  - `WEB_CRAWL_ENABLE_DOMAIN_MAP` / `web_crawl_enable_domain_map`: bool.
  - `WEB_CRAWL_DOMAIN_MAP` / `web_crawl_domain_map`: JSON or `domain:score` csv.

- Robots
  - `web_scraper_respect_robots` (bool; default `true`): enforce robots.txt for egress-allowed hosts with per-domain caching.

### Request-level overrides

The API `POST /api/v1/media/process-web-scraping` accepts optional overrides in the payload:

```json
{
  "scrape_method": "Recursive Scraping",
  "url_input": "https://example.com",
  "max_pages": 20,
  "max_depth": 3,
  "include_external": false,
  "score_threshold": 0.2,
  "crawl_strategy": "best_first",
  "mode": "persist"
}
```

## Metrics & Logging

- Counters
  - `webscraping.crawl.pages_crawled`
  - `webscraping.crawl.links_discovered`
  - `webscraping.crawl.urls_skipped{reason=visited_or_depth|dup_seen|filter_chain|robots|below_threshold|custom_filter}`
  - `scrape_blocked_by_robots_total{domain}` (existing)
- Gauges
  - `webscraping.crawl.queue_size`
  - `webscraping.crawl.depth`
- Histogram
  - `webscraping.crawl.score` (start URL and candidate scores)

Debug logs annotate rejections, scores, thresholds, enqueues, and successes with depth/score.

## Result Metadata & Persistence

- Each result includes `metadata: { depth, parent_url, score }`.
- Persistence stores `crawl_depth`, `crawl_parent_url`, and `crawl_score` in safe metadata and embeds them in formatted content for context.

## Recommended Defaults

- `include_external=false` for predictable scope and speed.
- `score_threshold≈0.2-0.4` to prefer likely content pages.
- Enable `keyword_scorer` when targeting topical sections; provide 2-5 concise keywords.
- Use modest `max_pages` (≤100) per crawl to avoid long runs.

## Limitations

- External crawling increases latency and risk of anti-bot triggers; keep off by default.
- The engine does not ship with proxy rotation or advanced evasion; honor robots and site policies.
- Playwright is optional; JS-heavy sites may need it enabled for accuracy.
- Domain authority map is static; keep maps small to avoid biasing too far from content relevance.

## References

- Code: `app/core/Web_Scraping/enhanced_web_scraping.py`, `app/core/Web_Scraping/filters.py`, `app/core/Web_Scraping/scoring.py`, `app/core/Web_Scraping/url_utils.py`.
- Config: `app/core/config.py`, `Config_Files/README.md`.
- API: `app/api/v1/endpoints/media.py` (`/api/v1/media/process-web-scraping`).
