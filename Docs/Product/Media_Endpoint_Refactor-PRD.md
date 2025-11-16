# PRD: Modularization of /media Endpoints

- Title: Modularize and Refactor /media Endpoints
- Owner: Server API Team
- Status: Draft (v1)
- Target Version: v0.2.x

## Current Implementation Status

- Stage 1 (Skeleton & Utilities): **Complete**
  - `endpoints/media/` package and compatibility shim in place.
  - Shared utilities added under `api/v1/utils/` (`cache.py`, `http_errors.py`, `request_parsing.py`) with unit tests.
- Stage 2 (Read-Only Endpoints): **In Progress – core routes migrated**
  - `GET /api/v1/media` → `media/listing.py` and `GET /api/v1/media/{media_id}` → `media/item.py`, preserving TEST_MODE diagnostics and response shapes; added deterministic ETags.
  - Versions `GET /{media_id}/versions` and `GET /{media_id}/versions/{version}` → `media/versions.py` with existing DB logic and JSON unchanged.
  - `GET /metadata-search`, `GET /by-identifier`, `POST /search`, `GET /transcription-models` → `media/listing.py`, preserving normalization and envelopes and adding ETag support.
  - Router shim (`media/__init__.py`) defines a new `APIRouter` that includes `listing`, `item`, and `versions` routers ahead of `_legacy_media.router`, so new read-only routes override the monolith while all other `/media` routes still use the legacy implementation.
  - Follow-ups: align pytest harnesses (MediaDB2 metadata tests, media list/versions tests) with the new router wiring and add explicit ETag/cache invalidation tests.

## Background

- Current media endpoints live in a monolithic module with broad responsibilities: request parsing, auth/RBAC, rate limits, caching, input sourcing, processing orchestration, persistence, and response shaping.
- Key file: `tldw_Server_API/app/api/v1/endpoints/media.py`
- Existing processing libraries live under `tldw_Server_API/app/core/Ingestion_Media_Processing/` and DB logic under `tldw_Server_API/app/core/DB_Management/`.
- Tests exist for uploads, security, media processing, and web scraping.

## Problem Statement

- The monolith is hard to maintain and test due to tight coupling, duplicated patterns, and mixed concerns.
- Changes risk regressions across unrelated features.
- Onboarding and iteration speed are slowed by the file’s size and complexity.

## Goals

- Thin, declarative routers with clear separation of concerns.
- Service-oriented orchestration for ingestion, processing, and persistence.
- Shared utilities for caching, error mapping, request normalization, and input sourcing.
- Preserve existing API behavior, response shapes, and performance.
- Improve testability and maintainability.

## Non‑Goals

- No route path changes or breaking response shape changes.
- No DB schema changes.
- No rewrites of core ingestion libraries.
- No feature expansion beyond modularization.

## Stakeholders

- Backend engineers maintaining ingestion, RAG, and audio/video flows.
- QA/Testing owners for Media and Web Scraping.
- Frontend clients relying on current `/media` endpoints.

## Scope

- In-scope: All handlers under `/api/v1/media` including management (list/detail/versions), processing (no-DB paths), and ingest with persistence.
- Out-of-scope: Non-media endpoints; chat, audio streaming WS, MCP.

## Endpoint Inventory (Current → Target)

All routes share the `/api/v1/media` prefix. “ingest+persist” includes any endpoint that writes to the Media DB (ingest or update).

