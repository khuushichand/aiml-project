# Admin Data Ops (Stage 5.2)

## Goals
- Provide admin-controlled backups and restores for core data stores.
- Allow admins to view/update retention policies that drive scheduled cleanup.
- Support server-side exports for audit logs and user lists.

## Non-Goals
- Multi-tenant bulk backup orchestration (per-org bulk jobs).
- Long-running job orchestration beyond synchronous backup/restore.
- Automatic retention enforcement for new datasets without scheduler support.

## Dataset Keys
- `media`: Media_DB_v2 (per-user)
- `chacha`: ChaChaNotes (per-user)
- `prompts`: prompts DB (per-user)
- `evaluations`: evaluations DB (per-user)
- `audit`: unified audit DB (per-user)
- `authnz`: users/auth DB (system, SQLite or Postgres)

## APIs

### Backups

#### GET `/api/v1/admin/backups`
List backup artifacts.

Query params:
- `dataset` (optional, one of dataset keys)
- `user_id` (optional; required for per-user datasets)
- `limit`/`offset` for paging

Response:
```json
{
  "items": [
    {
      "id": "media_backup_20250228_101530.db",
      "dataset": "media",
      "user_id": 1,
      "status": "ready",
      "size_bytes": 123456,
      "created_at": "2025-02-28T10:15:30Z"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

#### POST `/api/v1/admin/backups`
Create a backup snapshot.

Request:
```json
{
  "dataset": "media",
  "user_id": 1,
  "backup_type": "full",
  "max_backups": 10
}
```

Response:
```json
{
  "item": {
    "id": "media_backup_20250228_101530.db",
    "dataset": "media",
    "user_id": 1,
    "status": "ready",
    "size_bytes": 123456,
    "created_at": "2025-02-28T10:15:30Z"
  }
}
```

#### POST `/api/v1/admin/backups/{backup_id}/restore`
Restore a backup snapshot. Requires explicit confirmation.

Request:
```json
{
  "dataset": "media",
  "user_id": 1,
  "confirm": true
}
```

Response:
```json
{
  "status": "restored",
  "message": "Database restored from media_backup_20250228_101530.db"
}
```

#### Full Bundle Export/Import (Planned Extension)
Admin Data Ops bundles are intended to package multiple per-dataset backups into a single downloadable artifact with manifest and checksums. See `Docs/Product/DB_Exports_SQLite_PRD.md` for the current design and scope.

### Retention Policies

#### GET `/api/v1/admin/retention-policies`
Returns current retention windows (days).

Response:
```json
{
  "policies": [
    { "key": "audit_logs", "days": 180, "description": "AuthNZ audit log retention" },
    { "key": "usage_logs", "days": 180, "description": "Usage log retention" }
  ]
}
```

#### PUT `/api/v1/admin/retention-policies/{policy_key}`
Update a retention window.

Request:
```json
{ "days": 365 }
```

Response:
```json
{ "key": "audit_logs", "days": 365, "description": "AuthNZ audit log retention" }
```

### Exports

#### GET `/api/v1/admin/audit-log/export`
Export audit logs as CSV or JSON.

Query params:
- Same filters as `/api/v1/admin/audit-log` (`user_id`, `action`, `resource`, `start`, `end`, `days`, `org_id`)
- `format` (`csv`|`json`, default `csv`)
- `limit` (optional, defaults to 10000)
- `offset` (optional, defaults to 0)

#### GET `/api/v1/admin/users/export`
Export users as CSV or JSON.

Query params:
- Same filters as `/api/v1/admin/users` (`role`, `is_active`, `search`, `org_id`)
- `format` (`csv`|`json`, default `csv`)
- `limit` (optional, defaults to 10000)
- `offset` (optional, defaults to 0)

## Retention Policy Mapping
- `audit_logs` -> `AUDIT_LOG_RETENTION_DAYS`
- `usage_logs` -> `USAGE_LOG_RETENTION_DAYS`
- `llm_usage_logs` -> `LLM_USAGE_LOG_RETENTION_DAYS`
- `usage_daily` -> `USAGE_DAILY_RETENTION_DAYS`
- `llm_usage_daily` -> `LLM_USAGE_DAILY_RETENTION_DAYS`
- `sessions` -> `SESSION_LOG_RETENTION_DAYS`
- `privilege_snapshots` -> `PRIVILEGE_SNAPSHOT_RETENTION_DAYS`
- `privilege_snapshots_weekly` -> `PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS`

Updates persist in the AuthNZ database and load on boot; UI changes override default env/config values.

Defaults (deploy-time):
- Set the corresponding environment variables in your deployment config (.env, systemd unit, Docker compose, or k8s env) to seed defaults when no override exists.
- Example:
  ```bash
  export AUDIT_LOG_RETENTION_DAYS=365
  export USAGE_LOG_RETENTION_DAYS=180
  export LLM_USAGE_LOG_RETENTION_DAYS=90
  ```

Resetting overrides:
- Delete rows from `retention_policy_overrides` in the AuthNZ database to fall back to env defaults.

Roadmap: Stage 5.3 retention persistence is implemented; follow-up work includes adding a UI "reset to defaults" action.

## Implementation Status
- API endpoints implemented in `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py` (Data Ops section).
- Service logic implemented in `tldw_Server_API/app/services/admin_data_ops_service.py`.
- Retention policy overrides persist in AuthNZ DB via `retention_policy_overrides` (see `tldw_Server_API/app/core/AuthNZ/retention_policies.py`).
- Admin UI is planned (admin-ui); no current UI surface.

## UI Notes
- Data Ops page (planned for admin-ui) provides:
  - Backup list with create + restore actions.
  - Retention policy table with inline edits.
  - Export buttons for audit logs and users (CSV/JSON).
- Destructive actions require confirmation and emit audit events.
- Retention policy edits should require confirmation because they persist across restarts and affect cleanup windows.
