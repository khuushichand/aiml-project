# Jobs-Module-1: Generic Job Manager Extraction (Design + Plan)

## Overview

This document proposes extracting a generic, domain-agnostic Job Manager from the existing Prompt Studio queue so it can be reused across subsystems (Chatbooks, Embeddings, RAG batch tasks, etc.). The new module lives under `tldw_Server_API/app/core/Jobs/` and offers a consistent API for creating, leasing, processing, cancelling, and observing background jobs, with DB-backed persistence (SQLite/Postgres) and metrics.

## Goals

- Provide a single, reusable job queue for all modules.
- Preserve proven behaviors (leases, priority, retries, metrics) from Prompt Studio.
- Maintain backward compatibility for Prompt Studio while enabling adoption by Chatbooks and others.
- Keep multi-backend support (SQLite + Postgres) with the existing DB backend abstraction.

## Non-Goals

- Replace all module-specific workers in this iteration.
- Introduce external brokers (Redis/RabbitMQ). Optional in later phases.

## Current State (Prompt Studio)

- `Prompt Studio` uses `JobManager` backed by `PromptStudioDatabase` with job lease/renew, retries, priority, and rich metrics.
- Schema and tools are within the Prompt Studio namespace, making reuse possible but awkward for other domains.

## Proposed Architecture

Directory: `tldw_Server_API/app/core/Jobs/`

- `models.py`
  - `Job`, `JobStatus` (`queued`, `processing`, `completed`, `failed`, `cancelled`), `JobType` (string enum), `Lease` info.
  - `Domain` and `Queue` strings to namespace jobs.
- `storage.py`
  - Storage interface and DB implementation using existing backend adapters (SQLite/Postgres).
  - SQL helpers & migrations.
- `manager.py`
  - Generic `JobManager` with:
    - `create_job(domain, queue, job_type, payload, owner_user_id, project_id=None, priority=5, max_retries=3)`
    - `get_job(id|uuid)`, `get_job_by_uuid(uuid)`
    - `list_jobs(filter by domain/queue/type/status/owner)`
    - `acquire_next_job(domain, queue, lease_seconds, worker_id)` + `renew_job_lease(id, seconds)`
    - `complete_job(id, result)`, `fail_job(id, error, retryable)`
    - `cancel_job(id)`
- `metrics.py`
  - Pluggable reporter; default metrics with labels: `domain`, `queue`, `job_type`.
- `config.py`
  - Defaults + env overrides (`JOBS_MAX_LEASE_SECONDS`, `JOBS_MAX_CONCURRENCY`, etc.).

## Data Model / Schema

Table: `jobs`

Columns (common across SQLite/Postgres):
- `id` INTEGER PRIMARY KEY (serial in PG)
- `uuid` (TEXT in SQLite, UUID in Postgres; UNIQUE)
- `domain` TEXT, `queue` TEXT, `job_type` TEXT
- `owner_user_id` TEXT NULL, `project_id` INTEGER NULL
- `idempotency_key` TEXT NULL UNIQUE (optional, domain/queue/type scoped)
- `payload` JSON/TEXT, `result` JSON/TEXT
- `status` TEXT (queued|processing|completed|failed|cancelled)
- `priority` INTEGER DEFAULT 5, `max_retries` INTEGER DEFAULT 3, `retry_count` INTEGER DEFAULT 0
- `available_at` TIMESTAMP NULL (schedule or backoff)
- `leased_until` TIMESTAMP NULL, `lease_id` TEXT NULL, `worker_id` TEXT NULL, `acquired_at` TIMESTAMP NULL
- `error_message` TEXT, `last_error` TEXT
- `cancel_requested_at` TIMESTAMP NULL, `cancelled_at` TIMESTAMP NULL, `cancellation_reason` TEXT NULL
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `completed_at` TIMESTAMP NULL

Indexes:
- `(domain, queue, status, available_at, priority, created_at)`
- `(leased_until)`
- `(status)`
- `(uuid)`
- `(owner_user_id, status, created_at)`