| Method | Path                                  | Type           | Target module            |
|--------|---------------------------------------|----------------|--------------------------|
| GET    | `/`                                   | read-only      | `listing.py`             |
| GET    | `/{media_id}`                         | read-only      | `item.py`                |
| GET    | `/{media_id}/versions`                | read-only      | `versions.py`            |
| GET    | `/{media_id}/versions/{version}`      | read-only      | `versions.py`            |
| POST   | `/{media_id}/versions`                | ingest+persist | `versions.py`            |
| DELETE | `/{media_id}/versions/{version}`      | ingest+persist | `versions.py`            |
| POST   | `/{media_id}/versions/rollback`       | ingest+persist | `versions.py`            |
| PUT    | `/{media_id}/versions/{version}/metadata` | ingest+persist | `versions.py`        |
| POST   | `/{media_id}/versions/advanced`       | ingest+persist | `versions.py`            |
| PATCH  | `/{media_id}/metadata`                | ingest+persist | `item.py`                |
| PUT    | `/{media_id}`                         | ingest+persist | `item.py`                |
| GET    | `/metadata-search`                    | read-only      | `listing.py`             |
| GET    | `/by-identifier`                      | read-only      | `listing.py`             |
| POST   | `/search`                             | read-only      | `listing.py`             |
| GET    | `/transcription-models`               | read-only      | `listing.py`             |
| POST   | `/add`                                | ingest+persist | `add.py`                 |
| POST   | `/process-code`                       | process-only   | `process_code.py`        |
| POST   | `/process-videos`                     | process-only   | `process_videos.py`      |
| POST   | `/process-audios`                     | process-only   | `process_audios.py`      |
| POST   | `/process-documents`                  | process-only   | `process_documents.py`   |
| POST   | `/process-pdfs`                       | process-only   | `process_pdfs.py`        |
| POST   | `/process-ebooks`                     | process-only   | `process_ebooks.py`      |
| POST   | `/process-emails`                     | process-only   | `process_emails.py`      |
| POST   | `/mediawiki/ingest-dump`              | ingest+persist | `mediawiki.py`           |
| POST   | `/mediawiki/process-dump`             | process-only   | `mediawiki.py`           |
| POST   | `/process-web-scraping`               | ingest+persist | `web_scrape.py`          |
| POST   | `/ingest-web-content`                 | ingest+persist | `web_scrape.py`          |
| GET    | `/debug/schema`                       | read-only      | `debug.py`               |

This table serves as a migration checklist to ensure the compatibility shim continues to cover all existing routes.

## Functional Requirements

- Endpoints unchanged:
  - List media and item details (e.g., `GET /api/v1/media`, `GET /api/v1/media/{media_id}`) and versions (list/create/rollback).
  - Processing endpoints (no DB): code, videos, audio, documents, PDFs, ebooks, emails.
  - Ingest + persist endpoint: `POST /api/v1/media/add`.
  - Web scraping ingest: `POST /api/v1/media/process-web-scraping` and `POST /api/v1/media/ingest-web-content`.
  - Debug schema endpoint: `GET /api/v1/media/debug/schema`.
- Shared utilities:
  - Caching with ETag/If-None-Match for GET list/detail (and search where applicable).
  - Error mapping for DB and processing exceptions.
  - Request normalization: robust form coercions, URL lists, booleans/ints.
  - Input sourcing: URL downloads, tempdirs, upload validation.
- Services:
  - Orchestrator for process-only flows (no DB).
  - Persistence service (DB writes, versions, keywords, claims).
- Keep:
  - AuthNZ and RBAC decorators.
  - Rate limiting and backpressure hooks.
  - Quota checks and metrics emission.
  - Claims extraction and analysis when enabled.

## Non‑Functional Requirements

- Performance: No regression; caching enabled for list/detail.
- Reliability: Transactions around persistence; clear cleanup semantics for temp dirs.
- Security: Preserve validation, RBAC, rate limits, and input file checks; no logging of secrets.
- Observability: Loguru usage consistent with `main.py`; metrics labels maintained.
- Testing: All existing tests pass; new unit tests for utilities (>80% coverage in new code).
- Compatibility: Keep `tldw_Server_API/app/api/v1/endpoints/media.py` as a compatibility shim exporting router.

## Success Metrics

- Monolith shrinks to shim; new package assumes routes.
- Cyclomatic complexity and size reduced per endpoint module.
- Test pass rate unchanged or improved; new unit tests for utilities.
- Endpoint latencies/throughput unchanged within measurement noise.
- Developer feedback shows faster iteration and onboarding.

## Technical Design

