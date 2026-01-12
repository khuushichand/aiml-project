# Admin System Ops (Stage 5.3)

## Goals
- Provide a centralized system log feed with filtering and pagination.
- Offer incident history CRUD with a lightweight timeline.
- Expose maintenance mode controls with optional bypass allowlists.
- Manage feature flags across global/org/user scopes with audit metadata.

## Non-Goals
- Long-term log retention or external log aggregation integrations.
- Complex incident workflow automation (SLAs, paging, or on-call schedules).
- Enforcing feature flags across all subsystems (stage focuses on control plane).

## Data Model Notes
- **Maintenance State**: single global record with `enabled`, `message`, and allowlists.
- **Feature Flags**: keyed by (`key`, `scope`, `org_id`, `user_id`) with history entries.
- **Incidents**: stored with status/severity and a timeline of events.
- **Logs**: in-memory ring buffer plus a shared log file for cross-process queries.
- **Persistence**: maintenance state, feature flags, and incidents are stored in `Databases/system_ops.json`.
- **Concurrency**: the system ops store is protected with a file lock for multi-process safety.

## APIs

### Permissions
- All Admin System Ops endpoints require an admin principal.
- Mutating endpoints (maintenance, feature flags, incident create/update/delete) require a platform admin.

### System Logs

#### GET `/api/v1/admin/system/logs`
Returns recent log entries from an in-memory buffer.

Query params:
- `start`/`end` (optional ISO datetime)
- `level` (optional, e.g. `INFO`, `ERROR`)
- `service` (optional, logger/module filter)
- `query` (optional substring match against message)
- `org_id`/`user_id` (optional, based on log extras)
- `limit`/`offset`

Notes:
- Logs are aggregated across processes via `Databases/system_logs.jsonl`.
- Buffer size and log level are configurable via `SYSTEM_LOG_BUFFER_SIZE` and `SYSTEM_LOG_LEVEL`.
- File log behavior is configurable via `SYSTEM_LOG_FILE_ENABLED`, `SYSTEM_LOG_FILE_PATH`, and `SYSTEM_LOG_FILE_MAX_ENTRIES`.

Response:
```json
{
  "items": [
    {
      "timestamp": "2025-03-01T12:00:01Z",
      "level": "INFO",
      "message": "Job completed",
      "logger": "tldw_Server_API.app.core.Jobs.manager",
      "module": "manager",
      "function": "run_job",
      "line": 120,
      "request_id": "req_123",
      "org_id": 1,
      "user_id": 42
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### Maintenance Mode

#### GET `/api/v1/admin/maintenance`
Returns current maintenance state.

Response:
```json
{
  "enabled": false,
  "message": "",
  "allowlist_user_ids": [1, 2],
  "allowlist_emails": ["admin@example.com"],
  "updated_at": "2025-03-01T12:00:01Z",
  "updated_by": "admin@example.com"
}
```

#### PUT `/api/v1/admin/maintenance`
Update maintenance mode. When enabled, non-allowlisted users receive HTTP 503.

Request:
```json
{
  "enabled": true,
  "message": "Maintenance in progress. Please retry later.",
  "allowlist_user_ids": [1],
  "allowlist_emails": ["admin@example.com"]
}
```

### Feature Flags

#### GET `/api/v1/admin/feature-flags`
List feature flags with optional filtering.

Query params:
- `scope` (`global`|`org`|`user`)
- `org_id` (required for `org` scope)
- `user_id` (required for `user` scope)

Response:
```json
{
  "items": [
    {
      "key": "claims.monitoring",
      "scope": "global",
      "enabled": true,
      "description": "Enable claims monitoring features",
      "created_at": "2025-03-01T10:00:00Z",
      "updated_at": "2025-03-01T12:00:00Z",
      "updated_by": "admin@example.com",
      "history": [
        { "timestamp": "2025-03-01T12:00:00Z", "enabled": true, "actor": "admin@example.com" }
      ]
    }
  ],
  "total": 1
}
```

#### PUT `/api/v1/admin/feature-flags/{flag_key}`
Upsert a feature flag for the given scope.

Request:
```json
{
  "scope": "org",
  "org_id": 42,
  "enabled": false,
  "description": "Disable feature for org 42"
}
```

#### DELETE `/api/v1/admin/feature-flags/{flag_key}`
Remove a feature flag override for a specific scope.

Query params:
- `scope` (`global`|`org`|`user`)
- `org_id` (required for `org`)
- `user_id` (required for `user`)

### Incidents

#### GET `/api/v1/admin/incidents`
List incidents (newest first).

Query params:
- `status` (optional)
- `severity` (optional)
- `tag` (optional)
- `limit`/`offset`

Response:
```json
{
  "items": [
    {
      "id": "inc_123",
      "title": "RAG indexing backlog",
      "status": "investigating",
      "severity": "high",
      "summary": "Jobs delayed due to queue saturation.",
      "tags": ["rag", "queue"],
      "created_at": "2025-03-01T10:00:00Z",
      "updated_at": "2025-03-01T12:00:00Z",
      "resolved_at": null,
      "created_by": "admin@example.com",
      "updated_by": "admin@example.com",
      "timeline": [
        {
          "id": "evt_1",
          "message": "Incident created",
          "created_at": "2025-03-01T10:00:00Z",
          "actor": "admin@example.com"
        }
      ]
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### POST `/api/v1/admin/incidents`
Create a new incident.

#### PATCH `/api/v1/admin/incidents/{incident_id}`
Update incident status/summary/tags; optional `update_message` adds a timeline event.

#### POST `/api/v1/admin/incidents/{incident_id}/events`
Add a timeline entry.

#### DELETE `/api/v1/admin/incidents/{incident_id}`
Delete an incident (including its timeline).

## UI Notes
- Logs viewer includes filters for time range, level, service, and free-text search.
- Flags page includes maintenance mode toggle with allowlist editor.
- Incidents page shows a timeline card with status and severity badges.

## Audit & Observability
- Maintenance updates, feature flag changes, and incident updates emit audit events.
- Logs viewer surfaces request IDs when present in log extras.
