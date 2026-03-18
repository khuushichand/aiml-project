# Media DB v2 Stage 1 Remaining Surface Inventory

**Scope**: App-side Media DB lifecycle and compatibility surface in the `codex/media-db-v2-phase1-refactor` worktree after the phase-1 extraction work already landed.

## Normalized Counts

- Raw `MediaDatabase(...)` constructors in app code: 5
- Operational `create_media_database(...)` call sites in app code: 12
- Operational `managed_media_database(...)` call sites in app code: 35
- `Media_DB_v2` references in app code: 74

Notes:

- The operational counts exclude helper definitions in `media_db/api.py`, `media_db/runtime/factory.py`, `DB_Manager.py`, and README examples.
- The normalized counts also exclude test modules located under `app/**/tests`.
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
| `app/core/Chunking/template_initialization.py` | 1 | `MOVE_MANAGED` already satisfied | Built-in template initialization now centralizes owned DB lifecycle through the managed helper while preserving caller-provided DB ownership |
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
| `app/core/Claims_Extraction/claims_notifications.py` | 1 | `MOVE_MANAGED` already satisfied | Review notification delivery now scopes its DB session through the managed helper with suppressed init/close failures |
| `app/core/Claims_Extraction/claims_rebuild_service.py` | 2 | `MOVE_MANAGED` already satisfied | Health persistence and task processing now scope their DB sessions through the managed helper while preserving first-run health DB initialization semantics |
| `app/core/Claims_Extraction/claims_service.py` | 3 | `MOVE_MANAGED` already satisfied | Webhook event persistence, persisted rebuild-health reads, and the cross-user SQLite override helper now scope their DB sessions through the managed helper with suppressed close failures |
| `app/main.py` | 1 | `MOVE_MANAGED` already satisfied | Claims rebuild startup scanning now scopes its Media DB session through a local managed-helper wrapper with `initialize=False` and startup close-error suppression |
| `app/core/Embeddings/ChromaDB_Library.py` | 1 | `MOVE_MANAGED` already satisfied | Ingestion-claims SQL fallback now uses the managed helper with `initialize=False` and suppressed close failures |
| `app/core/Embeddings/services/jobs_worker.py` | 1 | `MOVE_MANAGED` already satisfied | Local media-content reads now scope their DB session through the managed helper with `initialize=False` |
| `app/core/Embeddings/services/vector_compactor.py` | 1 | `MOVE_MANAGED` already satisfied | Soft-delete lookup now scopes its Media DB read through the managed helper with `initialize=False` and suppressed close failures |
| `app/core/Workflows/adapters/knowledge/crud.py` | 1 | `MOVE_MANAGED` already satisfied | Workflow claims search/list reads now scope their per-user Media DB through a local managed-helper wrapper with `initialize=False` |
| `app/core/RAG/rag_service/unified_pipeline.py` | 1 | `MOVE_MANAGED` already satisfied | Pre-extracted claims verification now scopes its local Media DB read through the managed helper with `initialize=False` and suppressed close failures |
| `app/core/Watchlists/pipeline.py` | 1 | `MOVE_MANAGED` already satisfied | The optional per-run media DB now scopes through the managed helper with `initialize=False` and suppressed close failures |

## Operational `create_media_database(...)` Inventory

| File | Count | Current Pattern | Classification | Notes |
| --- | ---: | --- | --- | --- |
| `app/core/Ingestion_Media_Processing/persistence.py` | 1 | centralized worker-session helper | `NEW_HELPER` already satisfied | `_with_media_db_session(...)` is now the single factory-owned entry point |
| `app/services/media_ingest_jobs_worker.py` | 1 | helper returns DB handle | `KEEP_RAW` | owner is the caller, not the helper |
| `app/services/connectors_worker.py` | 1 | connector-owned per-sync DB helper through shared factory | `MOVE_FACTORY` already satisfied | `_process_import_job(...)` now opens via `_create_connector_media_db(...)` and closes on every exit path |
| `app/services/ingestion_sources_worker.py` | 1 | helper returns DB handle through shared factory | `MOVE_FACTORY` already satisfied | caller still owns sink DB lifetime |
| `app/services/tts_history_cleanup_service.py` | 1 | local cleanup DB helper wraps probe and per-user loops | `NEW_HELPER` already satisfied | preserves explicit close behavior while removing raw constructors |
| `app/core/Data_Tables/jobs_worker.py` | 1 | cached per-user DB owner | `KEEP_RAW` | explicit cache owner is intentional |
| `app/core/Evaluations/embeddings_abtest_jobs_worker.py` | 1 | helper returns DB handle | `KEEP_RAW` | explicit owner-controlled lifetime is fine |
| `app/core/DB_Management/Users_DB.py` | 1 | factory wrapper returns DB instance | `KEEP_RAW` | wrapper boundary, not local scope |
| `app/core/RAG/rag_service/agentic_chunker.py` | 1 | cached singleton structure-index DB owner through shared factory | `MOVE_FACTORY` already satisfied | `_get_media_db_for_structure()` now preserves singleton ownership while routing construction through the shared factory |
| `app/core/RAG/rag_service/database_retrievers.py` | 2 | retriever-owned adapter attachment through shared factory | `MOVE_FACTORY` already satisfied | media and claims retrievers now preserve explicit owner-controlled close behavior while routing attachment through the shared factory |
| `app/core/TTS/tts_jobs_worker.py` | 1 | helper returns DB handle through shared factory | `MOVE_FACTORY` already satisfied | `_handle_tts_job(...)` still owns close behavior |

