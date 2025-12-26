# Claims Monitoring Implementation Plan

## Goals
- Expose claims monitoring configuration via API for UI consumption.
- Emit claims provider, rebuild, and review metrics through the existing metrics registry.
- Provide lightweight health and alerting endpoints that can be wired to dashboards.

## Data Model
- `ClaimsMonitoringConfig`
  - `id` (PK), `workspace_id` (TEXT), `threshold_ratio` (REAL), `baseline_ratio` (REAL),
    `slack_webhook_url` (TEXT), `webhook_url` (TEXT), `email_recipients` (TEXT JSON),
    `enabled` (BOOLEAN), `created_at`, `updated_at`.
- `ClaimsMonitoringAlerts` (alert rules)
  - `id` (PK), `workspace_id` (TEXT), `name` (TEXT), `alert_type` (TEXT),
    `threshold_ratio` (REAL), `baseline_ratio` (REAL), `channels` (TEXT JSON),
    `enabled` (BOOLEAN), `created_at`, `updated_at`.
- `ClaimsMonitoringEvents`
  - `id` (PK), `workspace_id` (TEXT), `event_type` (TEXT), `severity` (TEXT),
    `payload_json` (TEXT), `created_at`.
- `ClaimsMonitoringHealth`
  - `id` (PK), `workspace_id` (TEXT), `queue_size` (INTEGER),
    `last_worker_heartbeat` (TIMESTAMP), `last_failure_at` (TIMESTAMP),
    `last_failure_reason` (TEXT), `updated_at`.

For v1, `workspace_id` maps to the current user id (string). Multi-tenant org/team
extensions should add org/team identifiers in later iterations.

## Metrics
Register in a dedicated claims monitoring module:
- `claims_provider_requests_total` (counter) labels: provider, model, mode.
- `claims_provider_latency_seconds` (histogram) labels: provider, model.
- `claims_provider_errors_total` (counter) labels: provider, model, reason.
- `claims_provider_estimated_cost_usd_total` (counter) labels: provider, model.
- `claims_rebuild_queue_size` (gauge).
- `claims_rebuild_processed_total` (counter).
- `claims_rebuild_failed_total` (counter).
- `claims_rebuild_job_duration_seconds` (histogram).
- `claims_rebuild_worker_heartbeat_timestamp` (gauge).
- `claims_review_queue_size` (gauge).
- `claims_review_processed_total` (counter).
- `claims_review_latency_seconds` (histogram).
- `claims_alert_webhook_delivered_total` (counter) labels: status (`success`, `failure`).
- `claims_alert_webhook_failed_total` (counter) labels: reason (`timeout`, `dns`, `tls`, `http_4xx`, `http_5xx`, `invalid_url`, `other`).
- `claims_alert_webhook_latency_seconds` (histogram) labels: status (`success`, `failure`).

## API Surface
- `GET /api/v1/claims/monitoring/config`
- `PATCH /api/v1/claims/monitoring/config`
- `GET /api/v1/claims/alerts`
- `POST /api/v1/claims/alerts`
- `PATCH /api/v1/claims/alerts/{alert_id}`
- `DELETE /api/v1/claims/alerts/{alert_id}`
- `GET /api/v1/claims/rebuild/health`
- `POST /api/v1/claims/analytics/export`

The monitoring config and alerts are stored in Media DB for now.

### Endpoint Semantics + Schemas
All endpoints are scoped to the current workspace (v1: user id). Unless noted,
responses include `created_at`/`updated_at` timestamps (ISO 8601).

#### GET /api/v1/claims/monitoring/config
Returns the single config row for the current workspace.

Response schema:
```
{
  "id": "string",
  "workspace_id": "string",
  "threshold_ratio": 0.0,     // float, nullable: false, min: 0.0
  "baseline_ratio": 0.0,      // float, nullable: false, min: 0.0, <= threshold_ratio
  "slack_webhook_url": "string|null", // nullable: true, https URL
  "webhook_url": "string|null",       // nullable: true, https URL
  "email_recipients": ["string"],     // array of email strings, nullable: true
  "enabled": true,
  "created_at": "string",
  "updated_at": "string"
}
```

#### PATCH /api/v1/claims/monitoring/config
Creates or updates the single config row for the current workspace.

Request schema (all optional; patchable fields):
```
{
  "threshold_ratio": 0.0,
  "baseline_ratio": 0.0,
  "slack_webhook_url": "string|null",
  "webhook_url": "string|null",
  "email_recipients": ["string"],
  "enabled": true
}
```
Constraints: `baseline_ratio <= threshold_ratio`, ratios >= 0.0; webhook URLs must be https.

Response schema: same as GET `/claims/monitoring/config`.

#### GET /api/v1/claims/alerts
Lists alert rules for the current workspace.

Response schema:
```
{
  "items": [
    {
      "id": "string",
      "workspace_id": "string",
      "name": "string",
      "alert_type": "string",          // e.g., "threshold_breach", "provider_error_rate"
      "threshold_ratio": 0.0,          // nullable: true, min: 0.0
      "baseline_ratio": 0.0,           // nullable: true, min: 0.0, <= threshold_ratio when both set
      "channels": {
        "slack": true,
        "webhook": true,
        "email": true
      },                               // nullable: false, at least one channel true
      "enabled": true,
      "created_at": "string",
      "updated_at": "string"
    }
  ]
}
```

#### POST /api/v1/claims/alerts
Creates an alert rule (not an event record). Events are written by the monitoring
pipeline into `ClaimsMonitoringEvents`.

