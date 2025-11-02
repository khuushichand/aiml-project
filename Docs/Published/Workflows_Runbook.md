# Workflows Runbook (Curated)

Operational guidance for migrations, backups, retention, and incident triage. See the full document at `../Operations/Workflows_Runbook.md`.

## Migrations

- PostgreSQL
  - Schema managed on startup by the server. Check version: `SELECT version FROM workflow_schema_version;`
  - Known migration (v3): convert `workflow_events.payload_json` to JSONB with a GIN index.
  - Procedure: snapshot → maintenance mode → start single server → verify schema bump → exit maintenance.
  - Rollback: stop app and restore snapshot; restart older server version.

- SQLite
  - Idempotent schema at startup; WAL + busy timeouts enabled. For manual migrations, back up DB and use a transaction (`BEGIN IMMEDIATE; ... COMMIT;`).

## Backups

- SQLite
  - Cold: stop server, copy `Databases/workflows.db` (and `-wal` if present).
  - Hot: `sqlite3 Databases/workflows.db '.backup Databases/workflows.backup-YYYYMMDD.db'`
  - Verify: run a test instance with the backup DB and hit `GET /api/v1/workflows/runs`.

- PostgreSQL
  - Logical: `pg_dump -Fc -f workflows-YYYYMMDD.dump $DATABASE_URL_WORKFLOWS`
  - PITR: enable WAL archiving; follow org policy.
  - Verify: `pg_restore -l workflows-*.dump` and restore into staging for validation.

## Retention

- Artifacts
  - Worker: `WORKFLOWS_ARTIFACT_GC_ENABLED=true`
  - Settings: `WORKFLOWS_ARTIFACT_RETENTION_DAYS`, `WORKFLOWS_ARTIFACT_GC_INTERVAL_SEC`
  - Deletes DB rows and file:// paths older than cutoff.

- Runs/Events
  - No hard cutoff by default. Consider periodic deletion by age for high-volume deployments.

## Incident Triage

- Run not visible
  - Check tenant/owner; admins can filter `owner=`. Ensure API and tests point to the same DB (check `DATABASE_URL_WORKFLOWS`).

- Webhook not firing
  - Ensure `WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS` is off. Inspect `webhook_delivery` events and DLQ (`SELECT * FROM workflow_webhook_dlq`).
  - If signing enabled, receiver must HMAC `"{ts}.{body}"` using `X-Signature-Timestamp` and `WORKFLOWS_WEBHOOK_SECRET`.

- Event ordering
  - Verify `(run_id, event_seq)` uniqueness and counters table health.

- SQLite lock errors
  - WAL + busy timeouts generally suffice; reduce concurrency or move to Postgres if persistent.

- Artifact 404/403
  - Confirm artifact exists for run; review path containment vs recorded `workdir` (strict mode enforces). Ensure route/test share DB.

## Debug Flags

- `WORKFLOWS_DEBUG=1` - broad Workflows debug logs
- `WORKFLOWS_ARTIFACTS_DEBUG=1` - artifact endpoint logs (IDs, paths, Range)
- `WORKFLOWS_DLQ_DEBUG=1` - DLQ list/replay and worker logs
