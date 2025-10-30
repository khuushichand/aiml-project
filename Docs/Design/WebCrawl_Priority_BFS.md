# Web Crawl Priority BFS Design

This document outlines the plan to enhance the EnhancedWebScraper with prioritized traversal while keeping default behavior unchanged behind feature flags.

## Scope

- Add feature flags to control crawling behavior and defaults without affecting existing flows.
- Prepare the service to read these flags from environment or `Config_Files/config.txt`.
- No change to the current traversal algorithm in this phase.

## Flags (with defaults)

- `WEB_CRAWL_STRATEGY` (default: `default`) – selects traversal mode (`default`, `bfs`, `best_first`).
- `WEB_CRAWL_INCLUDE_EXTERNAL` (default: `false`) – whether to traverse off-domain links.
- `WEB_CRAWL_SCORE_THRESHOLD` (default: `0.0`) – minimum score to enqueue a discovered URL in best‑first.
- `WEB_CRAWL_MAX_PAGES` (default: `100`) – default cap on pages per recursive crawl.

These are also readable from `[Web-Scraper]` in `Config_Files/config.txt` using the snake_case keys:

- `web_crawl_strategy`, `web_crawl_include_external`, `web_crawl_score_threshold`, `web_crawl_max_pages`.

Env variables override `config.txt` values; service parameters override both.

## Data Flow

1. Server startup loads `.env` and `Config_Files/config.txt` via `load_and_log_configs()`.
2. The `web_scraper` config section is extended to include the new crawl flags with environment precedence.
3. `WebScrapingService.process_web_scraping_task()` reads these flags and computes effective defaults only when explicit API params are not provided.
4. The effective values are passed to scraping methods and attached to result metadata for observability.

## Risks & Mitigations

- Risk: Behavior changes unintentionally for existing users.
  - Mitigation: Defaults keep current behavior; explicit params take precedence.
- Risk: Flags are read but unused until later phases.
  - Mitigation: Expose them in result metadata; do not alter traversal until Phase 4/5.
- Risk: Config parsing inconsistencies (string vs typed).
  - Mitigation: Parse to typed values in config and service; keep robust fallbacks.

## Next Phases (Summary)

- Implement URL normalization and FilterChain (Phase 1–2).
- Add scorers and priority queue traversal (Phase 3–4).
- Integrate link discovery caps and external link handling (Phase 5).
- Wire robots/egress checks into filters (Phase 6).

