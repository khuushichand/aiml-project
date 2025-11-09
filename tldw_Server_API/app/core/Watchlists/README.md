# Watchlists

## 1. Descriptive of Current Feature Set

- Purpose: Manage sources (RSS/sites), schedules, runs, and outputs that summarize and notify users about new items matching configured filters.
- Capabilities:
  - CRUD for sources, groups, tags; OPML import/export (with case/tag/group support).
  - Job scheduling (cron-like) for periodic fetch and filter pipelines; on-demand runs.
  - Preview endpoints to evaluate filters and extraction rules before running.
  - Output production with optional TTLs/retention and delivery via email or Chatbooks.
  - Optional topic monitoring notifications via Monitoring module.
- Inputs/Outputs:
  - Inputs: sources (URLs and parsing rules), jobs (filters, schedule), preview parameters.
  - Outputs: run details (tallies, filtered samples), outputs (HTML/Markdown content), exports (CSV/OPML).
- Related Endpoints (mounted under `/api/v1/watchlists`)
  - Router: tldw_Server_API/app/api/v1/endpoints/watchlists.py:83
  - Sources CRUD/bulk/import/export — see tests referencing routes:
    - Bulk create: `/watchlists/sources/bulk` (POST)
    - Export: `/watchlists/sources/export` (GET)
    - Examples: tldw_Server_API/tests/Watchlists/test_youtube_normalization_more.py:93, 118; test_opml_export_group_more.py:74; test_opml_export_tag_case.py:62
  - Jobs CRUD, run, preview
    - Create job: `/watchlists/jobs` (POST) — tldw_Server_API/tests/Watchlists/test_filters_api.py:38
    - Run job now: `/watchlists/jobs/{job_id}/run` (POST) — tldw_Server_API/tests/Watchlists/test_watchlists_scheduler_integration.py:99
    - Preview: `/watchlists/jobs/{job_id}/preview` (POST) — tldw_Server_API/tests/Watchlists/test_preview_endpoint_more.py:53
  - Runs and details
    - Runs listing and details: `/watchlists/runs`, `/watchlists/runs/{run_id}/details` — tldw_Server_API/tests/Watchlists/test_run_detail_filtered_sample.py:92
  - Outputs
    - Create outputs + deliveries (email/chatbook) — see tldw_Server_API/app/api/v1/endpoints/watchlists.py:2140–2240

## 2. Technical Details of Features

- Architecture & Data Flow
  - Pipeline orchestrator: `run_watchlist_job` consumes sources, fetches items (RSS or site rules), evaluates filters, and produces outputs: tldw_Server_API/app/core/Watchlists/pipeline.py:1
  - Fetchers and filters: RSS and site fetchers; filter evaluation utilities: tldw_Server_API/app/core/Watchlists/fetchers.py:1, tldw_Server_API/app/core/Watchlists/filters.py:1
  - Templates: HTML/Markdown templates stored and validated: tldw_Server_API/app/core/Watchlists/template_store.py:1
  - OPML import/export helpers: tldw_Server_API/app/core/Watchlists/opml.py:1

- Delivery
  - NotificationsService (email/chatbook) integration used at output creation: tldw_Server_API/app/api/v1/endpoints/watchlists.py:2168–2240
  - Monitoring module can emit topic alerts from content (see Monitoring README).

- Rate Limiting
  - Optional per-route SlowAPI limits with test-aware bypass: helpers at tldw_Server_API/app/api/v1/endpoints/watchlists.py:129–162
  - Global limiter: tldw_Server_API/app/api/v1/API_Deps/rate_limiting.py:1

- Configuration
  - Default retention/TTL via `WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS` and `WATCHLIST_OUTPUT_TEMP_TTL_SECONDS` env vars.
  - Optional `WATCHLISTS_DISABLE_RATE_LIMITS` for local/dev testing.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure
  - `pipeline.py`, `fetchers.py`, `filters.py`, `template_store.py`, `opml.py` — core watchlists components.
- Extension Points
  - Add new fetchers for providers; extend filter DSL; add more output formats or channels by reusing NotificationsService.
- Tests (selection)
  - Scheduler and run lifecycle: tldw_Server_API/tests/Watchlists/test_watchlists_scheduler_integration.py:63–109
  - Preview endpoints: tldw_Server_API/tests/Watchlists/test_preview_endpoint_more.py:39–95
  - OPML import/export (tag/group/case): tldw_Server_API/tests/Watchlists/test_opml_export_tag_case.py:51–62, test_opml_export_group_more.py:52–82
  - Runs listing/pagination: tldw_Server_API/tests/Watchlists/test_runs_list_global.py:49–73
- Local Dev Tips
  - Use OPML import to seed sources quickly; test preview before running long jobs.
  - For dev, disable rate limits and set temporary output TTLs to keep data tidy.
