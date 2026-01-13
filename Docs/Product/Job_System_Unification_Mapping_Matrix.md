# Job System Unification Mapping Matrix

Status: Draft
Owner: Core Maintainers
Source PRD: Docs/Product/Job_System_Unification_PRD.md

## Canonical Jobs Statuses
`queued`, `processing`, `completed`, `failed`, `cancelled`, `quarantined`

---

## Embeddings (public endpoints)
Domain: `embeddings`
Queue: `EMBEDDINGS_JOBS_QUEUE` (default: `default`)
Job type: `embeddings_pipeline` (root), stage job types: `embeddings_chunking`, `embeddings_embedding`, `embeddings_storage`

| Endpoint | Public Field/Status | Jobs Source | Adapter Rule | Notes |
| --- | --- | --- | --- | --- |
| `/api/v1/media/embeddings/jobs` (list) | `status` | `jobs.status` | `queued -> queued`, `quarantined -> failed`, others pass-through | Matches PRD mapping for queued. |
| `/api/v1/media/embeddings/jobs` (list) | `id` | `jobs.uuid` or `jobs.id` | `uuid` preferred | Legacy `job_id` is now Jobs UUID. |
| `/api/v1/media/embeddings/jobs` (list) | `embedding_model` | `jobs.payload.embedding_model` | pass-through |  |
| `/api/v1/media/embeddings/jobs` (list) | `embedding_count` | `jobs.result.embedding_count` | pass-through |  |
| `/api/v1/media/embeddings/jobs` (list) | `chunks_processed` | `jobs.result.chunks_processed` | pass-through |  |
| `/api/v1/media/embeddings/jobs` (list) | `error` | `jobs.error_message` or `jobs.last_error` | pass-through |  |
| `/api/v1/media/embeddings/jobs` (list) | `created_at` | `jobs.created_at` | epoch seconds |  |
| `/api/v1/media/embeddings/jobs` (list) | `updated_at` | `jobs.updated_at` | epoch seconds |  |
| `/api/v1/media/embeddings/jobs` (list) | `progress_percent` | `jobs.progress_percent` | pass-through if `EMBEDDINGS_JOBS_EXPOSE_PROGRESS=true` | Feature-flagged. |
| `/api/v1/media/embeddings/jobs` (list) | `total_chunks` | `jobs.result.total_chunks` | pass-through if `EMBEDDINGS_JOBS_EXPOSE_PROGRESS=true` | Feature-flagged. |
| `/api/v1/media/embeddings/jobs/{job_id}` | `status` | `jobs.status` | same as list mapping |  |
| `/api/v1/media/embeddings/jobs/{job_id}` | `media_id` | `jobs.payload.media_id` | pass-through |  |
| `/api/v1/media/embeddings/jobs/{job_id}` | `user_id` | `jobs.owner_user_id` | pass-through |  |

Notes:
- Status filtering in list: `status=processing` filters after mapping; `status` in `{queued,completed,failed,cancelled}` filters by Jobs status.
- Embeddings stages run over Redis Streams; only the root job is stored in Jobs for status/billing.
- Content embeddings for collections run on Redis Streams (`embeddings:content`) and update the same root Jobs record.

---

## Chatbooks Export (public endpoints)
Domain: `chatbooks`
Queue: `CHATBOOKS_JOBS_QUEUE` (default: `default`)
Job type: `export`

| Endpoint | Public Field/Status | Jobs Source | Adapter Rule | Notes |
| --- | --- | --- | --- | --- |
| `/api/v1/chatbooks/export/jobs` | `status` | `jobs.status` | `queued -> pending`, `processing -> in_progress`, `completed/failed/cancelled` pass-through, `quarantined -> failed` | Matches current adapter. |
| `/api/v1/chatbooks/export/jobs/{job_id}` | `job_id` | `jobs.payload.chatbooks_job_id` | map payload `chatbooks_job_id` to legacy job id | Adapter falls back to `jobs.uuid` if payload missing. |
| `/api/v1/chatbooks/export/jobs/{job_id}` | `download_url` | `export_jobs.download_url` | read from artifact table | Artifact table remains authoritative. |
| `/api/v1/chatbooks/export/jobs/{job_id}` | `expires_at` | `export_jobs.expires_at` | read from artifact table | Artifact table remains authoritative. |

---

## Chatbooks Import (public endpoints)
Domain: `chatbooks`
Queue: `CHATBOOKS_JOBS_QUEUE` (default: `default`)
Job type: `import`

| Endpoint | Public Field/Status | Jobs Source | Adapter Rule | Notes |
| --- | --- | --- | --- | --- |
| `/api/v1/chatbooks/import/jobs` | `status` | `jobs.status` | `queued -> pending`, `processing -> in_progress`, `completed/failed/cancelled` pass-through, `quarantined -> failed` | Matches current adapter. |
| `/api/v1/chatbooks/import/jobs/{job_id}` | `job_id` | `jobs.payload.chatbooks_job_id` | map payload `chatbooks_job_id` to legacy job id | Adapter falls back to `jobs.uuid` if payload missing. |
| `/api/v1/chatbooks/import/jobs/{job_id}` | `items_imported` | `import_jobs.items_imported` | read from artifact table | Artifact table remains authoritative. |
| `/api/v1/chatbooks/import/jobs/{job_id}` | `conflicts_found` | `import_jobs.conflicts_found` | read from artifact table | Artifact table remains authoritative. |

---

## Prompt Studio (public endpoints + websocket)
Domain: `prompt_studio`
Queue: `PROMPT_STUDIO_JOBS_QUEUE` (default: `default`)
Job types: `optimization`, `evaluation`, `generation`

| Endpoint | Public Field/Status | Jobs Source | Adapter Rule | Notes |
| --- | --- | --- | --- | --- |
| `/api/v1/prompt-studio/optimizations/{job_id}` | `status` | `jobs.status` | `quarantined -> failed`, unknown -> `queued` | Matches current adapter. |
| `/api/v1/prompt-studio/optimizations/{job_id}` | `job_type` | `jobs.job_type` | pass-through |  |
| `/api/v1/prompt-studio/optimizations/{job_id}` | `progress` | `jobs.progress_percent` | `progress_percent / 100.0` | Returned only if progress present. |
| `prompt_studio_websocket` job updates | `status` | `jobs.status` | same as above | Uses adapter on broadcast. |

---

## Open Gaps / TODOs
- Phase 4 ops: run the Redis-vs-Jobs embeddings benchmark and validate Worker SDK usage in deployment.
