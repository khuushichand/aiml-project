# Media Ingest Jobs API

Submit background media ingestion jobs with cancellation support.

Base path: `/api/v1/media`

## Endpoints

- POST `/ingest/jobs` - Submit jobs (one job per item)
  - Body: multipart form-data matching `/media/add` fields plus optional `files`
  - Response: `{ batch_id, jobs: [{ id, uuid, source, source_kind, status }], errors: [] }`
  - Notes: `errors` contains per-item staging failures; if every item fails, response uses HTTP 207.

- GET `/ingest/jobs/{job_id}` - Get job status (owner or admin)
  - Response includes progress fields (`progress_percent`, `progress_message`), result summary,
    and payload metadata (`media_type`, `source`, `source_kind`, `batch_id`).

- DELETE `/ingest/jobs/{job_id}` - Cancel a job (owner or admin)
  - Response: `{ success, job_id, status, message }`

## Cancellation Semantics

- Cancellation is cooperative and best-effort.
- Queued jobs are cancelled immediately.
- In-flight jobs check cancellation before persistence and finalize as `cancelled` without DB writes.

## Worker

- Service: `tldw_Server_API/app/services/media_ingest_jobs_worker.py`
- Env flags:
  - `MEDIA_INGEST_JOBS_WORKER_ENABLED`: `true|false` (default false)
  - `MEDIA_INGEST_JOBS_QUEUE`: queue name (default `default`)
  - `JOBS_DB_URL` or `JOBS_DB_PATH`: Jobs backend (Postgres DSN or SQLite path)

## Staging

- Uploads are staged into a per-file temp directory.
- The temp dir is stored in the job payload and cleaned up by the worker on completion/cancel.
