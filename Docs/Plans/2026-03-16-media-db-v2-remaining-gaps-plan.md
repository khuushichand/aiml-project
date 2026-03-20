# Media DB v2 Remaining Gaps Plan

**Purpose**: Document the remaining Media DB refactor surface after the phase-1 extraction work so follow-on slices can be executed deliberately, with explicit boundaries, owners, and stop conditions.

## Current Snapshot

- `Media_DB_v2.py`: 16,386 lines
- `ChaChaNotes_DB.py`: 24,237 lines
- `persistence.py`: 5,760 lines
- `DB_Manager.py`: 1,424 lines
- `media_db/api.py`: 97 lines
- App code still contains 31 direct `MediaDatabase(...)` constructors.
- App code still contains 37 `create_media_database(...)` calls.
- App code currently uses `managed_media_database(...)` in 7 places.
- App and tests still contain 339 `Media_DB_v2` references.

## What Is Already True

- Schema/bootstrap, runtime factory logic, repository seams, and legacy helper modules have been extracted under `app/core/DB_Management/media_db/`.
- App code no longer depends on `DB_Manager.create_media_database(...)`; the caller-facing factory path is now `media_db.api.create_media_database(...)`.
- App code no longer binds extracted helper functions like `get_document_version(...)`, `get_latest_transcription(...)`, `upsert_transcript(...)`, `fetch_keywords_for_media(...)`, or maintenance helpers through `Media_DB_v2.py`.
- `managed_media_database(...)` already exists and is in production use for claims schedulers and web-scraping services.

## Remaining Work Categories

1. Raw DB lifecycle boilerplate still exists in app code.
2. Raw `MediaDatabase(...)` construction still exists in services, MCP modules, RAG code, cleanup jobs, and claims override paths.
3. `Media_DB_v2.py` is still the dominant compatibility import surface for `MediaDatabase`, errors, and some tests.
4. `persistence.py` remains a mini god file and is the largest unfinished Media DB-adjacent hotspot.
5. `DB_Manager.py` is thinner, but the runtime/api surface is not yet the obvious default for all remaining consumers.

## Non-Goals

- Do not start `ChaChaNotes_DB.py` extraction before the Media DB lifecycle and compatibility surface is explicitly reduced.
- Do not rewrite stable repository behavior merely to remove import references.
- Do not force all test code off `Media_DB_v2` if those tests are intentionally validating compatibility or raw DB behavior.
- Do not collapse long-lived DB owners onto a context manager if their lifetime genuinely spans a worker/module lifecycle.

## Stage 1: Lock The Remaining Surface Inventory
**Goal**: Freeze a precise inventory of what remains so later slices cannot silently skip a category.
**Success Criteria**:
- Every remaining app-side `MediaDatabase(...)` constructor is classified as one of:
  - migrate to `managed_media_database(...)`
  - migrate to `create_media_database(...)`
  - replace with a new dedicated helper
  - keep raw and document why
- Every remaining app-side `create_media_database(...)` call is classified as:
  - caller-managed lifecycle
  - should be upgraded to `managed_media_database(...)`
  - should be wrapped by a domain-specific helper
- Every existing app-side `managed_media_database(...)` call is classified as:
  - correctly modeled
  - needs a more specific helper
  - should remain raw because the context manager is the wrong lifetime model
- Every lifecycle call site records:
  - initialization policy (`initialize=True`, `initialize=False`, or custom)
  - close policy (automatic close, deferred close, shared owner)
  - backend assumptions (SQLite-path, shared Postgres backend, or both)
- `Media_DB_v2` references are split into:
  - compatibility imports that are still acceptable for now
  - compatibility imports that should move to `media_db/*`
  - tests that intentionally validate the shim
**Tests**:
- `rg -n "MediaDatabase\\(" tldw_Server_API/app`
- `rg -n "create_media_database\\(" tldw_Server_API/app`
- `rg -n "managed_media_database\\(" tldw_Server_API/app`
- `rg -n "Media_DB_v2" tldw_Server_API/app tldw_Server_API/tests`
**Status**: Not Started

Stage 1 artifact:

- `Docs/Plans/artifacts/2026-03-16-media-db-v2-stage1-inventory.md`

Primary buckets to classify:

- Worker and cleanup services:
  - `app/services/audiobook_jobs_worker.py`
  - `app/services/connectors_worker.py`
  - `app/services/ingestion_sources_worker.py`
  - `app/services/media_files_cleanup_service.py`
  - `app/services/storage_cleanup_service.py`
  - `app/services/tts_history_cleanup_service.py`
  - `app/services/outputs_purge_scheduler.py`
- MCP and long-lived module owners:
  - `app/core/MCP_unified/modules/implementations/media_module.py`
  - `app/core/MCP_unified/modules/implementations/quizzes_module.py`
  - `app/core/MCP_unified/modules/implementations/slides_module.py`
  - `app/core/Chatbooks/chatbook_service.py`
  - `app/core/Sync/Sync_Client.py`