Notes:
- Use existing backend adapters in `DB_Management/backends/*` to maintain dual-backend support.
- For Postgres, prefer `JSONB` for `payload`/`result` and `UUID` for `uuid` (e.g., `DEFAULT gen_random_uuid()`).
- Keep timestamps timezone-aware in Postgres (`TIMESTAMPTZ`) and ISO8601 strings in SQLite; ensure `updated_at` is set on every write (trigger or application code).

Priority semantics:
- Lower number = higher priority. Tie-break on `available_at` then `created_at` to reduce starvation.

Retention:
- Prune completed/failed jobs after a configurable TTL.

Backoff:
- On retry, set `available_at = now() + backoff_with_jitter` and increment `retry_count`.

## API Surface (Python)

```python
jm = JobManager(db)

job = jm.create_job(
    domain="chatbooks",
    queue="default",
    job_type="export",
    payload={"name": "Weekly Backup", "selections": {...}},
    owner_user_id=user_id,
    priority=5,
)

next_job = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=60, worker_id="worker-1")
jm.renew_job_lease(next_job["id"], seconds=60)
jm.complete_job(next_job["id"], worker_id="worker-1", lease_id=next_job["lease_id"], result={"file": "/path/to/archive"})

jm.cancel_job(job_id, reason="user_request")

Notes:
- `complete_job` and `fail_job` must include the current `worker_id` and `lease_id` to prevent stale workers from overwriting state.
- Add `schedule_job(..., available_at=...)` for delayed jobs.

Cancellation semantics:
- If a job is `queued`, `cancel_job` transitions immediately to `cancelled` and sets `cancelled_at`.
- If a job is `processing`, `cancel_job` sets `cancel_requested_at` and `cancellation_reason`. Workers must check for cancellation between chunks and fail fast.

Retry/backoff:
- `fail_job(..., retryable=True)` increments `retry_count` and schedules `available_at` based on exponential backoff with jitter until `max_retries` is reached.

Idempotency:
- If `idempotency_key` is provided, duplicate `create_job` calls return the existing job.

Lease renewal:
- `renew_job_lease` requires matching `worker_id` and `lease_id` and extends `leased_until` within a configured max.

Acquisition filtering:
- Acquisition and listing calls accept `owner_user_id` and `project_id` filters, but access control is enforced at the service/endpoint layer (see Security section).
```

## Metrics

- Gauges: `jobs.queued`, `jobs.processing`, `jobs.backlog`, `jobs.stale_processing`
- Counters: `jobs.completed`, `jobs.failed`, `jobs.retries_total`, `jobs.cancellations_total`
- Histograms: `jobs.duration_seconds`, `jobs.queue_latency_seconds`
- Labels: `domain`, `queue`, `job_type`
- Strategy: preserve existing Prompt Studio metrics via wrappers/aliases with labels.

Metric definitions:
- `queue_latency_seconds = acquired_at - created_at`
- `duration_seconds = completed_at - acquired_at`
- `stale_processing = count(status='processing' AND leased_until < now())`

## Configuration

- `JOBS_MAX_LEASE_SECONDS` (default 60)
- `JOBS_HEARTBEAT_SECONDS` (default lease/2, min 2, max 30)
- `JOBS_MAX_CONCURRENCY` (per processor instance)
- `JOBS_ENABLE_METRICS=true|false`
- Feature flags for rollout:
  - `TLDW_JOBS_BACKEND=prompt_studio|core` (module-wide default)
  - Domain overrides, e.g., `CHATBOOKS_JOBS_BACKEND=prompt_studio|core` (overrides module default)
  - Precedence: domain override > module default

## Security & Multi-Tenant

- The core Jobs module is domain-agnostic and treats payloads as opaque.
- Enforce `owner_user_id` and RBAC scoping at the service/endpoint layer using the existing AuthNZ system.
- Within the Jobs module, ensure isolation via `domain`/`queue` and enforce correctness with leases (`worker_id`, `lease_id`, `leased_until`).
- Validate payload schemas at domain adapters (e.g., Chatbooks/Prompt Studio) with Pydantic.

