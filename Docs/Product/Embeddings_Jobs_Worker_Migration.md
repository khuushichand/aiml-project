# Embeddings Jobs Worker Migration (Phase 2)

Status: Complete (Phase 2 shipped; Phase 3 legacy removed)
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Keep embeddings status/billing in core Jobs while reintroducing a minimal Redis Streams transport for media embeddings stages. Jobs remain the root status source of truth; Redis handles chunking → embedding → storage throughput.

## 2. Current State
- Media embeddings stages run via Redis Streams workers (`core/Embeddings/services/redis_worker.py`).
- Content embeddings for collections items run via the Redis Streams `embeddings:content` stage.
- Legacy EmbeddingJobManager/queue schemas remain removed.
- Public job status endpoints read from core Jobs via `EmbeddingsJobsAdapter` (root jobs only).

## 3. Goals
- Execute media embeddings stages via Redis Streams for throughput.
- Keep API behavior unchanged (accepted response + job_id) while shifting execution off the API server.
- Keep Jobs as the status/billing source of truth for root jobs.

## 4. Non-Goals
- Full DAG dependency edges (Phase 4 in PRD).

## 5. Proposed Jobs Execution

### 5.1 Job Types & Queues
- `domain`: `embeddings`
- `root queue`: `EMBEDDINGS_ROOT_JOBS_QUEUE` (default `low`) for Jobs status/billing
- `stage streams`: Redis Streams `embeddings:chunking`, `embeddings:embedding`, `embeddings:storage`, `embeddings:content`

### 5.2 Payload Shape (media stage messages)
```json
{
  "media_id": 123,
  "user_id": "user-1",
  "embedding_model": "text-embedding-3-small",
  "embedding_provider": "openai",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "request_source": "media",
  "current_stage": "chunking",
  "root_job_uuid": "uuid",
  "config_version": "model:provider:1000:200"
}
```
Notes:
- No raw chunk/embedding arrays in payload.
- Content embeddings payloads include inline text (`content`) and optional metadata; keep payloads below `JOBS_MAX_JSON_BYTES`.

### 5.2.1 Payload Shape (content stage messages)
```json
{
  "item_id": 456,
  "content": "Inline text to embed",
  "metadata": { "source": "collections" },
  "current_stage": "content",
  "root_job_uuid": "uuid"
}
```

### 5.3 Worker Flow
Add a Redis Streams worker service `tldw_Server_API/app/core/Embeddings/services/redis_worker.py`:
1. Consume stage messages from Redis Streams (chunking/embedding/storage).
   - Run with: `python -m tldw_Server_API.app.core.Embeddings.services.redis_worker --stage all`
2. Chunking stage: load media content, create chunks, persist artifact, enqueue `embeddings:embedding`.
3. Embedding stage: read chunks, create embeddings (fallback model on provider error), persist artifact, enqueue `embeddings:storage`.
4. Storage stage: read artifacts, store vectors in ChromaDB, update root Jobs result.
5. Content stage: embed inline content payloads directly and update the root Jobs result.
6. Stage chaining is idempotent via artifact reuse and Redis idempotency keys.
7. On error, retry locally (bounded) then fail the root Jobs record.

### 5.4 API Behavior
- Embeddings APIs enqueue a Jobs root record and a Redis Streams chunking message, then return 202/accepted.
- `EMBEDDINGS_JOBS_BACKEND` legacy values are ignored (Jobs root remains the backend).

### 5.5 Backpressure / Quotas
- Jobs quotas remain enforced for root jobs (see PRD defaults).
- Redis Streams stage queues handle throughput; stage queue stats are Redis-native.

## 6. Migration Steps
1. Add Redis Streams worker service for staged pipelines and document run command.
2. Ensure endpoints enqueue Jobs root + Redis chunking message.
3. Migrate `core/Collections/embedding_queue.py` to Redis Streams for content embeddings.
4. Update runbooks/tests to start Redis worker during E2E runs.

## 7. Testing
- Unit: new tests for Jobs worker handler (success + failure).
- E2E: `tldw_Server_API/tests/e2e/test_embeddings_e2e.py` and media embeddings flows with `EMBEDDINGS_JOBS_BACKEND=jobs`.

## 8. Open Questions
- Should progress updates be exposed by default or remain behind `EMBEDDINGS_JOBS_EXPOSE_PROGRESS`?