- Claims and cross-user override paths:
  - `app/core/Claims_Extraction/claims_service.py`
  - `app/core/Claims_Extraction/claims_utils.py`
  - `app/core/Claims_Extraction/claims_notifications.py`
  - `app/core/Claims_Extraction/claims_rebuild_service.py`
- Retrieval and ingestion utilities:
  - `app/api/v1/API_Deps/DB_Deps.py`
  - `app/core/DB_Management/DB_Manager.py`
  - `app/core/RAG/rag_service/database_retrievers.py`
  - `app/core/RAG/rag_service/unified_pipeline.py`
  - `app/core/Embeddings/ChromaDB_Library.py`
  - `app/core/Ingestion_Media_Processing/persistence.py`
  - `app/core/Ingestion_Media_Processing/visual_ingestion.py`
  - `app/core/Chunking/template_initialization.py`
  - `app/core/TTS/tts_jobs_worker.py`

## Stage 2: Finish Lifecycle Helper Convergence
**Goal**: Make `media_db.api` the default lifecycle owner for short-lived Media DB sessions.
**Success Criteria**:
- Short-lived create/use/close blocks use `managed_media_database(...)` where possible.
- Raw `create_media_database(...)` is retained only where the caller intentionally owns the lifetime beyond a local scope.
- Repeated patterns that are more specific than `managed_media_database(...)` get a named helper instead of repeated boilerplate.
**Tests**:
- Extend import-surface and lifecycle tests under `tests/DB_Management/`
- Targeted suite reruns for each migrated caller
- Bandit on touched files
**Status**: Not Started

High-priority files for this stage:

- `app/core/Ingestion_Media_Processing/persistence.py`
- `app/services/document_processing_service.py`
- `app/core/Data_Tables/jobs_worker.py`
- `app/core/Embeddings/services/jobs_worker.py`
- `app/core/Embeddings/services/vector_compactor.py`
- `app/core/Watchlists/pipeline.py`
- `app/core/Claims_Extraction/claims_notifications.py`
- `app/core/Claims_Extraction/claims_rebuild_service.py`
- `app/core/Claims_Extraction/claims_service.py`
- `app/core/Web_Scraping/Article_Extractor_Lib.py`
- `app/core/Ingestion_Media_Processing/XML_Ingestion_Lib.py`
- `app/core/Ingestion_Media_Processing/MediaWiki/Media_Wiki.py`
- `app/core/Ingestion_Media_Processing/Books/Book_Processing_Lib.py`

Expected likely outcome:

- `managed_media_database(...)` expands for short-lived worker/service paths.
- A second helper is probably needed for "open another user's DB path temporarily" instead of duplicating raw per-user override logic.
- Stage 1 inventory should prevent mechanical `create_media_database(...)` -> `managed_media_database(...)` rewrites where init/close semantics differ.
- `persistence.py` should probably get a local session helper rather than eight inline factory blocks.

## Stage 3: Isolate The Intentional Raw Constructor Cases
**Goal**: Reduce raw `MediaDatabase(...)` construction to a small, documented set of intentional owners.
**Success Criteria**:
- Remaining direct constructors are either:
  - long-lived owners that should keep explicit lifecycle control, or
  - compatibility/test boundaries that are explicitly accepted
- Cross-user override logic no longer open-codes `MediaDatabase(...)` in multiple places if a helper can own the pattern safely.
- App code stops using raw constructors for simple short-lived tasks.
**Tests**:
- Existing module-specific suites
- New seam tests that fail if designated modules fall back to raw constructor usage
- `rg -n "MediaDatabase\\(" tldw_Server_API/app`
**Status**: Not Started

Likely intentional-owner candidates:

- `app/core/MCP_unified/modules/implementations/media_module.py`
- `app/core/Chatbooks/chatbook_service.py`
- `app/core/Sync/Sync_Client.py`

Likely migration candidates:

- `app/services/audiobook_jobs_worker.py`
- `app/services/media_files_cleanup_service.py`
- `app/services/storage_cleanup_service.py`
- `app/services/tts_history_cleanup_service.py`
- `app/services/outputs_purge_scheduler.py`
- `app/services/connectors_worker.py`
- `app/services/ingestion_sources_worker.py`
- `app/core/MCP_unified/modules/implementations/quizzes_module.py`
- `app/core/MCP_unified/modules/implementations/slides_module.py`
- `app/core/Workflows/adapters/media/ingest.py`
- `app/core/Embeddings/ChromaDB_Library.py`
- `app/core/RAG/rag_service/database_retrievers.py`
- `app/core/RAG/rag_service/unified_pipeline.py`
- `app/core/Ingestion_Media_Processing/visual_ingestion.py`
- `app/core/Chunking/template_initialization.py`
- `app/core/TTS/tts_jobs_worker.py`

Special-case bucket:

- `app/core/Claims_Extraction/claims_service.py`
  - Its raw constructors mostly exist for cross-user SQLite override behavior.
  - This should be centralized behind a dedicated helper instead of duplicated four times.

