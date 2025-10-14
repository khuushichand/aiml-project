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
- `JOBS_ALLOWED_QUEUES` / `JOBS_ALLOWED_QUEUES_<DOMAIN>`: Comma‑separated allowlists to restrict queue names (in addition to standard queues).
- `JOBS_MAX_JSON_BYTES` (default 1048576): Max serialized bytes for `payload` and `result`.
- `JOBS_JSON_TRUNCATE` (default false): If true, truncate oversize `payload`/`result` to a small marker instead of rejecting.
- `JOBS_ARCHIVE_BEFORE_DELETE` (default false): When true, `prune_jobs` copies rows to `jobs_archive` before deletion.
- `JOBS_SQLITE_SINGLE_UPDATE_ACQUIRE` (default false): Use an optional single‑UPDATE acquisition path on SQLite under contention.
- TTL (optional):
  - `JOBS_TTL_ENFORCE` (default false): Enable periodic TTL sweeps in the metrics loop.
  - `JOBS_TTL_AGE_SECONDS`: Max age for queued jobs (by `created_at`).
  - `JOBS_TTL_RUNTIME_SECONDS`: Max runtime for processing jobs (by `COALESCE(started_at, acquired_at)`).
  - `JOBS_TTL_ACTION`: `cancel` (default) or `fail`.
 - Domain‑scoped RBAC (optional):
   - `JOBS_DOMAIN_SCOPED_RBAC` (default false): Enforce domain scope for admin endpoints.
   - `JOBS_REQUIRE_DOMAIN_FILTER` (default false): Require the `domain` query/body field for domain‑scoped endpoints.
   - `JOBS_DOMAIN_ALLOWLIST_<USER_ID>`: Comma‑separated domain allowlist for a specific user id.

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
  - Manager exposes `prune_jobs(statuses, older_than_days, domain=None, queue=None, job_type=None, dry_run=False)` to delete old `completed/failed/cancelled` jobs based on `completed_at` (fallback to `created_at`).
  - Use `domain`/`queue`/`job_type` to scope deletion; pass `dry_run=True` to preview the count only (no deletes).
  - Admin endpoint (admin-only): `POST /api/v1/jobs/prune`
    - Request (JSON):
      - `statuses`: list of statuses, e.g. `["completed","failed","cancelled"]`
      - `older_than_days`: integer days threshold (min 1)
      - Optional filters: `domain`, `queue`, `job_type`
      - Optional `dry_run`: boolean (default false)
      - Optional `detail_top_k`: integer (0..100). When `dry_run=true`, compute top‑K groups by count (for preview).
    - Response: `{ "deleted": <int> }` — for dry runs this is the would-delete count.
  - Examples:
    - Preview prune for a single queue:
      ```bash
      curl -X POST "$BASE/api/v1/jobs/prune" \
        -H "X-API-KEY: $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
              "statuses": ["completed","failed"],
              "older_than_days": 14,
              "domain": "chatbooks",
              "queue": "default",
              "job_type": "export",
              "dry_run": true
            }'
      ```
    - Execute the prune (remove `dry_run` or set false):
      ```bash
      # Same body with "dry_run": false
      ```
  - WebUI:
    - Admin → Jobs includes a Prune panel with a “Dry Run (count only)” toggle and a “Saved Filters” badge reflecting current Domain/Queue/Job Type filters. Use Reset Filters to clear.

- Metrics:
  - Gauges: `prompt_studio.jobs.queued{...}` (ready only), `prompt_studio.jobs.scheduled{...}`, `prompt_studio.jobs.processing{...}`, `prompt_studio.jobs.backlog{...}` (ready + scheduled).
  - Histograms: `prompt_studio.jobs.duration_seconds{...}`, `prompt_studio.jobs.queue_latency_seconds{...}`.
  - Counters: `prompt_studio.jobs.created_total{...}`, `prompt_studio.jobs.completed_total{...}`, `prompt_studio.jobs.cancelled_total{...}`, `prompt_studio.jobs.retries_total{...}`, `prompt_studio.jobs.failures_total{...,reason}`.
  - Lease tuning: `prompt_studio.jobs.time_to_expiry_seconds{...}` histogram reflects remaining time on active leases.

### Docker Compose (Postgres)

- The repository ships a `docker-compose.yml` with a `postgres` service. To run Jobs on Postgres when using Compose:
  - Set the DSN using the `postgres` service hostname inside the Compose network:
    - `export JOBS_DB_URL=postgresql://tldw_user:ChangeMeStrong123!@postgres:5432/tldw_users`
  - Start services:
    - `docker compose up --build`
  - From your host, you can also connect via the published port:
    - `export JOBS_DB_URL=postgresql://tldw_user:ChangeMeStrong123!@localhost:5432/tldw_users`
  - The Jobs manager will auto‑provision the schema on first use.

### Running Postgres Jobs tests

- Ensure a Postgres instance is available (e.g., via Compose above) and set one of:
  - `export JOBS_DB_URL=postgresql://tldw_user:ChangeMeStrong123!@localhost:5432/tldw_users`
  - or `export POSTGRES_TEST_DSN=postgresql://...`
- Run only PG‑marked Jobs tests:
  - `python -m pytest -m "pg_jobs" -v tldw_Server_API/tests/Jobs`

- TTL Sweep (optional):
  - Admin endpoint (admin-only): `POST /api/v1/jobs/ttl/sweep`
    - Request: `{ age_seconds?: int, runtime_seconds?: int, action: 'cancel'|'fail', domain?: string, queue?: string, job_type?: string }`
    - Action applies to queued jobs older than `age_seconds` and processing jobs running longer than `runtime_seconds`.
    - Response: `{ "affected": <int> }`.
  - Metrics integrate with the centralized metrics manager; no external setup required.

## Notes

- SQLite is suitable for single-instance or dev; Postgres is recommended for multi-worker deployments.
- Avoid long leases; prefer short leases with renewals.
- Workers should check `cancel_requested_at` and verify lease validity between chunks before writing final results.

## API: Stats and Listing

- `GET /api/v1/jobs/stats` (admin-only): returns aggregated counts per `(domain, queue, job_type)` with fields:
  - `queued` (ready only), `scheduled` (available in the future), `processing`
  - Filterable by `domain`, `queue`, `job_type`

- `GET /api/v1/jobs/list` (admin-only): paged job listing with `domain`, `queue`, `status`, `owner_user_id`, `job_type`, `limit`

## Schema Notes

- New installs enforce:
  - CHECK status ∈ {queued, processing, completed, failed, cancelled}
  - CHECK priority in [1..10], max_retries in [0..100]
  - progress_percent [0..100] and progress_message fields (workers can update via `renew_job_lease`)
  - Postgres adds partial indexes accelerating counts and acquisitions
