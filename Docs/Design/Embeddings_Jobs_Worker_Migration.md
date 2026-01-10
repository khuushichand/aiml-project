# Embeddings Jobs Worker Migration (Phase 2)

Status: Draft
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Move embeddings background execution onto the core Jobs worker SDK. Jobs become the execution source of truth for media embeddings instead of in-process background tasks or Redis queues.

## 2. Current State
- `/api/v1/media/{media_id}/embeddings` and `/api/v1/media/embeddings/batch` create a Jobs row but immediately run `generate_embeddings_for_media` via `asyncio.create_task` in-process.
- Redis-based embeddings pipeline (`EmbeddingJobManager` + `worker_orchestrator.py`) exists for scale-out chunking/embedding/storage, plus a collections enqueue helper (`core/Collections/embedding_queue.py`).
- Public job status endpoints already read from core Jobs via `EmbeddingsJobsAdapter` with legacy fallback.

## 3. Goals
- Execute media embeddings jobs via core Jobs workers.
- Keep API behavior unchanged (accepted response + job_id) while shifting execution off the API server.
- Avoid embedding large chunk/embedding payloads in Jobs rows.

## 4. Non-Goals
- Removing Redis pipeline in this phase (Phase 3 handles deletions).
- Full DAG dependency edges (Phase 4 in PRD).

## 5. Proposed Jobs Execution

### 5.1 Job Types & Queues
- `domain`: `embeddings`
- `queue`: `EMBEDDINGS_JOBS_QUEUE` (default `default`)
- `job_type`: `media_embeddings` (existing adapter type)

### 5.2 Payload Shape (media jobs)
```json
{
  "media_id": 123,
  "embedding_model": "text-embedding-3-small",
  "embedding_provider": "openai",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "request_source": "media"
}
```
Notes:
- No raw chunk/embedding arrays in payload.
- If a non-media source is added later (collections), payload should store only references and keep content below `JOBS_MAX_JSON_BYTES`.

### 5.3 Worker Flow
Add a Jobs worker service `tldw_Server_API/app/core/Embeddings/services/jobs_worker.py`:
1. Acquire jobs via `WorkerSDK` (domain `embeddings`, queue `EMBEDDINGS_JOBS_QUEUE`).
2. Validate `job_type == media_embeddings`; otherwise fail with `error_code="unsupported_job_type"`.
3. Load media content via `get_media_content` (move to a shared helper or import from `media_embeddings.py`).
4. Call `generate_embeddings_for_media(...)` with payload fields.
5. Update job result fields on success:
   - `embedding_count`
   - `chunks_processed`
   - `embedding_model`
   - `embedding_provider`
   - optional `total_chunks` if available
6. Update `progress_percent` (0 -> 25 -> 75 -> 100) as stages complete.
7. On error, fail job (retryable if provider transient error).

### 5.4 API Behavior
- When `EMBEDDINGS_JOBS_BACKEND=jobs`, API endpoints only enqueue Jobs and return 202/accepted.
- When `EMBEDDINGS_JOBS_BACKEND=redis` (default), keep in-process background tasks.

### 5.5 Backpressure / Quotas
- Use Jobs quotas (see PRD defaults). Backpressure should return 429 when Jobs quota limits are reached.
- Redis queue stats remain available for legacy mode; Jobs mode can expose empty/disabled stats (Phase 3 cleanup).

## 6. Migration Steps
1. Add Jobs worker service for `media_embeddings` and document run command.
2. Gate endpoints with `EMBEDDINGS_JOBS_BACKEND=jobs` to enqueue only.
3. Optional: migrate `core/Collections/embedding_queue.py` to Jobs (content stays out of payload when possible).
4. Update runbooks/tests to start Jobs worker during E2E runs.

## 7. Testing
- Unit: new tests for Jobs worker handler (success + failure).
- E2E: `tldw_Server_API/tests/e2e/test_embeddings_e2e.py` and media embeddings flows with `EMBEDDINGS_JOBS_BACKEND=jobs`.
- Regression: ensure legacy mode remains unchanged.

## 8. Open Questions
- Should collections embedding enqueue be migrated in this phase or deferred to Phase 3?
- Should progress updates be exposed by default or remain behind `EMBEDDINGS_JOBS_EXPOSE_PROGRESS`?
