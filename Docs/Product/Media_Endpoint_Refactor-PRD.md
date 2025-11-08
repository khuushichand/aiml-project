PRD: Modularization of /media Endpoints

  - Title: Modularize and Refactor /media Endpoints
  - Owner: Server API Team
  - Status: Draft (v1)
  - Target Version: v0.2.x

  Background

  - Current media endpoints live in a monolithic module with broad responsibilities: request parsing, auth/RBAC, rate limits, caching, input sourcing, processing orchestration, persistence, and response shaping.
  - Key file: tldw_Server_API/app/api/v1/endpoints/media.py
  - Existing processing libraries live under tldw_Server_API/app/core/Ingestion_Media_Processing/ and DB logic under tldw_Server_API/app/core/DB_Management/.
  - Tests exist for uploads, security, media processing, and web scraping.

  Problem Statement

  - The monolith is hard to maintain and test due to tight coupling, duplicated patterns, and mixed concerns.
  - Changes risk regressions across unrelated features.
  - Onboarding and iteration speed are slowed by the file’s size and complexity.

  Goals

  - Thin, declarative routers with clear separation of concerns.
  - Service-oriented orchestration for ingestion, processing, and persistence.
  - Shared utilities for caching, error mapping, request normalization, and input sourcing.
  - Preserve existing API behavior, response shapes, and performance.
  - Improve testability and maintainability.

  Non‑Goals

  - No route path changes or breaking response shape changes.
  - No DB schema changes.
  - No rewrites of core ingestion libraries.
  - No feature expansion beyond modularization.

  Stakeholders

  - Backend engineers maintaining ingestion, RAG, and audio/video flows.
  - QA/Testing owners for Media and Web Scraping.
  - Frontend clients relying on current /media endpoints.

  Scope

  - In-scope: All handlers under /api/v1/media including management (list/detail/versions), processing (no-DB paths), and ingest with persistence.
  - Out-of-scope: Non-media endpoints; chat, audio streaming WS, MCP.

  Functional Requirements

  - Endpoints unchanged:
      - List media, item details, versions (list/create/rollback).
      - Processing endpoints (no DB): code, videos, documents, PDFs, ebooks, emails.
      - Ingest + persist endpoint: POST /api/v1/media/add.
      - Web scraping ingest: POST /api/v1/media/process-web-scraping.
      - Debug schema endpoint.
  - Shared utilities:
      - Caching with ETag/If-None-Match for GET list/detail.
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

  Non‑Functional Requirements

  - Performance: No regression; caching enabled for list/detail.
  - Reliability: Transactions around persistence; clear cleanup semantics for temp dirs.
  - Security: Preserve validation, RBAC, rate limits, and input file checks; no logging of secrets.
  - Observability: Loguru usage consistent with main.py; metrics labels maintained.
  - Testing: All existing tests pass; new unit tests for utilities (>80% coverage in new code).
  - Compatibility: Keep tldw_Server_API/app/api/v1/endpoints/media.py as a compatibility shim exporting router.

  Success Metrics

  - Monolith shrinks to shim; new package assumes routes.
  - Cyclomatic complexity and size reduced per endpoint module.
  - Test pass rate unchanged or improved; new unit tests for utilities.
  - Endpoint latencies/throughput unchanged within measurement noise.
  - Developer feedback shows faster iteration and onboarding.

  Technical Design

  - Endpoints Package (new)
      - tldw_Server_API/app/api/v1/endpoints/media/__init__.py (exposes router, includes subrouters)
      - tldw_Server_API/app/api/v1/endpoints/media/listing.py (GET list/search if exists)
      - tldw_Server_API/app/api/v1/endpoints/media/item.py (GET, PATCH/PUT, DELETE)
      - tldw_Server_API/app/api/v1/endpoints/media/versions.py (GET versions, POST version, PUT rollback)
      - tldw_Server_API/app/api/v1/endpoints/media/add.py (POST /add)
      - tldw_Server_API/app/api/v1/endpoints/media/process_code.py
      - tldw_Server_API/app/api/v1/endpoints/media/process_videos.py
      - tldw_Server_API/app/api/v1/endpoints/media/process_documents.py
      - tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py
      - tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py
      - tldw_Server_API/app/api/v1/endpoints/media/process_emails.py
      - tldw_Server_API/app/api/v1/endpoints/media/web_scrape.py
      - tldw_Server_API/app/api/v1/endpoints/media/debug.py
  - API Utilities (new)
      - tldw_Server_API/app/api/v1/utils/cache.py (ETag generation, If-None-Match, TTL)
      - tldw_Server_API/app/api/v1/utils/http_errors.py (map DatabaseError/InputError/ConflictError to FastAPI HTTPException)
      - tldw_Server_API/app/api/v1/utils/request_parsing.py (form coercions, URL list normalization, safe bool/int parsing)
  - Core Orchestration (new)
      - tldw_Server_API/app/core/Ingestion_Media_Processing/pipeline.py
          - Input resolution (URL or upload) → type-specific processor → standard result list
      - tldw_Server_API/app/core/Ingestion_Media_Processing/input_sourcing.py
          - Wraps _download_url_async, Upload_Sink.process_and_validate_file, tempdir lifecycle
      - tldw_Server_API/app/core/Ingestion_Media_Processing/result_normalization.py
          - Uniform MediaItemProcessResponse shape: status, metadata, content, chunks, analysis, claims, warnings
      - tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py
          - DB transactions, version creation, keywords, claims storage
  - Compatibility Shim
      - tldw_Server_API/app/api/v1/endpoints/media.py re-exports router from the new package.
  - Caching Design
      - Generate ETag based on response content hash (excluding volatile fields).
      - Honor If-None-Match; return 304 when matched.
      - Configurable TTL via config['CACHE_TTL']; disable when Redis disabled.
  - Error Mapping
      - DatabaseError → 500 (unless refined by context, e.g., not found → 404).
      - InputError → 400/422 based on validation context.
      - ConflictError → 409 for resource conflicts.
      - Graceful fallbacks to 500 with safe messages (no secrets).
  - Security & AuthNZ
      - Preserve Depends(get_request_user), PermissionChecker(MEDIA_CREATE), and rbac_rate_limit("media.create") on routes that modify data.
      - Keep file extension allowlists per media type and size caps.
      - Maintain URL safety checks and content-type based filtering.

  API Compatibility

  - No changes to route paths, query params, or body schemas.
  - Response models remain per tldw_Server_API/app/api/v1/schemas/media_response_models.py:1.
  - Request models remain per tldw_Server_API/app/api/v1/schemas/media_request_models.py:1 (allow internal re-exports only).

  Data Model Impact

  - None. All DB operations continue via MediaDatabase and existing DB helpers.

  Telemetry & Metrics

  - Maintain existing counters for uploads, bytes, and per-route usage events.
  - Keep TEST_MODE diagnostics behavior, but confine to helpers to reduce handler clutter.

  Rollout & Backout

  - Rollout: Incremental PRs per stage; keep shim in place; run full pytest suite after each stage.
  - Backout: Revert to previous media.py monolith; keep migrations isolated to code structuring (no DB migration).

  Risks & Mitigations

  - Tests patch internals of media.py: keep temporary re-exports of commonly patched functions in the shim.
  - Route order conflicts: keep /{media_id:int} with type converter and preserve registration order.
  - Behavior drift in form coercion: centralize and add unit tests in utils/request_parsing.py.
  - Unexpected perf cost from caching: keep cache optional; measure and tune TTL and ETag generation.

  Acceptance Criteria

  - All existing tests pass:
      - tldw_Server_API/tests/Media/*
      - tldw_Server_API/tests/http_client/test_media_download_helper.py
      - tldw_Server_API/tests/Web_Scraping/test_friendly_ingest_crawl_flags.py
  - New unit tests for cache, request parsing, input sourcing, and normalization at >80% coverage.
  - API responses identical for representative golden cases across endpoints.
  - Logs and metrics preserved; no sensitive leakage.

  Open Questions

  - Do any external integrations or clients patch/import internal helpers from media.py? If yes, list to re-export for one release cycle.
  - Should we add a feature flag to force old router? Default plan relies on shim; a flag is optional.

  Timeline (Rough)

  - Design and approval: 1–2 days
  - Utilities + skeleton package: 1 day
  - List/Item/Versions extraction: 1–2 days
  - Process-only endpoints: 3–4 days
  - /add persistence extraction: 2–3 days
  - Web scraping extraction: 1 day
  - Cleanup + docs + final tests: 1–2 days
  - Total: ~10–15 working days

  Dependencies

  - Redis (optional cache).
  - Existing core modules: Upload sink, PDF/Doc/AV processors, DB management, usage/metrics.
  - AuthNZ dependencies and rate limiters.

  Implementation Plan

  - Stage 0: PRD Sign‑Off
      - Deliverable: Approved PRD.
      - Exit: Stakeholder sign-off.
  - Stage 1: Skeleton & Utilities
      - Create endpoints/media/ package with __init__.py exporting router.
      - Add api/v1/utils/cache.py, utils/http_errors.py, utils/request_parsing.py.
      - Keep endpoints/media.py as shim importing router from package.
      - Tests: unit tests for cache and parsing utilities.
  - Stage 2: Read‑Only Endpoints
      - Move GET list and GET item to listing.py and item.py.
      - Move versions GET/POST/PUT to versions.py.
      - Apply cache decorator for list/detail.
      - Tests: run Media list/detail/version tests; verify ETag behavior on list/detail.
  - Stage 3: Process‑Only Endpoints
      - Create core orchestrator: pipeline.py, input_sourcing.py, result_normalization.py.
      - Move process_code, process_documents, process_pdfs, process_ebooks, process_emails, process_videos into dedicated files; handlers delegate to orchestrator.
      - Tests: adapt existing tests; add unit tests for input sourcing and normalization.
  - Stage 4: Persistence Path (/add)
      - Create persistence.py with transactional DB writes, keyword tagging, claims storage.
      - Extract /add endpoint to add.py; reuse orchestrator for processing and call persistence layer.
      - Preserve quotas, metrics, and claims feature flags.
      - Tests: /add end-to-end tests; quota and error mapping coverage.
  - Stage 5: Web Scraping
      - Move handler to web_scrape.py; ensure it delegates to services/web_scraping_service.
      - Tests: web scraping tests (crawl flags, summarization toggles).
  - Stage 6: Debug Endpoint
      - Move schema introspection to debug.py.
      - Tests: basic health assertions.
  - Stage 7: Cleanup & Docs
      - Ensure media.py shim only re-exports router.
      - Update docs:
          - Docs/Code_Documentation/Ingestion_Media_Processing.md
          - Docs/Code_Documentation/Ingestion_Pipeline_*
          - Add Docs/Design/Media_Endpoint_Refactor.md overview.
      - Tests: full suite with coverage.
  - Definition of Done (per stage)
      - Tests passing (unit + integration for impacted endpoints).
      - Response shapes verified with golden samples.
      - Lint/format per project conventions.
      - Logs clean; no sensitive data exposure.
      - Update CHANGELOG (internal note only; no external API changes).
  - Validation Steps
      - Run: python -m pytest -v
      - Coverage: python -m pytest --cov=tldw_Server_API --cov-report=term-missing
      - Manual: spot-check /api/v1/media list/detail, /add, /process-* endpoints.
  - Backout Plan
      - Revert to last commit where media.py monolith was active.
      - Keep compatibility shim until next minor release.