Auditing:
- Emit audit logs (state transitions) via `core/Audit/unified_audit_service.py` using DI (e.g., `get_audit_service_for_user`).

## Migration Plan

Phase 1: Create Jobs module (core)
- Implement `manager.py`, `storage.py`, `models.py`, `metrics.py`.
- Add migrations for `jobs` table (SQLite + Postgres).
- Unit tests for CRUD, lease/renew, retries, cancel, metrics.

Phase 2: Prompt Studio Adapter
- Add `PromptStudioJobManager` façade mapping to core `JobManager` while returning the same shapes expected by Prompt Studio.
- Introduce `domain="prompt_studio"` and queue names to preserve semantics.
- Keep existing PS metrics but source from the generic reporter with labels.

Phase 3: Prompt Studio Cutover
- Route PS job creation/lease/cancel through core `JobManager` behind `TLDW_JOBS_BACKEND=core` (or domain override) flag.
- Keep legacy table/views as needed or migrate records into `jobs` with a one-time migration.
- Dual-path tests: assert equivalent behavior on SQLite/Postgres.

Phase 4: Chatbooks Adoption
- Replace in-process task registry with core `JobManager` (`domain="chatbooks"`, `job_type="export"|"import"`).
- Implement cancellable workers that check lease/cancellation points between steps (export packaging, import item loops).
- Endpoint tests for async jobs + cancellation.

Phase 5: Broader Adoption
- Embeddings and other long-running operations adopt the core manager incrementally.

Phase 6: Deprecation
- Deprecate old Prompt Studio queue API; maintain compatibility via adapter for one release.
- Remove legacy code after adoption + docs complete.

## Backward Compatibility

- Prompt Studio continues to function via façade; record shapes preserved.
- Provide a view or compatibility layer if PS queries legacy table names.

## Testing Strategy

- Unit tests in `tests/Jobs/`:
  - create/list/get, lease/renew, retries, cancel, metrics, dual backend
- Integration tests per domain adopter (PS, Chatbooks):
  - end-to-end job lifecycle + cancellation + metrics sanity
- Property tests for lease correctness (no duplicate processing).

## Risks & Mitigations

- Schema drift: keep explicit migrations and views; dual-path tests reduce risk.
- Metrics regressions: map existing metrics to new labels; alert on deltas.
- Cancellation depth: ensure workers check cancellation/lease between chunks.
- SQLite concurrency: use `BEGIN IMMEDIATE` and atomic update-with-select to avoid double leases under write contention.

## Timeline (Estimate)

- Phase 1 (core module): 1-2 days
- Phase 2 (PS façade + wiring): 1-2 days
- Phase 3 (PS cutover + tests): 0.5-1 day
- Phase 4 (Chatbooks adopt + tests): 1 day
- Total: ~3.5-6.5 days across short iterations

## Acceptance Criteria (DoD)

- [ ] Jobs module passes unit tests on SQLite + Postgres
- [ ] Prompt Studio operates fully via core Jobs behind flag
- [ ] Chatbooks export/import run via core Jobs (flagged) with cancellation
- [ ] Metrics exposed with `domain`/`job_type` labels and verified
- [ ] Docs updated (API, Dev Guide, Ops)

## Acquisition & Concurrency Semantics

Acquisition contract:
- Only consider jobs with `status='queued'`, `(available_at IS NULL OR available_at <= now)`, and either not leased or lease expired.
- Acquisition atomically transitions the job to `processing` and sets `worker_id`, `lease_id`, `leased_until`, and `acquired_at` within a single transaction.

Acknowledgement rules:
- `complete_job`/`fail_job` must provide `worker_id` and `lease_id`. If they do not match the current lease, the operation must be rejected.
- `renew_job_lease` extends `leased_until` when `worker_id`/`lease_id` match and within configured maximums.

Cancellation:
- `cancel_job` sets `cancel_requested_at` if `processing`, or transitions to `cancelled` if `queued`.
- Workers are required to check `cancel_requested_at` and lease validity between chunks and before final write.

