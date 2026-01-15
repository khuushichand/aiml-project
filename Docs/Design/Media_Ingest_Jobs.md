# Media Ingestion Jobs (Async + Cancellation)

## Summary
Introduce a Jobs-backed media ingestion pipeline that supports user cancellation, one job per item, and staged uploads. This replaces long-running synchronous ingestion with submit/poll/cancel semantics while reusing existing processing and persistence logic.

## Goals
- Allow users to cancel media ingestion/transcription before completion.
- Support all media types handled by `/media/add` (audio, video, pdf, document, ebook, email, json).
- Use one job per input item with a shared `batch_id` for grouping.
- Preserve existing processing behavior and DB persistence when not cancelled.
- Keep payloads small and secrets-free.

## Non-Goals
- Replacing existing synchronous endpoints immediately (they remain as-is).
- Perfect mid-stage preemption for all third-party processing libraries.
- Distributed cancellation signaling beyond the Jobs DB.

## Architecture
### Flow
1. Client submits `/api/v1/media/ingest/jobs` with AddMediaForm fields and optional file uploads.
2. Files are staged to a temp directory (cleanup deferred).
3. One JobManager job per input item is created in domain `media_ingest` with a shared `batch_id`.
4. Worker (`media_ingest_worker`) processes jobs using existing ingestion helpers and checks for cancellation.
5. On cancel, worker skips DB writes and cleans staged files.

### Jobs Domain
- Domain: `media_ingest`
- Queue: `default` (standard queues)
- Job type: `media_ingest_item`
- Result: small summary only (counts, media_id, error)

### Payload (per job)
- `batch_id`: UUID grouping the job set
- `media_type`: matches AddMediaForm
- `source`: URL or staged file path
- `source_kind`: `url` | `file`
- `original_filename`: for uploads (optional)
- `temp_dir`: staging directory for cleanup (optional)
- `options`: AddMediaForm fields (sans files/urls)

## API
### Submit
`POST /api/v1/media/ingest/jobs`
- Body: AddMediaForm fields via form-data + files
- Response: `batch_id`, list of `job_ids`, per-item errors

### Status
`GET /api/v1/media/ingest/jobs/{job_id}`
- Returns job row + progress fields + small result summary

### Cancel
`DELETE /api/v1/media/ingest/jobs/{job_id}`
- Cancels queued or processing job (JobManager cancel)
- Owner/admin check required

### Optional Batch Status
`GET /api/v1/media/ingest/jobs?batch_id=...`
- Returns jobs for batch (owner/admin scoped)

## Cancellation Semantics
- `cancel_job(job_id)` marks `status=cancelled` immediately.
- Worker checks cancellation before heavy steps and before DB writes.
- If cancelled mid-flight, worker finalizes as cancelled and skips persistence.
- Best-effort cleanup of staged files on cancel or completion.

## Staging
- Uploaded files are saved under a per-request temp directory.
- Staging directory is stored in job payload for cleanup.
- For URLs, staging is not required.

## Progress
- Worker updates progress via `update_job_progress` at each stage:
  - `prepare`, `download`, `convert`, `transcribe`, `chunk`, `analyze`, `persist`

## Security
- Reuse existing SSRF and file validation logic.
- Payload is sanitized by JobManager secret scan.
- Enforce owner access via existing auth deps.

## Testing
- Unit tests for job submission validation, job creation, cancel behavior.
- Integration test: submit -> cancel -> status is `cancelled`.
- Integration test: job completes and persists when not cancelled.

## Migration / Compatibility
- Synchronous endpoints remain for now.
- Frontend can opt into new submit/poll/cancel flow incrementally.