## Raw `MediaDatabase(...)` Constructor Inventory

| File | Count | Current Pattern | Classification | Notes |
| --- | ---: | --- | --- | --- |
| `app/core/MCP_unified/modules/implementations/media_module.py` | 3 | module-level cached owner | `KEEP_RAW` | explicit long-lived owner and cache management are intentional |
| `app/core/Chatbooks/chatbook_service.py` | 1 | lazy cached owner | `KEEP_RAW` | explicit cache owner is intentional |
| `app/core/Sync/Sync_Client.py` | 1 | long-lived client sync owner | `KEEP_RAW` | explicit owner lifecycle is part of the design |

## App-Side `Media_DB_v2` Compatibility Buckets

### 1. Central boundaries

- `app/api/v1/API_Deps/DB_Deps.py`
- `app/core/DB_Management/DB_Manager.py`

Assessment:

- `DB_Deps.py` is still a real app boundary, not a leaf detail. It now depends on `media_db.errors`, `MediaDbFactory`, and `MediaDbSession` instead of importing runtime error types or `MediaDatabase` from the shim directly, but it still owns request/session scoping and cache compatibility.
- `DB_Manager.py` is already thinner and no longer binds `MediaDatabase` from the shim directly, but it still imports selected compatibility exports from `Media_DB_v2.py` and remains part of the boundary allowlist discussion.

Recommendation:

- Treat `DB_Manager.py` as the remaining direct-shim Stage 4 target, and keep `DB_Deps.py` in the boundary bucket until the request-scope/session surface is explicitly finalized.
- Do not assume app-side compatibility reduction is complete until these two files have an approved allowlist.

### 2. Intentional compatibility owners

Representative files:

- `app/core/MCP_unified/modules/implementations/media_module.py`
- `app/core/Chatbooks/chatbook_service.py`
- `app/core/Sync/Sync_Client.py`

Assessment:

- These modules own DB lifecycle explicitly or cache DB handles over time.
- They are not the first place to chase import-count reduction.

### 3. Leaf compatibility consumers

Status:

- Completed for the previously identified representative leaves.
- `app/services/admin_bundle_service.py` now resolves the media schema version through `media_db.runtime.factory.get_current_media_schema_version()` instead of importing `MediaDatabase` from the shim directly.
- `app/services/claims_review_metrics_scheduler.py` no longer binds `MediaDatabase` from the shim just for the optional `db` parameter annotation.
- `app/core/Claims_Extraction/claims_notifications.py` no longer binds `MediaDatabase` from the shim just for notification-helper annotations.
- `app/core/Claims_Extraction/ingestion_claims.py` no longer binds `MediaDatabase` from the shim just for claim-storage typing.
- `app/core/RAG/rag_service/agentic_chunker.py` now creates its cached structure-index DB through `media_db.api.create_media_database(...)` instead of the shim constructor.
- `app/core/RAG/rag_service/database_retrievers.py` now attaches media DB adapters through `media_db.api.create_media_database(...)` and `media_db.errors.DatabaseError` instead of importing those bindings from the shim.
- `app/core/Utils/metadata_utils.py` now imports `DatabaseError` from `media_db.errors` inside its safe-metadata write helper instead of from the shim.
- Remaining `Media_DB_v2` reduction work is now concentrated in boundary/owner modules rather than low-blast leaf consumers.

## Acute Issues Found During Inventory

### 1. Workflow knowledge adapter factory signature mismatch

File:

- `app/core/Workflows/adapters/knowledge/crud.py`

Status:

- Resolved in the worktree by introducing a workflow-specific helper that scopes short-lived claims reads through `managed_media_database(client_id=..., db_path=..., initialize=False)`.
- Keep the workflow helper in place until the broader workflow DB surface is revisited.

### 2. Local-scope DB creation without obvious close in the same helper

Representative files:

- `app/api/v1/endpoints/research.py`
- `app/core/Web_Scraping/Article_Extractor_Lib.py`
- `app/core/Ingestion_Media_Processing/XML_Ingestion_Lib.py`
- `app/core/Ingestion_Media_Processing/Books/Book_Processing_Lib.py`
- `app/services/audiobook_jobs_worker.py`
- `app/core/Workflows/adapters/media/ingest.py`

Recommendation:

- Audit these before broad compatibility cleanup.
- They are the most likely source of accidental lifecycle drift or silent connection leaks.

## Recommended Next Execution Order

1. Revisit long-lived owners and explicitly mark which raw constructors remain acceptable.
2. Review the remaining owner-controlled factory helpers and convert only true local-scope leftovers.
3. Narrow the `Media_DB_v2` boundary imports once lifecycle helper policy is stable.
