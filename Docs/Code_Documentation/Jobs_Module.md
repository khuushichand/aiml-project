# Jobs Module

The Jobs module provides a reusable, DB‑backed job queue with leasing, retries, cancellation, and metrics. It is domain‑agnostic and used by Chatbooks and Prompt Studio; other subsystems can adopt it incrementally.

## Standard Queues

- default
- high
- low

Use these names across domains to keep operations consistent.

## Configuration

- `JOBS_DB_URL` (optional): PostgreSQL DSN (e.g., `postgresql://user:pass@host:5432/db`). If not set, SQLite is used at `Databases/jobs.db`.
- `JOBS_LEASE_SECONDS` (default 60): Lease duration when acquiring.
- `JOBS_LEASE_RENEW_SECONDS` (default 30): Worker renewal cadence.
- `JOBS_LEASE_RENEW_JITTER_SECONDS` (default 5): Renewal jitter to avoid herds.
- `JOBS_LEASE_MAX_SECONDS` (default 3600): Cap for lease extension.
- `JOBS_ENFORCE_LEASE_ACK` (default false): When true, `renew/complete/fail` require matching `worker_id` and `lease_id` (prevents stale workers from acking).

Endpoint: `GET /api/v1/config/jobs` lists backend, flags, and standard queues.

## Core API (Python)

```python
from tldw_Server_API.app.core.Jobs.manager import JobManager

jm = JobManager()  # auto-selects SQLite or Postgres

# Create a job (queued)
job = jm.create_job(
    domain="chatbooks",
    queue="default",
    job_type="export",
    payload={"name": "Weekly", "chatbooks_job_id": "abc123"},
    owner_user_id="1",
    priority=5,
)

# Acquire next job with a lease
lease_seconds = 60
worker_id = "worker-1"
job = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=lease_seconds, worker_id=worker_id)
lease_id = job["lease_id"]

# Periodically renew (enforcement on)
jm.renew_job_lease(job["id"], seconds=lease_seconds, worker_id=worker_id, lease_id=lease_id)

# Complete with enforcement (recommended)
jm.complete_job(job["id"], result={"path": "/path/to/file"}, worker_id=worker_id, lease_id=lease_id)

# Fail (retryable or terminal)
jm.fail_job(job["id"], error="boom", retryable=True, worker_id=worker_id, lease_id=lease_id)
```

## Operational Guidance

- Leases and Reclaim:
  - Expired `processing` leases are reclaimed on the next acquire.
  - Set `JOBS_ENFORCE_LEASE_ACK=true` in production to enforce correct acknowledgements.

- Priorities and Fairness:
  - Lower `priority` = higher priority.
  - Acquisition order: `priority ASC`, then `available_at/created_at ASC`.

- Pruning:
  - Manager exposes `prune_jobs(statuses, older_than_days)` to delete old `completed/failed/cancelled` jobs based on `completed_at` (fallback to `created_at`).
  - Admin endpoint: `POST /api/v1/jobs/prune` with body `{ "statuses": ["completed","failed"], "older_than_days": 30 }` (requires auth).

- Metrics:
  - Gauges: `prompt_studio.jobs.queued{domain,queue,job_type}`, `prompt_studio.jobs.processing{...}`, `prompt_studio.jobs.backlog{...}`.
  - Histograms: `prompt_studio.jobs.duration_seconds{...}`, `prompt_studio.jobs.queue_latency_seconds{...}`.
  - Counters: `prompt_studio.jobs.retries_total{...}`, `prompt_studio.jobs.failures_total{...,reason}`.
  - Metrics integrate with the centralized metrics manager; no external setup required.

## Notes

- SQLite is suitable for single-instance or dev; Postgres is recommended for multi-worker deployments.
- Avoid long leases; prefer short leases with renewals.
- Workers should check `cancel_requested_at` and verify lease validity between chunks before writing final results.

