# Media DB v2 Stage 1 Remaining Surface Inventory

**Scope**: App-side Media DB lifecycle and compatibility surface in the `codex/media-db-v2-phase1-refactor` worktree after the phase-1 extraction work already landed.

## Normalized Counts

- Raw `MediaDatabase(...)` constructors in app code: 13
- Operational `create_media_database(...)` call sites in app code: 24
- Operational `managed_media_database(...)` call sites in app code: 29
- `Media_DB_v2` references in app code: 137

Notes:

- The operational counts exclude helper definitions in `media_db/api.py`, `media_db/runtime/factory.py`, `DB_Manager.py`, and README examples.
- The `Media_DB_v2` reference count is not all migration debt. A significant fraction is still compatibility-oriented app boundary code.

## Classification Rubric

- `MOVE_MANAGED`: short-lived local scope that should prefer `managed_media_database(...)`
- `MOVE_FACTORY`: should stop using raw `MediaDatabase(...)`, but still needs explicit owner-controlled lifetime
- `NEW_HELPER`: repeated or specialized pattern that should be centralized behind a domain helper
- `KEEP_RAW`: intentional long-lived owner or cached handle; explicit lifecycle is acceptable
- `BOUNDARY`: compatibility surface that should be reduced deliberately rather than by leaf rewrites

## Managed Helper Call Sites Already In The Right Shape

| File | Call Sites | Assessment | Notes |
| --- | ---: | --- | --- |
| `app/services/claims_alerts_scheduler.py` | 2 | `MOVE_MANAGED` already satisfied | Correct backend-aware scheduler pattern with suppressed init/close failures |
| `app/services/claims_review_metrics_scheduler.py` | 2 | `MOVE_MANAGED` already satisfied | Same pattern as alerts scheduler |
| `app/api/v1/endpoints/research.py` | 1 | `MOVE_MANAGED` already satisfied | Deprecated arXiv ingest helper now scopes its DB write through the managed helper with `initialize=False` |
| `app/services/document_processing_service.py` | 1 | `MOVE_MANAGED` already satisfied | Local document persistence now scopes its DB write through the managed helper with `initialize=False` |
| `app/core/Web_Scraping/Article_Extractor_Lib.py` | 1 | `MOVE_MANAGED` already satisfied | Local article ingest helper now scopes its DB write through the managed helper with `initialize=False` |
| `app/core/Ingestion_Media_Processing/XML_Ingestion_Lib.py` | 1 | `MOVE_MANAGED` already satisfied | Local XML import now scopes its DB write through the managed helper with `initialize=False` |
| `app/core/Ingestion_Media_Processing/Books/Book_Processing_Lib.py` | 1 | `MOVE_MANAGED` already satisfied | Local text-file ingest now scopes its DB write through the managed helper with `initialize=False` |
| `app/core/Ingestion_Media_Processing/MediaWiki/Media_Wiki.py` | 1 | `MOVE_MANAGED` already satisfied | Local MediaWiki import now scopes its DB write through the managed helper with `initialize=False` |
| `app/services/web_scraping_service.py` | 1 | `MOVE_MANAGED` already satisfied | Correct `initialize=False` local scope |
| `app/services/enhanced_web_scraping_service.py` | 1 | `MOVE_MANAGED` already satisfied | Correct `initialize=False` local scope |
| `app/services/media_files_cleanup_service.py` | 1 | `MOVE_MANAGED` already satisfied | Local MediaFiles lookup now scoped through managed helper with `initialize=False` |
| `app/services/storage_cleanup_service.py` | 1 | `MOVE_MANAGED` already satisfied | Local TTS history update now scoped through managed helper with `initialize=False` |
| `app/services/outputs_purge_scheduler.py` | 1 | `MOVE_MANAGED` already satisfied | Output-history purge path now scoped through managed helper with `initialize=False` |
| `app/services/audiobook_jobs_worker.py` | 1 | `MOVE_MANAGED` already satisfied | Media-id source reads now use the managed helper with `initialize=False` |
| `app/core/MCP_unified/modules/implementations/slides_module.py` | 1 | `MOVE_MANAGED` already satisfied | Local media lookup for slide generation now uses the managed helper with `initialize=False` |
| `app/core/MCP_unified/modules/implementations/quizzes_module.py` | 1 | `MOVE_MANAGED` already satisfied | Local media lookup for quiz generation now uses the managed helper with `initialize=False` |
| `app/core/Workflows/adapters/media/ingest.py` | 1 | `MOVE_MANAGED` already satisfied | Local workflow indexing now scopes its DB write through the managed helper with `initialize=False` |
| `app/core/Ingestion_Media_Processing/visual_ingestion.py` | 1 | `MOVE_MANAGED` already satisfied | Visual document persistence now scopes its DB writes through the managed helper with `initialize=False` |
| `app/core/Claims_Extraction/claims_utils.py` | 1 | `MOVE_MANAGED` already satisfied | Claims persistence worker now scopes its DB writes through the managed helper with `initialize=False` and close-error suppression |
| `app/core/Embeddings/ChromaDB_Library.py` | 1 | `MOVE_MANAGED` already satisfied | Ingestion-claims SQL fallback now uses the managed helper with `initialize=False` and suppressed close failures |
| `app/core/Embeddings/services/jobs_worker.py` | 1 | `MOVE_MANAGED` already satisfied | Local media-content reads now scope their DB session through the managed helper with `initialize=False` |
| `app/core/Embeddings/services/vector_compactor.py` | 1 | `MOVE_MANAGED` already satisfied | Soft-delete lookup now scopes its Media DB read through the managed helper with `initialize=False` and suppressed close failures |

