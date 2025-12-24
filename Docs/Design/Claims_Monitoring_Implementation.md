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
- `ClaimsMonitoringEvents`
  - `id` (PK), `workspace_id` (TEXT), `event_type` (TEXT), `severity` (TEXT),
    `payload_json` (TEXT), `created_at`.

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

## API Surface
- `GET /api/v1/claims/monitoring/config`
- `PATCH /api/v1/claims/monitoring/config`
- `GET /api/v1/claims/alerts`
- `POST /api/v1/claims/alerts`
- `PATCH /api/v1/claims/alerts/{alert_id}`
- `DELETE /api/v1/claims/alerts/{alert_id}`
- `GET /api/v1/claims/rebuild/health`
- `POST /api/v1/claims/analytics/export`

The monitoring config and alerts are stored in Media DB for now. Health endpoint
reads the claims rebuild service queue length, last worker heartbeat, and last
failure state tracked in memory.

## Access Control
- Require `admin` role or `claims.admin` permission for config/alerts endpoints.
- Health endpoint should be limited to `admin`/SRE roles.

## Testing
- API tests for config CRUD and rebuild health response shape.
- Unit tests for metric registration and alert config serialization.
