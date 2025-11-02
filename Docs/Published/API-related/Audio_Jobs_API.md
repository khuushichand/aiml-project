# Audio Jobs API (Published)

Submit and manage background audio processing jobs using the Jobs module. These endpoints run in parallel to existing synchronous and streaming STT APIs.

Base path: `/api/v1/audio`

- POST `/jobs/submit` - submit job (url/local_path, model, chunking, analysis)
- GET `/jobs/{job_id}` - get job status (owner/admin)
- GET `/jobs/admin/list` - list jobs (admin)
- GET `/jobs/admin/summary` - counts by status (admin)
- GET `/jobs/admin/owner/{owner_user_id}/processing` - owner’s processing and limit (admin)

Worker flags:
- `AUDIO_JOBS_WORKER_ENABLED` (default false)
- `AUDIO_JOBS_OWNER_STRICT` (default false)

Quotas:
- Per-user concurrent jobs and daily minutes enforced across HTTP/WS and Jobs worker.
