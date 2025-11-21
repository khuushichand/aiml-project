# Media Endpoint Refactor – Design Overview

## Goals

- Modularize the `/api/v1/media` surface into focused endpoint modules.
- Move ingestion and persistence logic into core helpers under `Ingestion_Media_Processing`.
- Keep external API contracts, response shapes, and status codes unchanged.
- Retain `_legacy_media.py` only as a compatibility layer for older imports and tests.
- Support an opt-in **legacy-free** mode driven by `TLDW_DISABLE_LEGACY_MEDIA=1`.

## High-Level Architecture

### Routers and Packages

- Legacy monolith:
  - `tldw_Server_API/app/api/v1/endpoints/_legacy_media.py`
  - Historically owned all `/media` endpoints, request parsing, processing orchestration, persistence, and caching.
  - Now acts primarily as:
    - A router containing historical endpoint definitions.
    - Shim functions that delegate to modular endpoints and core helpers.
    - A small set of shared constants, enums, and Pydantic form models.

- Modular package:
  - `tldw_Server_API/app/api/v1/endpoints/media/`
  - Provides the canonical router and endpoint modules:
    - `__init__.py` – router builder + helper shim (see below).
    - `add.py` – `/api/v1/media/add` ingest-and-persist.
    - `listing.py` – `GET /api/v1/media`, `/metadata-search`, `/by-identifier`, `/search`, `/transcription-models`.
    - `item.py` – `GET /api/v1/media/{media_id}`, `PUT /api/v1/media/{media_id}`.
    - `versions.py` – version listing, creation, update, rollback, and delete.
    - Process-only:
      - `process_code.py`, `process_documents.py`, `process_pdfs.py`,
        `process_ebooks.py`, `process_emails.py`,
        `process_videos.py`, `process_audios.py`,
        `process_mediawiki.py`, `process_web_scraping.py`.
    - Other:
      - `ingest_web_content.py`, `debug.py`, `transcription_models.py`.

- Shim package entry:
  - Importing `tldw_Server_API.app.api.v1.endpoints.media` resolves to the
    `media/__init__.py` package shim, not a separate `media.py` file.
  - That `__init__.py` file builds the combined router (modular endpoints
    plus optional `_legacy_media` router) and re-exports a small set of
    helpers (`_download_url_async`, `_save_uploaded_files`, `TempDirManager`,
    `file_validator_instance`, cache helpers, and processor shims) so
    existing imports of `...endpoints.media` continue to work.

### Core Ingestion and Persistence Helpers

