# Workflows Runbook

Operational guidance for running, migrating, backing up, and troubleshooting the Workflows module.

## Migrations

- Postgres
  - Workflows schema is created/updated by `WorkflowsDatabase._initialize_schema_backend()` on startup.
  - Verify schema version: `SELECT version FROM workflow_schema_version;` Must match `_CURRENT_SCHEMA_VERSION` in `Workflows_DB.py`.
  - If upgrading from legacy schema with `payload_json TEXT`, v3 migration converts to `JSONB` and adds a GIN index.
  - Safe rollback: ensure no data loss by taking a snapshot (see Backups) before applying updates.

- SQLite
  - Schema is applied idempotently at startup. WAL mode and busy timeout are enabled; write bursts use backoff.

## Backups

- SQLite
  - Snapshot the `Databases/workflows.db` file while the server is stopped or via `.backup` pragma for hot backups.
  - Store snapshots with timestamps; test restore by spinning a temp instance.

- Postgres
  - Use `pg_dump` per your RPO/RTO policies. Recommended: daily logical backups; WAL archiving for point‑in‑time recovery.

## Retention

- Artifact GC worker (optional)
  - Enable: `WORKFLOWS_ARTIFACT_GC_ENABLED=true`.
  - Configure: `WORKFLOWS_ARTIFACT_RETENTION_DAYS` (default 30), `WORKFLOWS_ARTIFACT_GC_INTERVAL_SEC`.
  - Policy: delete file:// artifacts from disk if present and remove DB rows older than cutoff.

## Incident Triage

1) User cannot see run
   - Check tenant and owner constraints; admins can filter with `owner=`.
2) Webhook not firing
   - Confirm `WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS` is not set.
   - Check `webhook_delivery` events for `blocked|failed`.
   - Validate egress policy and allowlists; inspect DLQ with `SELECT * FROM workflow_webhook_dlq`.
3) Event stream out of order / missing
   - Validate uniqueness of `(run_id, event_seq)` and counters table health.
4) “database is locked” (SQLite)
   - WAL mode and busy timeout should handle most cases; reduce concurrency or move to Postgres.

## Maintenance

- Verify readiness endpoints `/readyz` and `/healthz` in monitoring.
- Review schema version and DLQ queue depth during upgrades.
- Periodically audit allow/deny lists and retention policy according to compliance.

