# Workflows Performance (Curated)

Sizing and tuning guidance for SQLite and PostgreSQL. See the full guide at `../Operations/Workflows_Performance.md`.

## SQLite

- WAL mode + busy timeouts; keep concurrent writers modest.
- Use SSD/NVMe; avoid network filesystems.
- Tune `PRAGMA busy_timeout` and keep batch writes small.
- For continuous backups, consider Litestream; avoid I/O contention during peaks.

## PostgreSQL

- Pooling: size min/max pool, lifetime, and idle timeouts to match workload.
- Indexes: ensure unique `(run_id, event_seq)`; add GIN on `workflow_events.payload_json` (v3); B-tree on `(tenant_id, status, created_at)`.
- Autovacuum: keep aggressive for high-churn `workflow_events`.

## Engine & Queues

- Concurrency caps: `WORKFLOWS_TENANT_CONCURRENCY`, `WORKFLOWS_WORKFLOW_CONCURRENCY`.
- Rate limits/quotas: keep enabled outside tests; prefer batched submissions to avoid thundering herds.

## Monitoring

- Track p95 step durations, queue depth, and webhook outcomes per host.
- Watch DB metrics: lock waits, autovacuum, connection saturation, row churn.