## Operational `create_media_database(...)` Inventory

| File | Count | Current Pattern | Classification | Notes |
| --- | ---: | --- | --- | --- |
| `app/core/Ingestion_Media_Processing/persistence.py` | 8 | repeated local worker/pre-check DB creation | `NEW_HELPER` | highest-priority lifecycle cleanup hotspot |
| `app/services/media_ingest_jobs_worker.py` | 1 | helper returns DB handle | `KEEP_RAW` | owner is the caller, not the helper |
| `app/services/connectors_worker.py` | 1 | connector-owned per-sync DB helper through shared factory | `MOVE_FACTORY` already satisfied | `_process_import_job(...)` now opens via `_create_connector_media_db(...)` and closes on every exit path |
| `app/services/ingestion_sources_worker.py` | 1 | helper returns DB handle through shared factory | `MOVE_FACTORY` already satisfied | caller still owns sink DB lifetime |
| `app/services/tts_history_cleanup_service.py` | 1 | local cleanup DB helper wraps probe and per-user loops | `NEW_HELPER` already satisfied | preserves explicit close behavior while removing raw constructors |
| `app/core/Workflows/adapters/knowledge/crud.py` | 2 | per-user lazy import path | `NEW_HELPER` | currently calls `create_media_database(user_id=...)`; signature mismatch hazard |
| `app/core/Watchlists/pipeline.py` | 1 | per-job DB used through ingest flow | `MOVE_MANAGED` | likely function-scope context-manager conversion |
| `app/core/Data_Tables/jobs_worker.py` | 1 | cached per-user DB owner | `KEEP_RAW` | explicit cache owner is intentional |
| `app/core/Claims_Extraction/claims_notifications.py` | 1 | local delivery helper init/close | `MOVE_MANAGED` | could also be folded into a notification DB helper |
| `app/core/Claims_Extraction/claims_rebuild_service.py` | 2 | local health/task DB open-close | `NEW_HELPER` | repeated pattern with health-init semantics |
| `app/core/Claims_Extraction/claims_service.py` | 2 | local event/health persistence DB | `NEW_HELPER` | likely same helper family as rebuild/notifications |
| `app/core/Evaluations/embeddings_abtest_jobs_worker.py` | 1 | helper returns DB handle | `KEEP_RAW` | explicit owner-controlled lifetime is fine |
| `app/core/DB_Management/Users_DB.py` | 1 | factory wrapper returns DB instance | `KEEP_RAW` | wrapper boundary, not local scope |
| `app/core/TTS/tts_jobs_worker.py` | 1 | helper returns DB handle through shared factory | `MOVE_FACTORY` already satisfied | `_handle_tts_job(...)` still owns close behavior |
| `app/core/Chunking/template_initialization.py` | 1 | internal helper opens via shared factory and closes owned DBs | `MOVE_FACTORY` already satisfied | preserves caller-provided DB ownership while closing internal startup DBs |

