# Services Module - Overview and Operational Guide

This document summarizes the background services in `tldw_server`, their responsibilities, configuration, and production hardening notes. It reflects the code in `tldw_Server_API/app/services` as of v0.1.0.

## At-a-Glance

- Core workers: Chatbooks Jobs worker, Jobs metrics gauges worker, Claims rebuild worker
- Aggregators: API request usage aggregator, LLM usage aggregator
- Quotas: User storage quota service (filesystem + DB)
- Web scraping: Enhanced scraping service (Playwright-based) with legacy fallback
- Placeholders (non-production): document/ebook/podcast/XML processors, in-memory ephemeral store

## Startup/Shutdown

The app starts/stops service loops in `tldw_Server_API/app/main.py` (lifespan):
- Chatbooks Core Jobs worker (if jobs backend is `core`): `tldw_Server_API/app/services/core_jobs_worker.py`
- Jobs metrics gauges loop: `tldw_Server_API/app/services/jobs_metrics_service.py`
- Claims rebuild loop (optional): `tldw_Server_API/app/services/claims_rebuild_service.py`
- Usage aggregators: `tldw_Server_API/app/services/usage_aggregator.py` and `llm_usage_aggregator.py`

Each loop supports graceful stop via an `asyncio.Event` and is gated by env flags.

## Services

### Storage Quota Service
- File: `tldw_Server_API/app/services/storage_quota_service.py`
- Purpose: Tracks per-user storage (`USER_DATA_BASE_PATH` and optionally per-user ChromaDB). Updates usage in `users` table. Provides quota checks, recalculation, temp cleanup, and breakdown.
- Key methods:
  - `calculate_user_storage(user_id)` - scans disk, updates DB (async + threadpool)
  - `check_quota(user_id, new_bytes)` - cached, emits gauges
  - `update_usage(user_id, bytes_delta, operation)` - safe increments with floor at 0
  - `cleanup_temp_files(user_id?, older_than_hours=24)`
- Caching: `TTLCache` for quota and storage results (5-10 minutes)
- Backend: Works with SQLite and PostgreSQL via `DatabasePool`
- Notes: All heavy filesystem ops run in a small threadpool. Methods self-init on first use.

### Jobs Metrics Gauges
- File: `tldw_Server_API/app/services/jobs_metrics_service.py`
- Purpose: Periodically emits metrics: stale processing counts, queue depths, and time to expiry for processing jobs.
- Env:
  - `JOBS_METRICS_INTERVAL_SEC` (default 30)
  - `JOBS_TTL_ENFORCE` with `JOBS_TTL_AGE_SECONDS`, `JOBS_TTL_RUNTIME_SECONDS`, `JOBS_TTL_ACTION` (cancel|fail)

### Chatbooks Core Jobs Worker
- File: `tldw_Server_API/app/services/core_jobs_worker.py`
- Purpose: Processes Chatbooks import/export jobs from the core jobs backend with lease renewal and cancellation checks; writes job result and updates per-user Chatbooks job records.
- Env:
  - `CHATBOOKS_JOBS_BACKEND` = `core` (default) to enable core backend
  - `CHATBOOKS_CORE_WORKER_ENABLED` (true/false)
  - `JOBS_POLL_INTERVAL_SECONDS`, `JOBS_LEASE_SECONDS`, `JOBS_LEASE_RENEW_SECONDS`, `JOBS_LEASE_RENEW_JITTER_SECONDS`

### Claims Rebuild Worker
- File: `tldw_Server_API/app/services/claims_rebuild_service.py`
- Purpose: Background thread pool to rebuild claims for media, using chunking and the claims extractor.
- Env (via app settings): `CLAIMS_REBUILD_ENABLED`, `CLAIMS_REBUILD_INTERVAL_SEC`, `CLAIMS_REBUILD_POLICY` (missing|all|stale), `CLAIMS_STALE_DAYS`

### Usage Aggregators
- Files: `usage_aggregator.py`, `llm_usage_aggregator.py`
- Purpose: Aggregate request/usage logs to daily summaries (per user; and per provider/model for LLMs).
- Env/Settings:
  - `USAGE_LOG_ENABLED`, `USAGE_AGGREGATOR_INTERVAL_MINUTES`
  - `LLM_USAGE_AGGREGATOR_ENABLED`, `LLM_USAGE_AGGREGATOR_INTERVAL_MINUTES`

### Web Scraping Service (Enhanced)
- File: `tldw_Server_API/app/services/enhanced_web_scraping_service.py`
- Purpose: Production scraping pipeline with queueing, rate limiting, cookie/session support, and rich progress.
- Notes:
  - Uses Playwright if available; otherwise raises to trigger legacy fallback (`services/web_scraping_service.py`).
  - Persists scraped content into Media DB with chunk-level FTS.
  - Ephemeral mode stores results in an in-memory store (dev-only; see “Known Gaps”).

## Known Gaps and Recommendations

- Placeholders not production-ready:
  - `document_processing_service.py`, `ebook_processing_service.py`, `podcast_processing_service.py`, `xml_processing_service.py` - keep out of critical paths until completed and tested.
  - `ephemeral_store.py` is in-memory, non-thread-safe, and has no TTL. Replace with a bounded, TTL-backed store (e.g., Redis or a small SQLite table) for production.
  - Feature flag: set `PLACEHOLDER_SERVICES_ENABLED=1` (env) to enable these placeholders; otherwise they return 503 to prevent accidental use.

- Async/blocking mix:
  - Some persistence paths (e.g., storing scraped articles) call synchronous DB methods from async contexts. Wrap heavy sync calls with `asyncio.to_thread` to avoid event-loop blocking.

- Observability:
  - Jobs workers emit useful metrics; consider adding counters/timers to storage quota recalculation and temp cleanup.

- Tests:
  - Add integration tests for quota checks, breakdown, and cleanup. Mock filesystem with temporary dirs.
  - Add end-to-end tests for aggregators with seed rows in `usage_log` / `llm_usage_log`.
  - Add smoke tests for enhanced web scraping service initialization and fallback path.

## Quick Reference (Env Flags)

- Chatbooks jobs worker: `CHATBOOKS_JOBS_BACKEND`, `CHATBOOKS_CORE_WORKER_ENABLED`
- Jobs metrics gauges: `JOBS_METRICS_GAUGES_ENABLED`, interval and TTL flags above
- Aggregators: `DISABLE_USAGE_AGGREGATOR`, `DISABLE_LLM_USAGE_AGGREGATOR`
- Claims rebuild: `CLAIMS_REBUILD_ENABLED`, `CLAIMS_REBUILD_INTERVAL_SEC`

## Safety/Performance Notes

- Quota scanning runs in a small threadpool; avoid large max_workers to prevent I/O contention.
- Ensure user directories exist and have expected layout: `media`, `notes`, `embeddings`, `exports`, `temp`.
- PostgreSQL is recommended for multi-user deployments; SQLite supported for single-user.

---

For implementation details, see the service files referenced above and the startup wiring in `tldw_Server_API/app/main.py`.