Fairness:
- Order by `priority ASC, available_at ASC NULLS FIRST, created_at ASC` to prevent starvation; consider aging if needed.

## Open Questions

- Should we standardize queue names across domains (`default`, `high`, `low`)?
- Do we want optional Redis broker in a future phase for scale-out workers?
- How strict should we enforce payload schemas per domain (lightweight Pydantic in adapters)?

## Appendix A: Example DDL (SQLite)

Note: SQLite stores timestamps as ISO8601 TEXT. Use triggers or application code to keep `updated_at` current.

```sql
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  uuid TEXT UNIQUE,
  domain TEXT NOT NULL,
  queue TEXT NOT NULL,
  job_type TEXT NOT NULL,
  owner_user_id TEXT,
  project_id INTEGER,
  idempotency_key TEXT UNIQUE,
  payload TEXT,
  result TEXT,
  status TEXT NOT NULL,
  priority INTEGER DEFAULT 5,
  max_retries INTEGER DEFAULT 3,
  retry_count INTEGER DEFAULT 0,
  available_at TEXT,
  leased_until TEXT,
  lease_id TEXT,
  worker_id TEXT,
  acquired_at TEXT,
  error_message TEXT,
  last_error TEXT,
  cancel_requested_at TEXT,
  cancelled_at TEXT,
  cancellation_reason TEXT,
  created_at TEXT DEFAULT (DATETIME('now')),
  updated_at TEXT DEFAULT (DATETIME('now')),
  completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_lookup ON jobs(domain, queue, status, available_at, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(leased_until);
CREATE INDEX IF NOT EXISTS idx_jobs_owner_status ON jobs(owner_user_id, status, created_at);

-- Keep updated_at current
CREATE TRIGGER IF NOT EXISTS trg_jobs_updated_at
AFTER UPDATE ON jobs
FOR EACH ROW
BEGIN
  UPDATE jobs SET updated_at = DATETIME('now') WHERE id = NEW.id;
END;
```

## Appendix B: Example DDL (Postgres)

Requires `pgcrypto` (preferred) or `uuid-ossp` for UUID generation.

```sql
-- Enable one of these extensions (choose one available in your environment)
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- for uuid_generate_v4()

CREATE TABLE IF NOT EXISTS jobs (
  id BIGSERIAL PRIMARY KEY,
  uuid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
  domain TEXT NOT NULL,
  queue TEXT NOT NULL,
  job_type TEXT NOT NULL,
  owner_user_id TEXT,
  project_id BIGINT,
  idempotency_key TEXT UNIQUE,
  payload JSONB,
  result JSONB,
  status TEXT NOT NULL,
  priority INT NOT NULL DEFAULT 5,
  max_retries INT NOT NULL DEFAULT 3,
  retry_count INT NOT NULL DEFAULT 0,
  available_at TIMESTAMPTZ,
  leased_until TIMESTAMPTZ,
  lease_id TEXT,
  worker_id TEXT,
  acquired_at TIMESTAMPTZ,
  error_message TEXT,
  last_error TEXT,
  cancel_requested_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_lookup ON jobs(domain, queue, status, available_at, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(leased_until);
CREATE INDEX IF NOT EXISTS idx_jobs_owner_status ON jobs(owner_user_id, status, created_at);

-- Keep updated_at current
CREATE OR REPLACE FUNCTION set_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON jobs;
CREATE TRIGGER trg_jobs_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION set_jobs_updated_at();
```

## Appendix C: Acquisition Algorithms (SQL)

Postgres (single statement, atomic acquisition):

```sql
WITH cte AS (
  SELECT id
  FROM jobs
  WHERE domain = $1
    AND queue = $2
    AND status = 'queued'
    AND (available_at IS NULL OR available_at <= NOW())
    AND (leased_until IS NULL OR leased_until <= NOW())
  ORDER BY priority ASC, available_at ASC NULLS FIRST, created_at ASC
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE jobs j
SET status = 'processing',
    worker_id = $3,
    lease_id = $4,
    leased_until = NOW() + ($5 || ' seconds')::interval,
    acquired_at = NOW(),
    updated_at = CURRENT_TIMESTAMP
FROM cte
WHERE j.id = cte.id
RETURNING j.*;
```

