# Audio Concurrency and Metrics

This guide summarizes how audio quotas, concurrency, and metrics work and how to observe them in production. It also covers the optional Redis-backed counters and the dedicated GPU transcription queue.

## Overview

- Per-user quotas are enforced across HTTP and WebSocket paths via the Usage module.
- Concurrency can be tracked in-process or via Redis for multi-instance fairness.
- Audio Jobs worker supports a dedicated `transcribe` queue for GPU-bound stages.
- Admin endpoints expose summaries by status and owner to aid tuning.

## Key Env Vars

- `AUDIO_JOBS_WORKER_ENABLED`: Enable the in-process audio jobs worker at app startup (`true|false`).
- `AUDIO_JOBS_OWNER_STRICT`: Opt-in owner-aware acquisition heuristic for fair scheduling (`true|false`).
- `AUDIO_QUOTA_USE_REDIS`: Use Redis for active jobs/streams counters when `REDIS_URL` is set (`true|false`). Defaults to true if `REDIS_URL` is present.
- `REDIS_URL`: Redis connection string (e.g., `redis://localhost:6379`).

## Queues and Workers

- CPU worker (`run_audio_jobs_worker`) pulls from queue `default`.
- GPU worker (`run_audio_transcribe_gpu_worker`) pulls only `audio_transcribe` jobs from queue `transcribe` and enqueues the next stage back to `default`.
- Submit an audio job via `POST /api/v1/audio/jobs/submit`.

GPU worker container (stub):

```bash
# Build
docker build -f tldw_Server_API/Dockerfiles/Dockerfile.audio_gpu_worker -t tldw-audio-gpu-worker .

# Run (reads JOBS_DB_URL)
docker run --rm -e JOBS_DB_URL="sqlite:///./Databases/jobs.db" tldw-audio-gpu-worker
```

## Admin Endpoints

- List jobs (admin): `GET /api/v1/audio/jobs/admin/list`
- Summary counts: `GET /api/v1/audio/jobs/admin/summary`
- Summary by owner: `GET /api/v1/audio/jobs/admin/summary-by-owner`
- Owner processing count/limit: `GET /api/v1/audio/jobs/admin/owner/{owner_user_id}/processing`
- Audio tiers (get/set):
  - `GET /api/v1/audio/jobs/admin/tiers/{user_id}`
  - `PUT /api/v1/audio/jobs/admin/tiers/{user_id}`

## Metrics (What to Watch)

- Active streams (WS) and active jobs (HTTP/jobs) - per owner.
- Quota hits (daily minutes, concurrent streams/jobs).
- Jobs by status and by owner (queued/processing/completed/failed).

If you have a metrics registry enabled elsewhere in the app, consider publishing gauges for:

- `audio.active_streams{owner}`
- `audio.active_jobs{owner}`
- `audio.quota_hits{type="daily_minutes|concurrent_streams|concurrent_jobs"}`
- `audio.jobs{status,owner}`

## Redis-backed Concurrency

When `AUDIO_QUOTA_USE_REDIS=true` (or `REDIS_URL` is set), active counters are stored in Redis, allowing consistent enforcement across multiple processes/instances. If Redis is unavailable, the system falls back to in-process counters with warnings.

Recommended Redis settings:

- Set short TTLs (e.g., 120s) for active counters to auto-heal on process crashes.
- Use owner-scoped keys like `audio:active_streams:{owner}` and `audio:active_jobs:{owner}`.

## Troubleshooting

- If WS sessions close with code `4003` and `{ error_type: "quota_exceeded" }`, the daily minutes budget was exhausted mid-stream.
- If jobs appear starved for a specific owner, enable `AUDIO_JOBS_OWNER_STRICT=true` and inspect `/summary-by-owner`.
- If counters look inconsistent across replicas, verify `REDIS_URL` reachability and that `AUDIO_QUOTA_USE_REDIS=true` is set.
