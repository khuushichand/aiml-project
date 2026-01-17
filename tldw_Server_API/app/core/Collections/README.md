# Collections

## 1. Descriptive of Current Feature Set

- Purpose: Unified content collections (reading list, outputs, tags) with search, filtering, and artifact generation.
- Capabilities:
  - Reading list: save URLs, list/filter, update status/favorite/tags
  - Outputs: template CRUD, preview, artifact creation (md/html/mp3 via TTS), retention and purge
  - Items: unified listing across Collections with legacy Media DB fallback (deprecated; retained for compatibility)
  - Automatic embeddings enqueue on new/changed reading items
- Inputs/Outputs:
  - Inputs: URLs, metadata, item/job/run filters; template bodies and context
  - Outputs: Content items, output templates, output artifacts on disk
- Related Endpoints:
  - Reading: `tldw_Server_API/app/api/v1/endpoints/reading.py:1`
  - Items: `tldw_Server_API/app/api/v1/endpoints/items.py:1`
  - Output Templates: `tldw_Server_API/app/api/v1/endpoints/outputs_templates.py:1`
  - Outputs: `tldw_Server_API/app/api/v1/endpoints/outputs.py:1`
- Related Schemas:
  - Reading: `tldw_Server_API/app/api/v1/schemas/reading_schemas.py:1`
  - Items: `tldw_Server_API/app/api/v1/schemas/items_schemas.py:1`
  - Outputs/Templates: `tldw_Server_API/app/api/v1/schemas/outputs_schemas.py:1`, `tldw_Server_API/app/api/v1/schemas/outputs_templates_schemas.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - Service: `core/Collections/reading_service.py` handles fetch, dedupe, persist, and embeddings enqueue
  - API uses Collections DB via DI; legacy fallback to Media DB search to maintain compatibility (deprecated)
- Key Classes/Functions:
  - `ReadingService.save_url`, `.list_items`, `.update_item`
  - `embedding_queue.enqueue_embeddings_job_for_item` (core Jobs-backed enqueue)
  - Templating: `Chat/prompt_template_manager.safe_render` for outputs
- Dependencies:
  - Internal: `DB_Management/Collections_DB`, core Jobs, `Web_Scraping.Article_Extractor_Lib`
  - External (optional): Redis for embeddings queue; provider TTS for mp3 outputs
- Data Models & DB:
  - `Collections_DB.py`: tables `output_templates`, `outputs`, `reading_highlights`, `content_items` (+ indices/uniques)
- Configuration:
  - Redis URL for embeddings queue: `EMBEDDINGS_REDIS_URL` or `REDIS_URL`
- Concurrency & Performance:
  - Background embeddings job per new/updated item
  - Paging on list endpoints; FTS optional depending on backend
- Error Handling:
  - Safe fallbacks when outputs re-encode fails; DB backfills in schema initializer
- Security:
  - AuthNZ enforced at endpoints; per-user DB paths; soft-delete for outputs

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `Collections/reading_service.py`, `embedding_queue.py`, `utils.py`; DB adapter in `DB_Management/Collections_DB.py`
- Extension Points:
  - Add new origins 
  - to `content_items`; extend outputs formats; add highlight strategies
- Coding Patterns:
  - DI for DB, loguru for logging; avoid raw SQL in endpoints (use DB adapter)
- Tests:
  - `tldw_Server_API/tests/Collections/test_reading_service.py:1`
  - `tldw_Server_API/tests/Collections/test_items_and_outputs_api.py:1`
- Local Dev Tips:
  - Save reading items with inline content override for offline tests; render outputs to inspect saved files
- Pitfalls & Gotchas:
  - Large selections for outputs; ensure retention and purge behavior matches expectations
- Roadmap/TODOs:
  - Highlights CRUD endpoints; richer tags and collection views