- Endpoints Package (new)
  - `tldw_Server_API/app/api/v1/endpoints/media/__init__.py` (exposes router, includes subrouters)
  - `tldw_Server_API/app/api/v1/endpoints/media/listing.py` (GET list/search/read-only utilities)
  - `tldw_Server_API/app/api/v1/endpoints/media/item.py` (GET, PATCH/PUT, DELETE)
  - `tldw_Server_API/app/api/v1/endpoints/media/versions.py` (GET versions, POST version, PUT/POST rollback/advanced)
  - `tldw_Server_API/app/api/v1/endpoints/media/add.py` (POST /add)
  - `tldw_Server_API/app/api/v1/endpoints/media/process_code.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/process_videos.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/process_audios.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/process_documents.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/process_emails.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/web_scrape.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/mediawiki.py`
  - `tldw_Server_API/app/api/v1/endpoints/media/debug.py`
- API Utilities (new)
  - `tldw_Server_API/app/api/v1/utils/cache.py`
    - Stateless helpers for ETag generation and If-None-Match handling (usable without Redis).
    - Optional Redis-backed storage keyed by route + query + media_id with `CACHE_TTL`, no-op when Redis is disabled or unavailable.
  - `tldw_Server_API/app/api/v1/utils/http_errors.py` (map `DatabaseError`/`SchemaError`/`InputError`/`ConflictError` to FastAPI `HTTPException`)
  - `tldw_Server_API/app/api/v1/utils/request_parsing.py` (form coercions, URL list normalization, safe bool/int parsing)
