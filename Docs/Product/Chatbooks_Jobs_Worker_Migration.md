# Chatbooks Jobs Worker Migration (Phase 2)

Status: Complete
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Move chatbooks async export/import execution onto the core Jobs worker SDK. Jobs become the execution source of truth for chatbooks background processing instead of the in-process worker loop.

## 2. Current State
- Chatbooks enqueues core Jobs rows for async export/import (`domain=chatbooks`, `job_type=export|import`).
- The in-process `_core_worker_loop` exists in `ChatbookService` but is not started in production paths.
- Jobs adapters already map chatbooks status from core Jobs rows.

## 3. Goals
- Provide a standalone Jobs worker for chatbooks export/import.
- Keep API contracts unchanged; async endpoints continue to return job_id.
- Maintain per-user export/import tracking tables and download URL behavior.

## 4. Non-Goals
- Replacing chatbooks DB schema or export/import logic.
- Prompt Studio backend changes.

## 5. Jobs Execution

### 5.1 Job Types & Queues
- `domain`: `chatbooks`
- `queue`: `CHATBOOKS_JOBS_QUEUE` (default `default`)
- `job_type`: `export` or `import`

### 5.2 Payload Fields (export)
```json
{
  "action": "export",
  "chatbooks_job_id": "uuid",
  "name": "E2E Chatbook",
  "description": "...",
  "content_selections": {"note": ["123"]},
  "author": "user",
  "include_media": false,
  "media_quality": "compressed",
  "include_embeddings": false,
  "include_generated_content": true,
  "tags": [],
  "categories": []
}
```

### 5.3 Payload Fields (import)
```json
{
  "action": "import",
  "chatbooks_job_id": "uuid",
  "file_path": "/path/to/chatbook.zip",
  "content_selections": {},
  "conflict_resolution": "skip",
  "prefix_imported": false,
  "import_media": true,
  "import_embeddings": false
}
```

### 5.4 Worker Flow
- Acquire jobs via `WorkerSDK`.
- Instantiate `ChatbookService` for `owner_user_id`.
- Claim export/import job rows to avoid duplicates.
- Execute export/import using existing ChatbookService helpers.
- Update export/import tables and complete/fail Jobs rows.

## 6. Validation
- Run chatbooks roundtrip E2E in async mode with worker running.
- Ensure download URLs are generated on export completion.

## 7. Run Command
```bash
python -m tldw_Server_API.app.core.Chatbooks.services.jobs_worker
```

## 8. Resolved Questions
- ✅ `_core_worker_loop` removed from `ChatbookService` - standalone `jobs_worker.py` is now the only execution path.
