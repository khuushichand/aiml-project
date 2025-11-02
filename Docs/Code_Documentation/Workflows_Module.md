Workflows Module

Overview
- Provides definition CRUD (minimal), run submission (saved/adhoc), events, artifacts, and basic control (pause/resume/cancel/retry).
- Background engine executes simple step types (prompt, rag_search, webhook, delay, log).

Route-Level Permissions
- workflows.runs.read: required for read endpoints (list runs, get run, events, artifacts, definition).
- workflows.runs.control: required for control endpoints (pause/resume/cancel/retry, approve/reject).
- In single-user mode, permissions are allowed by default. In multi-user mode, configure roles/permissions via AuthNZ RBAC.

Key Endpoints
- GET /api/v1/workflows/step-types
  - Lists available step types with minimal JSONSchema, example config, and min engine version.
  - Example:
    curl -H "X-API-KEY: $API_KEY" http://127.0.0.1:8000/api/v1/workflows/step-types

- GET /api/v1/workflows/runs/{run_id}/events?limit=&since=&types=
  - Paged events stream for a run. Use since (event_seq) for incremental polling.
  - Example:
    curl -H "X-API-KEY: $API_KEY" "http://127.0.0.1:8000/api/v1/workflows/runs/$RUN_ID/events?limit=200"

- POST /api/v1/workflows/runs/{run_id}/{action}
  - action: pause|resume|cancel|retry
  - Requires workflows.runs.control

DLQ Retry Worker (Webhooks)
- Purpose: retry webhook deliveries that failed during engine processing.
- Table: workflow_webhook_dlq (id, tenant_id, run_id, url, body_json, attempts, next_attempt_at, last_error, created_at)
- Service: enabled via WORKFLOWS_WEBHOOK_DLQ_ENABLED=true
- Backoff: exponential with jitter
  - WORKFLOWS_WEBHOOK_DLQ_BASE_SEC (default 30)
  - WORKFLOWS_WEBHOOK_DLQ_MAX_BACKOFF_SEC (default 3600)
  - WORKFLOWS_WEBHOOK_DLQ_MAX_ATTEMPTS (default 8)
  - WORKFLOWS_WEBHOOK_DLQ_INTERVAL_SEC (default 15)
  - WORKFLOWS_WEBHOOK_DLQ_BATCH (default 25)
  - WORKFLOWS_WEBHOOK_DLQ_TIMEOUT_SEC (default 10)

Tenant Allow/Deny Lists
- Global defaults:
  - WORKFLOWS_WEBHOOK_ALLOWLIST: comma-separated hostnames (supports wildcard like *.example.com)
  - WORKFLOWS_WEBHOOK_DENYLIST: comma-separated hostnames
- Tenant overrides:
  - WORKFLOWS_WEBHOOK_ALLOWLIST_<TENANT>, WORKFLOWS_WEBHOOK_DENYLIST_<TENANT>
  - Example: WORKFLOWS_WEBHOOK_ALLOWLIST_TEAM1=hooks.example.com,*.trusted.org

Operational Tips
- Permissions: grant workflows.runs.read to users who need visibility into runs beyond ownership; workflows.runs.control for operators.
- Events polling: clients should poll with since=last_seq and a reasonable limit (e.g., 200-500).
- Webhooks: set allowlist/denylist and keep DLQ enabled to ensure reliable delivery; monitor attempts and errors via DB queries.
