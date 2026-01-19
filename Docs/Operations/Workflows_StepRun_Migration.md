# Workflows Step Run Migration Plan

This change adds `tenant_id` and `assigned_to` columns to `workflow_step_runs`.

## Scope

- SQLite: adds columns via `ALTER TABLE` and backfills `tenant_id` from `workflow_runs`.
- Postgres: schema version bump to v5; adds columns and backfills `tenant_id` from `workflow_runs`.

## Rollout Steps

1) Deploy code with schema version v5.
2) Restart the API server so it runs the Workflows DB initialization.
3) Verify columns exist:

```sql
-- Postgres
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'workflow_step_runs'
  AND column_name IN ('tenant_id', 'assigned_to');

-- SQLite
PRAGMA table_info(workflow_step_runs);
```

4) Verify backfill:

```sql
SELECT COUNT(*) AS missing_tenant
FROM workflow_step_runs
WHERE tenant_id IS NULL OR tenant_id = '';
```

5) Optional cleanup: if any rows are missing `tenant_id`, run a manual backfill:

```sql
UPDATE workflow_step_runs
SET tenant_id = workflow_runs.tenant_id
FROM workflow_runs
WHERE workflow_step_runs.run_id = workflow_runs.run_id
  AND (workflow_step_runs.tenant_id IS NULL OR workflow_step_runs.tenant_id = '');
```

## Notes

- `assigned_to` is nullable and only populated for `wait_for_human` / `wait_for_approval` steps.
- `tenant_id` is required for new rows; existing rows are backfilled best-effort.