## Raw `MediaDatabase(...)` Constructor Inventory

| File | Count | Current Pattern | Classification | Notes |
| --- | ---: | --- | --- | --- |
| `app/core/MCP_unified/modules/implementations/media_module.py` | 3 | module-level cached owner | `KEEP_RAW` | explicit long-lived owner and cache management are intentional |
| `app/core/Chatbooks/chatbook_service.py` | 1 | lazy cached owner | `KEEP_RAW` | explicit cache owner is intentional |
| `app/core/Claims_Extraction/claims_service.py` | 4 | cross-user SQLite override DBs | `NEW_HELPER` | needs one dedicated override helper, not four duplicated constructors |
| `app/core/Sync/Sync_Client.py` | 1 | long-lived client sync owner | `KEEP_RAW` | explicit owner lifecycle is part of the design |
| `app/core/RAG/rag_service/unified_pipeline.py` | 1 | local fallback lookup | `MOVE_MANAGED` | local read scope |
| `app/core/RAG/rag_service/database_retrievers.py` | 2 | retriever-owned DB instances | `KEEP_RAW` | lifetime is owned by retriever instances with explicit `close()` |

## App-Side `Media_DB_v2` Compatibility Buckets

### 1. Central boundaries

- `app/api/v1/API_Deps/DB_Deps.py`
- `app/core/DB_Management/DB_Manager.py`

Assessment:

- `DB_Deps.py` is still a real app boundary, not a leaf detail. It imports `MediaDatabase`, `DatabaseError`, and `SchemaError` from the shim while also depending on `MediaDbFactory` and `MediaDbSession`.
- `DB_Manager.py` is already thinner, but it still imports `MediaDatabase` and selected compatibility exports from `Media_DB_v2.py`.

Recommendation:

- Treat both modules as explicit Stage 4 targets.
- Do not assume app-side compatibility reduction is complete until these two files have an approved allowlist.

### 2. Intentional compatibility owners

Representative files:

- `app/core/MCP_unified/modules/implementations/media_module.py`
- `app/core/Chatbooks/chatbook_service.py`
- `app/core/Sync/Sync_Client.py`
- `app/core/RAG/rag_service/database_retrievers.py`

Assessment:

- These modules own DB lifecycle explicitly or cache DB handles over time.
- They are not the first place to chase import-count reduction.

### 3. Leaf compatibility consumers

Representative files:

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

Assessment:

- These should be reduced after lifecycle helper policy is stable.
- Moving them too early risks re-binding against temporary interfaces.

## Acute Issues Found During Inventory

### 1. Workflow knowledge adapter factory signature mismatch

File:

- `app/core/Workflows/adapters/knowledge/crud.py`

Status:

- Resolved in the worktree by introducing a workflow-specific helper that calls `create_media_database(client_id=..., db_path=...)` with the real API contract.
- Keep the workflow helper in place until the broader workflow DB surface is revisited.

### 2. Local-scope DB creation without obvious close in the same helper

Representative files:

- `app/api/v1/endpoints/research.py`
- `app/core/Web_Scraping/Article_Extractor_Lib.py`
- `app/core/Ingestion_Media_Processing/XML_Ingestion_Lib.py`
- `app/core/Ingestion_Media_Processing/Books/Book_Processing_Lib.py`
- `app/services/audiobook_jobs_worker.py`
- `app/core/RAG/rag_service/unified_pipeline.py`
- `app/core/Workflows/adapters/media/ingest.py`

Recommendation:

- Audit these before broad compatibility cleanup.
- They are the most likely source of accidental lifecycle drift or silent connection leaks.

## Recommended Next Execution Order

1. Centralize the claims cross-user SQLite override pattern into one helper.
2. Convert the remaining simple local raw constructor sites to `managed_media_database(...)` or `create_media_database(...)` based on ownership.
3. Revisit long-lived owners and explicitly mark which raw constructors remain acceptable.
4. Narrow the `Media_DB_v2` boundary imports once lifecycle helper policy is stable.
