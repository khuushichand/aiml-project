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

### Worker Operations
- Cancellation checkpoints: check before each `update_job_progress` call, after download/staging, before conversion/transcription, before chunk/analyze, and immediately before DB writes and cleanup.
- Worker configuration: start with a small pool (e.g., 2-4 workers per host) and per-worker concurrency of 1 for CPU/GPU-heavy stages; scale based on queue depth, CPU/GPU availability, and staging disk budget.
- Cleanup failure handling: cleanup is best-effort; log failures with `batch_id`/`job_id`, mark the cleanup as pending in results/logs, and rely on a background janitor task (see Staging) to retry without failing successful ingestion.

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

Design doc overview only. See `Docs/API-related/Media_Ingest_Jobs_API.md` for detailed schemas, HTTP status codes, and error formats, and keep this section aligned with that spec.

## Cancellation Semantics
- `cancel_job(job_id)` marks `status=cancelled` immediately.
- Worker checks cancellation at specific checkpoints: before each `update_job_progress` call, after download/staging, before conversion/transcription, before chunk/analyze, and immediately before DB writes and cleanup.
- If cancelled mid-flight, worker finalizes as cancelled and skips persistence.
- Staged file cleanup is best-effort: failures are logged with `batch_id`/`job_id`, marked as pending in results/logs, and retried by the background janitor task without blocking job finalization.

## Staging
- Uploaded files are saved under a per-request temp directory.
- Base path: configurable, with a recommended layout like `/tmp/tldw/ingest/{batch_id}/job_{job_id}/` to avoid collisions and simplify cleanup.
- Staging directory path is stored in job payload for cleanup.
- Disk limits: enforce max file size per item and total batch size at submit time (when size is known) and while streaming to disk; reject with a 413-style error when limits are exceeded.
- Cleanup timing: cleanup runs immediately after job completion or cancellation; a background janitor also removes expired staging directories.
- Orphaned files: detect directories with no active job and older than a configured TTL (e.g., 24h) and delete them in the janitor pass.
- For URLs, staging is not required unless download-to-disk is needed for processing.

## Progress
- Worker updates progress via `update_job_progress` at each stage:
  - `prepare`: validate inputs, resolve options, and create staging paths.
  - `download`: fetch URL content or move uploaded files into staging.
  - `convert`: normalize formats and extract text/audio where needed.
  - `transcribe`: run STT for audio/video inputs.
  - `chunk`: split content into chunks for indexing/analysis.
  - `analyze`: metadata extraction, embeddings, and enrichment.
  - `persist`: write DB records and finalize job result before cleanup.

## Operations
### Observability
- Logs: structured logs with `batch_id`, `job_id`, stage, and duration; include cleanup failures and cancellation outcomes.
- Metrics: job counts (queued/running/succeeded/failed/cancelled), stage duration histograms, queue depth, worker utilization, staging disk usage, and cleanup failure counts.
- Alerts: sustained failure rate spikes, queue depth near cap, and staging disk usage above safe thresholds.

### Timeouts & Retries
- Timeouts are stage-specific (download/convert/transcribe/analyze) and should fail the job with a clear error when exceeded.
- Retries are limited to transient failures (network, provider timeouts) with exponential backoff; validation errors are not retried.
- Cancellation checks occur between retries and before each new attempt.

### Resource Limits
- Maximum file size per item and maximum total batch size are configurable and enforced at submit and during staging.
- Queue depth caps prevent unbounded backlog; submissions beyond the cap return a clear backpressure error.
- Per-user concurrency caps limit the number of active jobs per user.
- Worker scaling: keep concurrency at 1 for CPU/GPU-heavy stages, and scale worker count to available cores/GPUs and staging disk budget.

## Security
- [ ] File validation: verify magic bytes and MIME type, enforce maximum file size limits, and run content-scanning (AV/malware and harmful content) in the ingestion pipeline before processing.
- [ ] Path traversal: sanitize and normalize all staging directory and filename handling, and reject any attempt to escape staging roots.
- [ ] Resource limits: enforce per-user rate limits at submit, cap max concurrent jobs per user in scheduling, and apply total queue depth caps with explicit enforcement points.
- [ ] Secret sanitization: JobManager secret scan removes/flags secrets from job payloads/results; see JobManager secret scan documentation for details.
- [ ] Reuse existing SSRF defenses and file validation logic where applicable.
- [ ] Enforce owner access via existing auth deps.

## Testing
- Unit tests for job submission validation, job creation, cancel behavior.
- Integration test: submit -> cancel -> status is `cancelled`.
- Integration test: job completes and persists when not cancelled.
- Error handling: worker crash recovery, stage timeouts, and cleanup failures are handled and reported.
- Edge cases: disk exhaustion during staging, oversized files, and malformed uploads are rejected cleanly.
- Concurrency: cancel during DB writes or cleanup does not corrupt DB state or leave staging leaks.
- Load: multiple concurrent batches, queue depth limits, and worker pool saturation behave as expected.

## Migration / Compatibility
- Synchronous endpoints remain for now.
- Frontend can opt into new submit/poll/cancel flow incrementally.
- Deprecation timeline: keep sync endpoints for at least one or two release cycles after async is stable; announce deprecation in release notes before removal.
- Rollout strategy: feature-flag async ingestion in the WebUI and roll out by tenant or environment with a fallback to sync.
- In-flight requests: existing synchronous requests continue to completion during deploys; async workers remain backward compatible with queued jobs.
- Monitoring: track usage of sync vs async endpoints and error rates to guide the deprecation timeline.