- Module: `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
  - Canonical `/media/add` helpers:
    - `add_media_persist(...)` – public entry point used by `media/add.py`; performs basic request setup and delegates to `add_media_orchestrate(...)`.
    - `add_media_orchestrate(...)` – owns the end-to-end ingest pipeline:
      - Temp directory management (via `TempDirManager`).
      - URL/file normalization and upload saving (via `save_uploaded_files`).
      - Quota/backpressure checks.
      - Per-type dispatch:
        - Audio/Video: `process_batch_media(...)`.
        - Documents/ebooks/emails/JSON: `process_document_like_item(...)`.
      - Optional embeddings / claims extraction.
      - Final status selection and result normalization.
    - `process_batch_media(...)` – canonical helper for A/V inline ingestion:
      - Pre-checks existing media for overwrite behavior (using `MediaDatabase`).
      - Orchestrates `Video_DL_Ingestion_Lib.process_videos` / `Audio_Files.process_audio_files`.
      - Calls `persist_primary_av_item(...)` for DB writes and claims persistence.
    - `process_document_like_item(...)` – canonical helper for document-like items:
      - Handles URL/download preparation with SSRF guards.
      - Dispatches to processors for `pdf` / `document` / `ebook` / `json` / `email` and email archives.
      - Calls `persist_doc_item_and_children(...)` to write parent and child items plus claims.
    - `persist_primary_av_item(...)`, `persist_doc_item_and_children(...)`:
      - Perform Media DB writes and ingestion-time claims persistence (`claims_utils.persist_claims_if_applicable`).
      - Standardize envelopes (`status`, `input_ref`, `processing_source`, `media_type`, `metadata`,
        `content`/`transcript`, chunks, analysis, claims, `db_id`, `db_message`, `media_uuid`).

- Other core helpers:
  - `input_sourcing.py`
    - `TempDirManager` – lifecycle of per-request temp directories.
    - `save_uploaded_files(...)` – saves `UploadFile` objects to disk with safe filenames.
  - `download_utils.py`
    - `download_url_async(...)` – shared URL→file helper:
      - Centralizes HTTP fetching, timeouts, and content-type checks.
      - Provides TEST_MODE stubs for selected hosts so JSON/document tests do not require real network access.
  - `result_normalization.py`, `pipeline.py`
    - `MediaItemProcessResponse`, `ProcessItem`, `run_batch_processor(...)` – unify batch semantics and counters for process-only endpoints.

### Process-Only Endpoint Patterns (Current State)

- Shared pipeline pattern:
  - `process_pdfs.py`, `process_ebooks.py`, `process_emails.py`:
    - Use `TempDirManager` + `media._save_uploaded_files` to stage inputs.
    - Build `ProcessItem` instances and call `run_batch_processor(...)`
      around the existing per-type processors, preserving legacy result
      envelopes and 200/207/400 status semantics.
  - `process_documents.py`:
    - Uses the same staging helpers plus `media._download_url_async` for
      URL inputs, then builds `ProcessItem` items and calls
      `run_batch_processor(...)` with a `_document_batch_processor` that
      bridges to `Plaintext_Files.process_document_content` and normalizes
      batch results.
  - `process_code.py`:
    - Uses `TempDirManager` + `media._save_uploaded_files` /
      `media._download_url_async`, builds `ProcessItem` items, then runs
      them through `run_batch_processor(...)` with a per-item processor
      that performs language detection and line/code chunking while keeping
      the legacy batch envelope and counters.

- Intentional bespoke/exception cases:
  - `process_audios.py`, `process_videos.py`:
    - Use the shared upload/TempDir helpers but delegate orchestration to
      the core audio/video batch helpers that also power `/media/add`
      (rather than `run_batch_processor(...)`), so A/V processing remains
      aligned between process-only and ingest-and-persist flows.
  - `process_mediawiki.py`:
    - Implements streaming NDJSON-style responses for MediaWiki imports and
      does not use `run_batch_processor(...)`; this is an intentional
      divergence due to long-running, incremental processing.
  - `process_web_scraping.py`:
    - Delegates to the web scraping service layer for orchestration and
      returns already-normalized batch results; it does not go through
      `run_batch_processor(...)` and is treated as a documented special
      case.

## Media Shim Behavior (`endpoints/media/__init__.py`)

### Legacy-Aware Router Construction

- Environment flag:
  - `TLDW_DISABLE_LEGACY_MEDIA` (string; values `1`, `true`, `yes`, `on` are treated as enabled).

- When legacy is **enabled** (default):
  - The module attempts to import `_legacy_media` and obtain its `router`.
  - A combined router is built by **prepending** modular routes ahead of legacy routes:
    - Keeps path/verb behavior backward compatible.
    - Ensures modular `listing` / `item` / `versions` / `add` / `process_*` handlers handle
      traffic for overlapping paths.
  - If `_legacy_media` fails to import (e.g. missing optional audio/ML deps in minimal test profiles),
    - A fallback router exposes only modular endpoints to keep focused tests runnable.

- When legacy is **disabled** (`TLDW_DISABLE_LEGACY_MEDIA=1`):
  - `_legacy_media` is set to `None`.
  - The combined router is built **only** from modular endpoint modules.
  - All hot `/media` paths are owned by `endpoints/media` + core helpers.

### Helper Re-Exports

- `endpoints/media/__init__.py` exposes commonly patched helpers so tests and
  external integrations can depend on `endpoints.media` rather than `_legacy_media`:
  - `_download_url_async`
    - Legacy mode: forwarded from `_legacy_media._download_url_async` when present.
    - Legacy-free mode: bound to `download_utils.download_url_async`.
  - `_save_uploaded_files`, `TempDirManager`
    - Legacy mode: proxy to `_legacy_media` implementations, falling back to core helpers.
    - Legacy-free mode: direct aliases of `input_sourcing.save_uploaded_files` and `TempDirManager`.
  - `file_validator_instance`
    - Resolved from `API_Deps.validations_deps`, with a legacy fallback.
  - `_process_document_like_item`
    - Thin async wrapper that imports `persistence.process_document_like_item` at call time.
    - Ensures patches applied to `persistence.process_document_like_item` in tests are visible
      to callers that use `endpoints.media._process_document_like_item`.
  - `books`, `pdf_lib`, `docs`
    - Imported from the corresponding core ingestion libraries and exported at module scope.
  - `aiofiles`
    - Exposes the `aiofiles` module used by core upload helpers so tests can monkeypatch
      `endpoints.media.aiofiles.open` to simulate write failures.

### Cache Shim

- Legacy redis-backed cache:
  - `_legacy_media.py` defines `cache`, `cache_response`, `invalidate_cache` when Redis is enabled.
  - Many tests monkeypatch `endpoints.media.cache` and assert behavior through the shim.

- Legacy-free behavior:
  - When `_legacy_media` is `None`, `endpoints/media/__init__.py`:
    - Provides an in-memory `_DummyCache` with a Redis-like API (`setex`, `get`, `delete`, `sadd`,
      `smembers`, `expire`, `scan`).
    - Implements `cache_response(key, response)`:
      - Computes an ETag and serializes the response to JSON.
      - Stores `"etag|content"` under a cache key and maintains an index set per media ID.
    - Implements `invalidate_cache(media_id)`:
      - Deletes cached entries via the index set when available.
      - Falls back to `scan`-based deletion for matching keys.
  - When `_legacy_media` is present:
    - `cache_response` / `invalidate_cache` delegate to legacy implementations while temporarily
      swapping in the shim’s `cache` object so monkeypatches still work.

## `_legacy_media.py` Compatibility Layer

- Current responsibilities:
  - Router definitions for historical endpoints that forward into modular implementations:
    - List, detail, versioning, `/media/add`, process-only routes, web scraping orchestrators.
  - Shared constants and Pydantic form models for code/process/add endpoints.
  - Some shared helpers still used by modules outside `endpoints/media` or by older integrations.

- Shims into core/modular behavior:
  - `_process_batch_media(...)`:
    - Thin wrapper that imports and awaits `persistence.process_batch_media(...)`.
  - `_process_document_like_item(...)`:
    - Thin wrapper around `persistence.process_document_like_item(...)`.
  - Endpoint shims like `list_media_endpoint` and `process_code_endpoint`:
    - Import the corresponding implementation from `endpoints/media/*` and forward all parameters.

- Dead-code status:
  - Helpers not referenced by modular endpoints, core ingestion modules, or the test suite are
    treated as deprecated/legacy-only.
  - The file is intentionally **not** the source of truth for `/media` behavior; new work should
    target core helpers and modular endpoints and add shims here only when required for
    backwards compatibility.

## Legacy-Free Media Mode

- Flag: `TLDW_DISABLE_LEGACY_MEDIA=1`
  - Recognized values: `1`, `true`, `yes`, `on` (case-insensitive).
  - Effects:
    - `_legacy_media` is not imported.
    - The exported `router` is composed solely from modular endpoints.
    - Shim helpers (`_download_url_async`, `_save_uploaded_files`, `TempDirManager`,
      `_process_document_like_item`, `file_validator_instance`, `books`, `pdf_lib`, `docs`,
      `aiofiles`, `cache`, `cache_response`, `invalidate_cache`) are all backed by core modules
      or in-memory implementations.

- Test strategy:
  - The Media suites are expected to run cleanly both:
    - With default settings (legacy router present, but modular handlers own most behavior).
    - With `TLDW_DISABLE_LEGACY_MEDIA=1` (legacy router absent).
  - Important suites:
    - `tldw_Server_API/tests/Media/`
    - `tldw_Server_API/tests/MediaIngestion_NEW/`
    - `tldw_Server_API/tests/Media_Ingestion_Modification/`
  - Golden-envelope tests patch helpers via `tldw_Server_API.app.api.v1.endpoints.media`
    so that they remain valid in both modes.

## How to Extend `/media` Safely

- Business logic:
  - Add new core helpers under `core/Ingestion_Media_Processing/` when implementing new
    ingestion behavior (e.g., new media types or pipelines).
  - Keep functions DB-agnostic when possible and rely on persistence helpers for writes.

- API surface:
  - Add new endpoints under `api/v1/endpoints/media/` in their own modules.
  - Wire new routers via `media/__init__.py`.
  - If an older endpoint in `_legacy_media.py` must forward to the new behavior, implement a
    thin wrapper there that imports from the modular module.

- Tests:
  - Prefer patching via `tldw_Server_API.app.api.v1.endpoints.media` and core modules, not
    `_legacy_media`.
  - Add integration tests under `MediaIngestion_NEW` or `Media` mirroring existing patterns.
  - Verify behavior with and without `TLDW_DISABLE_LEGACY_MEDIA=1`.

## References

- PRD: `Docs/Product/Media_Endpoint_Refactor-PRD.md`
- Core ingestion docs: `Docs/Code_Documentation/Ingestion_Media_Processing.md`
- Chunking docs: `Docs/Code_Documentation/Chunking-Module.md`
- Claims design: `Docs/Design/ingestion_claims.md`

## Canonical Import Paths (For Contributors)

- For **API behavior** under `/api/v1/media`:
  - Import routers and helpers from `tldw_Server_API.app.api.v1.endpoints.media` and its submodules.
  - Example: use `endpoints.media._process_document_like_item` in tests instead of `_legacy_media._process_document_like_item`.
- For **core ingestion/business logic**:
  - Import from `tldw_Server_API.app.core.Ingestion_Media_Processing.*` (e.g. `persistence`, `input_sourcing`, `download_utils`).
- `_legacy_media.py`:
  - Treated as a compatibility layer only.
  - New code **must not** import `_legacy_media` directly; add behavior in core + modular endpoints, and introduce shims in `_legacy_media` only when strictly required for backwards compatibility.