- Core Orchestration (new)
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/pipeline.py`
    - Input resolution (URL or upload) → type-specific processor → standard result list.
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/input_sourcing.py`
    - Wraps `_download_url_async`, `Upload_Sink.process_and_validate_file`, tempdir lifecycle.
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/result_normalization.py`
    - Uniform `MediaItemProcessResponse` shape: status, metadata, content, chunks, analysis, claims, warnings.
    - Normalization is internal; HTTP responses preserve existing envelopes (e.g., `batch_result` with `results`, `errors`, `processed_count`, `errors_count` and legacy aliases like `results` vs `items`).
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
    - DB transactions, version creation, keywords, claims storage.
- Compatibility Shim
  - `tldw_Server_API/app/api/v1/endpoints/media.py` re-exports router from the new package (and can be re-pointed to a `_legacy_media.py` module for backout).
- Caching Design
  - Generate ETag based on a deterministic serialization of the response content (sorted keys, stable item ordering; exclude volatile fields such as timestamps when possible).
  - Honor If-None-Match; return 304 when matched.
  - Configurable TTL via `config['CACHE_TTL']`; when Redis is disabled or unavailable, fall back to stateless ETag behavior without caching errors surfacing to clients.
  - Invalidate list/detail/search cache entries on operations that change media content or metadata, including `/add`, item updates, version create/update/delete/rollback, MediaWiki ingest, and web scraping ingest endpoints.
- Error Mapping
  - `DatabaseError` → 500 (unless refined by context, e.g., not found → 404).
  - `SchemaError` → 500 with clear log context for schema/migration issues.
  - `InputError` → 400/422 based on validation context.
  - `ConflictError` → 409 for resource conflicts.
  - Transient Redis/cache errors are logged and treated as cache misses (no change to HTTP status); no secrets in error messages.
- Security & AuthNZ
  - Preserve `Depends(get_request_user)`, `PermissionChecker(MEDIA_CREATE)`, `rbac_rate_limit("media.create")`, and `guard_backpressure_and_quota` on routes that modify data.
  - Keep file extension allowlists per media type and size caps.
  - Maintain URL safety checks and content-type based filtering.

## API Compatibility

- No changes to route paths, query params, or body schemas.
- Response models remain per `tldw_Server_API/app/api/v1/schemas/media_response_models.py`.
- Request models remain per `tldw_Server_API/app/api/v1/schemas/media_request_models.py` (allow internal re-exports only).
- Process-only endpoints preserve existing semantics for partial success:
  - 200 when all items succeed.
  - 207 when at least one item succeeds and at least one fails.
  - 400 when no valid inputs are provided.
  - 500 only for unrecoverable server errors.
- Per-input errors remain itemized in the batch response; they are not collapsed into a single top-level error string.

## Data Model Impact

- None. All DB operations continue via `MediaDatabase` and existing DB helpers.

## Telemetry & Metrics

- Maintain existing counters for uploads, bytes, and per-route usage events.
- Preserve TEST_MODE diagnostics behavior (including headers such as `X-TLDW-DB-Path` and `X-TLDW-List-Total` and existing `TEST_MODE: ...` log messages) while confining implementations to helpers/utilities to reduce handler clutter.

## Rollout & Backout

- Rollout: Incremental PRs per stage; keep shim in place; run full pytest suite after each stage.
- Backout: Keep a `_legacy_media.py` (or equivalent) monolith alongside the new package and re-point the `media.py` compatibility shim back to that module to restore previous behavior without a repo-wide git revert (no DB migrations involved).

## Risks & Mitigations

- Tests patch internals of `media.py`: keep temporary re-exports of commonly patched functions in the shim.
- Route order conflicts: keep `/{media_id:int}` with type converter and preserve registration order.
- Behavior drift in form coercion: centralize and add unit tests in `utils/request_parsing.py`.
- Unexpected perf cost from caching: keep cache optional; measure and tune TTL, ETag generation, and key design.

## Acceptance Criteria

- All existing tests pass:
  - `tldw_Server_API/tests/Media/*`
  - `tldw_Server_API/tests/http_client/test_media_download_helper.py`
  - `tldw_Server_API/tests/Web_Scraping/test_friendly_ingest_crawl_flags.py`
- New unit tests for cache, request parsing, input sourcing, normalization, and error mapping at >80% coverage for new code.
- Explicit tests for:
  - Cache invalidation (list/detail/search caches after create/update/delete/rollback and ingest endpoints).
  - Error mapping (`DatabaseError`, `SchemaError`, `InputError`, `ConflictError`, and generic `Exception` paths).
  - ETag behavior (match/mismatch cases for list/detail/search).
- API responses identical for representative golden cases across endpoints (see Golden Samples appendix).
- Logs and metrics preserved; no sensitive leakage.

## Open Questions

- Stage 0/1 action: Inventory any external integrations or tests that patch/import internal helpers from `media.py`, and list functions to re-export from the shim for at least one release cycle.
- Should we add a feature flag to force the old router? Default plan relies on the shim; a flag is optional but may simplify backout in some deployments.

## Timeline (Rough)

- Design and approval: 1–2 days
- Utilities + skeleton package: 1 day
- List/Item/Versions extraction: 1–2 days
- Process-only endpoints: 3–4 days
- `/add` persistence extraction: 2–3 days
- Web scraping extraction: 1 day
- Cleanup + docs + final tests: 1–2 days
- Total: ~10–15 working days

## Dependencies

- Redis (optional cache).
- Existing core modules: Upload sink, PDF/Doc/AV processors, DB management, usage/metrics.
- AuthNZ dependencies and rate limiters.

## Implementation Plan

- Stage 0: PRD Sign‑Off
  - Deliverable: Approved PRD.
  - Exit: Stakeholder sign-off, plus inventory of external imports/patches of `media.py` helpers to inform shim re-exports.
- Stage 1: Skeleton & Utilities **(Status: Complete)**
  - Create `endpoints/media/` package with `__init__.py` exporting router.
  - Add `api/v1/utils/cache.py`, `utils/http_errors.py`, `utils/request_parsing.py`.
  - Keep `endpoints/media.py` as shim importing router from package.
  - Tests: unit tests for cache and parsing utilities.
- Stage 2: Read‑Only Endpoints **(Status: In Progress – core routes migrated)**
  - Move `GET /api/v1/media` and `GET /api/v1/media/{media_id}` to `listing.py` and `item.py`.
    - Implemented in `media/listing.py` (`GET /`) and `media/item.py` (`GET /{media_id:int}`), preserving TEST_MODE headers/logs and response shapes; added deterministic ETag support via `utils/cache`.
  - Move versions `GET /{media_id}/versions` and `GET /{media_id}/versions/{version}` to `versions.py`.
    - Implemented in `media/versions.py` (`GET /{media_id:int}/versions`, `GET /{media_id:int}/versions/{version_number:int}`) with existing DB queries and JSON structure untouched.
  - Move `GET /metadata-search`, `GET /by-identifier`, `POST /search`, and `GET /transcription-models` into `listing.py`.
    - Implemented in `media/listing.py` (`GET /metadata-search`, `GET /by-identifier`, `POST /search`, `GET /transcription-models`) using the same normalization and batch response envelopes; ETags now use `utils/cache.generate_etag`.
  - Apply cache decorator/ETag support for list/detail/search as implemented in `cache.py`.
    - Implemented as stateless ETag calculation + `If-None-Match` handling; Redis-backed response caching remains in `_legacy_media` for now.
  - Router wiring:
    - `media/__init__.py` now prepends new `listing`, `item`, and `versions` routes ahead of `_legacy_media.router` while preserving all existing imports/monkeypatch points (`cache`, `_download_url_async`, `_save_uploaded_files`, etc.).
  - Tests: run Media list/detail/version/search tests; verify ETag behavior on list/detail/search and cache invalidation after updates.
    - Status: new handlers pass direct ASGI client probes; selected pytest suites (`MediaDB2` metadata tests, `Media_Ingestion_Modification` list/versions tests) are still being reconciled with the new router wiring.
- Stage 3: Process‑Only Endpoints
  - Create core orchestrator: `pipeline.py`, `input_sourcing.py`, `result_normalization.py`.
  - Move `process_code`, `process_documents`, `process_pdfs`, `process_ebooks`, `process_emails`, `process_videos`, `process_audios` into dedicated files; handlers delegate to orchestrator.
  - Tests: adapt existing tests; add unit tests for input sourcing, normalization, and HTTP status code semantics for partial success.
- Stage 4: Persistence Path (`/add`)
  - Create `persistence.py` with transactional DB writes, keyword tagging, claims storage.
  - Extract `/add` endpoint to `add.py`; reuse orchestrator for processing and call persistence layer.
  - Preserve quotas, metrics, and claims feature flags.
  - Tests: `/add` end-to-end tests; quota, error mapping, and cache invalidation coverage.
- Stage 5: Web Scraping
  - Move `/process-web-scraping` handler to `web_scrape.py`; ensure it delegates to `services/web_scraping_service`.
  - Move `/ingest-web-content` handler to `web_scrape.py`; share request normalization and orchestration with the process-only handler while preserving DB persistence behavior.
  - Tests: web scraping tests (crawl flags, summarization toggles, ingest vs ephemeral modes).
- Stage 6: Debug Endpoint
  - Move schema introspection to `debug.py`.
  - Tests: basic health assertions.
- Stage 7: Cleanup & Docs
  - Ensure `media.py` shim only re-exports router (and any temporary compatibility helpers identified in Stage 0/1).
  - Update docs:
    - `Docs/Code_Documentation/Ingestion_Media_Processing.md`
    - `Docs/Code_Documentation/Ingestion_Pipeline_*`
    - Add `Docs/Design/Media_Endpoint_Refactor.md` overview.
  - Tests: full suite with coverage.
- Definition of Done (per stage)
  - Tests passing (unit + integration for impacted endpoints).
  - Response shapes verified with golden samples.
  - Lint/format per project conventions.
  - Logs clean; no sensitive data exposure.
  - Update CHANGELOG (internal note only; no external API changes).
- Validation Steps
  - Run: `python -m pytest -v`
  - Coverage: `python -m pytest --cov=tldw_Server_API --cov-report=term-missing`
  - Manual: spot-check `/api/v1/media` list/detail, `/add`, `/process-*`, MediaWiki, and web scraping endpoints.

## Backout Plan

- Switch the `media.py` shim to re-export the monolithic `_legacy_media.py` router while leaving the refactored package in place, then revert shim back to the new package once issues are resolved.

## Golden Samples (Appendix)

- Maintain a set of representative request/response “golden” samples for:
  - List and detail endpoints (`GET /api/v1/media`, `GET /api/v1/media/{media_id}`).
  - `/add` ingestion flows (URLs and uploads).
  - Each process-* endpoint (code, videos, audio, documents, PDFs, ebooks, emails, MediaWiki, web scraping).
  - Search endpoints (`/search`, `/metadata-search`, `/by-identifier`).
- Encode these samples as fixtures in the test suite to assert byte-for-byte compatibility (excluding expected non-deterministic fields like timestamps and IDs).