SQLite (transaction + update-with-select):

```sql
BEGIN IMMEDIATE;
WITH next AS (
  SELECT id FROM jobs
  WHERE domain = ?
    AND queue = ?
    AND status = 'queued'
    AND (available_at IS NULL OR available_at <= DATETIME('now'))
    AND (leased_until IS NULL OR leased_until <= DATETIME('now'))
  ORDER BY priority ASC, available_at ASC, created_at ASC
  LIMIT 1
)
UPDATE jobs
SET status = 'processing',
    worker_id = ?,
    lease_id = ?,
    leased_until = DATETIME('now', printf('+%d seconds', ?)),
    acquired_at = DATETIME('now')
WHERE id = (SELECT id FROM next);

SELECT * FROM jobs WHERE id = (SELECT id FROM next);
COMMIT;
```

Completion/failure requires matching the current lease:

```sql
-- Postgres example
UPDATE jobs
SET status = 'completed', result = $4, completed_at = NOW(), updated_at = CURRENT_TIMESTAMP
WHERE id = $1 AND worker_id = $2 AND lease_id = $3
RETURNING *;

-- Failure with retryable backoff
UPDATE jobs
SET status = CASE WHEN retry_count + 1 >= max_retries THEN 'failed' ELSE 'queued' END,
    retry_count = retry_count + 1,
    last_error = $5,
    error_message = $5,
    available_at = CASE WHEN retry_count + 1 >= max_retries THEN NULL ELSE NOW() + ($6 || ' seconds')::interval END,
    updated_at = CURRENT_TIMESTAMP
WHERE id = $1 AND worker_id = $2 AND lease_id = $3
RETURNING *;
```

Cancellation:

```sql
-- If queued, cancel immediately
UPDATE jobs
SET status = 'cancelled', cancelled_at = NOW(), cancellation_reason = $2, updated_at = CURRENT_TIMESTAMP
WHERE id = $1 AND status = 'queued'
RETURNING *;

-- If processing, request cancellation
UPDATE jobs
SET cancel_requested_at = NOW(), cancellation_reason = $2, updated_at = CURRENT_TIMESTAMP
WHERE id = $1 AND status = 'processing'
RETURNING *;
```

## Appendix D: Example Usage (Chatbooks)

Synchronous worker:

```python
import time
from tldw_Server_API.app.core.Jobs.manager import JobManager

jm = JobManager(db)
job = jm.create_job(
    domain="chatbooks", queue="default", job_type="export",
    payload={"name": name, "selections": content_selections}, owner_user_id=user_id,
)

while True:
    job = jm.acquire_next_job("chatbooks", "default", lease_seconds=60, worker_id="cb-worker-1")
    if not job:
        time.sleep(2)
        continue
    try:
        # process export/import
        jm.complete_job(job["id"], worker_id="cb-worker-1", lease_id=job["lease_id"], result={"path": archive_path})
    except Exception as e:
        jm.fail_job(job["id"], worker_id="cb-worker-1", lease_id=job["lease_id"], error=str(e), retryable=True)
```

Asynchronous worker (if the API is async):

```python
import asyncio
from tldw_Server_API.app.core.Jobs.manager import JobManager

jm = JobManager(db)

async def run_worker():
    while True:
        job = await jm.acquire_next_job("chatbooks", "default", lease_seconds=60, worker_id="cb-worker-1")
        if not job:
            await asyncio.sleep(2)
            continue
        try:
            # process export/import
            await jm.complete_job(job["id"], worker_id="cb-worker-1", lease_id=job["lease_id"], result={"path": archive_path})
        except Exception as e:
            await jm.fail_job(job["id"], worker_id="cb-worker-1", lease_id=job["lease_id"], error=str(e), retryable=True)

asyncio.run(run_worker())
```
