# Media Ingest Jobs API

Submit background media ingestion jobs with cancellation support.

Base path: `/api/v1/media`

## Endpoints

- POST `/ingest/jobs` - Submit jobs (one job per item)
  - Body: multipart form-data matching `/media/add` fields plus optional `files`
  - Response: `{ batch_id, jobs: [{ id, uuid, source, source_kind, status }], errors: [] }`
  - Notes: `errors` contains per-item staging failures; if every item fails, response uses HTTP 207.

- GET `/ingest/jobs?batch_id=...` - List jobs for a batch (owner or admin)
  - Response: `{ batch_id, jobs: [MediaIngestJobStatus...] }`
  - Notes: Uses indexed `batch_group` lookup with legacy payload fallback for older rows.

- GET `/ingest/jobs/{job_id}` - Get job status (owner or admin)
  - Response includes progress fields (`progress_percent`, `progress_message`), result summary,
    and payload metadata (`media_type`, `source`, `source_kind`, `batch_id`).

- DELETE `/ingest/jobs/{job_id}` - Cancel a job (owner or admin)
  - Response: `{ success, job_id, status, message }`

- POST `/ingest/jobs/cancel?batch_id=...` - Cancel jobs for an entire batch (owner or admin)
  - Alias: `session_id` can be provided instead of `batch_id`
  - Optional query: `reason`
  - Response:
    - `{ success, batch_id, requested, cancelled, already_terminal, failed, message }`

- GET `/ingest/jobs/events/stream` - Stream ingest job events via SSE (owner or admin)
  - Optional query: `batch_id` to scope to one batch
  - Optional query: `after_id` to resume from a previous event id
  - Stream events:
    - `snapshot` event containing current job statuses
    - `job` events containing incremental `event_id`, `job_id`, `event_type`, and `attrs`

## Cancellation Semantics

- Cancellation is cooperative and best-effort.
- Queued jobs are cancelled immediately.
- In-flight jobs check cancellation before persistence and finalize as `cancelled` without DB writes.
- Audio/video ingestion attempts to preempt long-running FFmpeg/STT work when cancellation is requested.
- Batch/session cancellation applies the same semantics to each matched non-terminal job.

## Worker

- Service: `tldw_Server_API/app/services/media_ingest_jobs_worker.py`
- Env flags:
  - `MEDIA_INGEST_JOBS_WORKER_ENABLED`: `true|false` (default false)
  - `MEDIA_INGEST_JOBS_QUEUE`: queue name (default `default`)
  - `JOBS_DB_URL` or `JOBS_DB_PATH`: Jobs backend (Postgres DSN or SQLite path)

## Staging

- Uploads are staged into a per-file temp directory.
- The temp dir is stored in the job payload and cleaned up by the worker on completion/cancel.
