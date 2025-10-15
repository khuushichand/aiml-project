# Workflows Performance Tuning

Guidance for sizing and tuning the Workflows module under different backends.

## SQLite (Development / Light Workloads)

- WAL mode enabled with busy timeouts; inserts retry with backoff on contention.
- Keep concurrent writers modest. For heavier workloads, prefer Postgres.
- Use SSD/NVMe storage; avoid network filesystems.

## PostgreSQL (Recommended for Production)

- Connection Pooling
  - The Postgres backend uses `psycopg` with pooling; size pools according to CPU and workload.
  - Tune: min/max pool size, connection lifetime, and idle timeouts per environment.

- Indexes & Constraints
  - Unique `(run_id, event_seq)` guarantees ordered events per run.
  - JSONB payloads with GIN on `workflow_events.payload_json` (migrated in v3) enable JSON filtering when needed.

- Vacuum/Analyze
  - Use autovacuum; configure aggressive settings for high‑churn tables like `workflow_events`.

## Engine & Queues

- Tenant/workflow concurrency caps:
  - `WORKFLOWS_TENANT_CONCURRENCY` and `WORKFLOWS_WORKFLOW_CONCURRENCY`.

- Quotas/Rate Limits
  - Keep endpoint rate limits and per‑user quotas enabled outside tests; adjust for bursty clients.

## Monitoring

- Scrape metrics and build dashboards/duty alerts (examples under `monitoring/`).
- Track p95 step durations, queue depth, and webhook delivery outcomes per host.