## Stage 4: Narrow The Compatibility Surface Deliberately
**Goal**: Decide what `Media_DB_v2.py` is still allowed to export and move the rest of app code to the `media_db` package.
**Success Criteria**:
- App code no longer treats `Media_DB_v2.py` as the default import source for new work.
- Compatibility imports in app code are reduced to an explicitly approved subset.
- Tests that validate compatibility remain, but ordinary tests prefer the extracted modules where practical.
**Tests**:
- Import-surface guards in `tests/DB_Management/`
- Targeted endpoint/service regressions
- `rg -n "Media_DB_v2" tldw_Server_API/app`
**Status**: Not Started

Key remaining app-side `Media_DB_v2` users to review:

- Central boundary modules:
  - `app/api/v1/API_Deps/DB_Deps.py`
  - `app/core/DB_Management/DB_Manager.py`
- Endpoints and services that import `MediaDatabase` or legacy errors:
  - `app/api/v1/endpoints/media/document_references.py`
  - `app/api/v1/endpoints/media/document_insights.py`
  - `app/api/v1/endpoints/media/document_outline.py`
  - `app/api/v1/endpoints/media/item.py`
  - `app/api/v1/endpoints/media/navigation.py`
  - `app/api/v1/endpoints/media/process_documents.py`
  - `app/api/v1/endpoints/media/process_pdfs.py`
  - `app/api/v1/endpoints/media/reading_progress.py`
  - `app/api/v1/endpoints/media/versions.py`
  - `app/core/Claims_Extraction/review_assignment.py`
  - `app/core/External_Sources/sync_coordinator.py`
  - `app/services/quiz_generator.py`
  - `app/services/quiz_source_resolver.py`

Important caution:

- The 339 `Media_DB_v2` references are not all migration debt.
- Many test files intentionally instantiate the compatibility class directly.
- The plan should drive app-code boundary cleanup first, then prune test imports where that yields real value.
- `DB_Deps.py` is part of the app boundary, not just an internal detail. If it keeps shim-only typing and errors indefinitely, Stage 4 will stall even if leaf callers look clean.
- `DB_Manager.py` needs an explicit allowlist for which Media DB compatibility exports remain acceptable after Stage 4.

## Stage 5: Prepare The Post-Media-DB Handoff
**Goal**: Finish the Media DB follow-on work with explicit exit gates before moving to the next DB god file.
**Success Criteria**:
- `persistence.py` has a documented decomposition plan and is no longer carrying anonymous DB lifecycle boilerplate.
- `DB_Manager.py` is a thin compatibility wrapper, not an alternate default API.
- Remaining app-side raw constructor and compatibility imports are documented and intentionally accepted.
- A readiness note exists for the next target: `ChaChaNotes_DB.py`.
**Tests**:
- Full bounded DB-management regression sweep
- Existing SQLite/Postgres parity suites for touched areas
- Bandit on touched scope
**Status**: Not Started

Exit gates before starting `ChaChaNotes_DB.py`:

- No app imports of `DB_Manager.create_media_database(...)`
- No new helper/function imports routed through `Media_DB_v2.py`
- All remaining app-side `MediaDatabase(...)` constructors have an explicit rationale
- `persistence.py` has either been split, or has a dedicated decomposition plan plus the first extraction slice and its regression tests already landed
- `media_db/api.py` is the documented default entry point for new Media DB callers

## Cross-Cutting Risks

- Over-normalizing lifecycle management:
  - Some modules legitimately need a long-lived DB handle.
  - Forcing those onto `managed_media_database(...)` will create premature close bugs.
- Breaking SQLite cross-user admin flows:
  - Claims and some review paths intentionally swap DB paths when not on Postgres.
  - Those semantics must remain explicit.
- Postgres parity drift:
  - Any helper that assumes filesystem-backed SQLite behavior will be wrong for Postgres content mode.
- Test false positives:
  - Import-count reduction is useful, but not if it deletes compatibility coverage we still need.
- `persistence.py` shadow-monolith risk:
  - If DB lifecycle cleanup happens without function decomposition, the god-file problem simply moves one layer down.

## Verification Gates For Every Slice

1. Run the narrowest relevant pytest suite for the touched boundary first.
2. Re-run the applicable DB-management regression tests.
3. Re-run any SQLite/Postgres parity tests touched by the slice.
4. Run Bandit on the touched files.
5. Update the remaining-inventory counts after any slice that reduces constructors, factory calls, or shim imports.

## Suggested Execution Order

1. Finish the inventory classification in Stage 1 and keep it current.
2. Collapse the repeated lifecycle boilerplate in `persistence.py`.
3. Centralize the claims cross-user override pattern.
4. Migrate the easy short-lived raw constructor cases in services and cleanup jobs.
5. Revisit long-lived owners and decide which stay explicit.
6. Narrow app-side `Media_DB_v2` imports once the lifecycle helpers are stable.
7. Only then start the `ChaChaNotes_DB.py` design/inventory pass.