Request schema (required fields: `name`, `alert_type`, `channels`):
```
{
  "name": "string",                   // non-empty
  "alert_type": "string",
  "threshold_ratio": 0.0,             // optional
  "baseline_ratio": 0.0,              // optional
  "channels": {
    "slack": true,
    "webhook": true,
    "email": true
  },
  "enabled": true
}
```
Constraints: `baseline_ratio <= threshold_ratio` when both provided; ratios >= 0.0.

Response schema: single alert rule (same shape as GET list item).

#### PATCH /api/v1/claims/alerts/{alert_id}
Updates an alert rule.

Request schema (patchable fields):
```
{
  "name": "string",
  "alert_type": "string",
  "threshold_ratio": 0.0,
  "baseline_ratio": 0.0,
  "channels": { "slack": true, "webhook": false, "email": true },
  "enabled": true
}
```
Response schema: single alert rule.

#### DELETE /api/v1/claims/alerts/{alert_id}
Deletes an alert rule.

Response schema:
```
{ "deleted": true }
```

#### GET /api/v1/claims/rebuild/health
Returns persisted service health for claims rebuild workers.

Response schema:
```
{
  "workspace_id": "string",
  "queue_size": 0,                    // integer, >= 0
  "last_worker_heartbeat": "string|null",
  "last_failure_at": "string|null",
  "last_failure_reason": "string|null",
  "updated_at": "string"
}
```

#### POST /api/v1/claims/analytics/export
Creates an export for claims monitoring analytics.

Request schema:
```
{
  "format": "csv|json",               // required
  "filters": {
    "workspace_id": "string|null",
    "event_type": "string|null",
    "severity": "string|null",
    "provider": "string|null",
    "model": "string|null",
    "start_time": "string|null",      // ISO 8601
    "end_time": "string|null"         // ISO 8601
  },
  "pagination": {
    "limit": 1000,                    // optional, max 10000
    "offset": 0                       // optional
  }
}
```

Response schema:
```
{
  "export_id": "string",
  "format": "csv|json",
  "status": "queued|ready|failed",
  "download_url": "string|null",
  "created_at": "string"
}
```
Download endpoint: `GET /api/v1/claims/analytics/export/{export_id}` returns the export payload (JSON) or CSV body.

#### GET /api/v1/claims/analytics/exports
Lists stored analytics exports.

Query params:
```
{
  "limit": 100,                       // optional, max 1000
  "offset": 0,                        // optional
  "status": "queued|ready|failed",    // optional
  "format": "csv|json",               // optional
  "workspace_id": "string|null"       // optional, admin only
}
```

Response schema:
```
{
  "exports": [
    {
      "export_id": "string",
      "format": "csv|json",
      "status": "queued|ready|failed",
      "download_url": "string|null",
      "created_at": "string",
      "updated_at": "string",
      "filters": "object|null",
      "pagination": "object|null",
      "error_message": "string|null"
    }
  ],
  "total": 0,
  "limit": 100,
  "offset": 0
}
```

Retention: exports older than `CLAIMS_ANALYTICS_EXPORT_RETENTION_HOURS` (default 24)
are deleted during new export creation.

### Error Handling
All endpoints return consistent error payloads:
```
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object|null"
  }
}
```
Status codes: 400 for validation failures, 401/403 for auth/permissions, 404 for
missing resources, 409 for conflicts, 429 for rate limits, 500 for unexpected errors.

Webhook delivery:
- Retry strategy: exponential backoff with jitter.
- Max retries: 5 attempts (initial attempt + 4 retries).
- Backoff schedule: 5s, 15s, 45s, 120s, 300s (cap at 5 minutes).
- On non-2xx response or network error, record a failed delivery event with
  reason and attempt count; log at warn and emit `claims_alert_webhook_failed_total`
  and `claims_alert_webhook_delivered_total{status="failure"}`.
- On success (2xx), record delivery success, log at info, emit
  `claims_alert_webhook_delivered_total{status="success"}`, and record
  `claims_alert_webhook_latency_seconds` with the observed duration.
- Reason/status mapping guidance:
  - `status="success"`: any 2xx response.
  - `status="failure"`: any non-2xx response or network/validation error.
  - `reason="http_4xx"`: response status 400-499.
  - `reason="http_5xx"`: response status 500-599.
  - `reason="timeout"`: connect/read timeout exceeded.
  - `reason="dns"`: name resolution failure.
  - `reason="tls"`: TLS handshake/verification error.
  - `reason="invalid_url"`: URL validation fails (scheme/host/SSRF policy).
  - `reason="other"`: fallback for uncategorized errors.

### Health Persistence
Health endpoints must read from persisted state in Media DB so multi-instance
restarts do not reset queue/heartbeat visibility. Workers update
`ClaimsMonitoringHealth` on each heartbeat and queue size change; the API reads
the latest row per workspace.

## Access Control
- Require `admin` role or `claims.admin` permission for config/alerts endpoints.
- Health endpoint should be limited to `admin`/SRE roles.

## Testing
- API tests for config CRUD and rebuild health response shape.
- Unit tests for metric registration and alert config serialization.
- Config CRUD cases: reject invalid `webhook_url`/`slack_webhook_url`, enforce
  `workspace_id` constraints on create/update, and return 404 on deleting
  non-existent configs.
- Alert threshold edge cases: validate `baseline_ratio <= threshold_ratio` and
  reject negative ratios.
- Integration coverage: webhook delivery retries and end-to-end alert emission
  from threshold breach to stored `ClaimsMonitoringEvents`.
