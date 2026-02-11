# Email Sync Operations Runbook

Audience: Backend + SRE/Ops  
Status: Ready for staging dry-run

Related:
- PRD: `Docs/Product/Email_Ingestion_Search_PRD.md`
- Email APIs: `tldw_Server_API/app/api/v1/endpoints/email.py`
- Sync worker: `tldw_Server_API/app/services/connectors_worker.py`
- Sync state persistence: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Monitoring/alerts: `Docs/Operations/monitoring/README.md`, `Docs/Operations/monitoring/prometheus_alerts_tldw.yml`
- Env vars: `Docs/Operations/Env_Vars.md`

## Scope
Operational response guide for Gmail sync behavior in the normalized email ingestion pipeline, including:
- Retry/backoff incidents.
- Cursor invalidation and bounded replay/full-backfill escalation.
- Quota/throttle incidents and safe recovery.

## Runtime Components
- User-facing sync APIs:
  - `GET /api/v1/email/sources`
  - `POST /api/v1/email/sources/{source_id}/sync`
- Jobs domain:
  - `connectors` jobs created by `create_import_job(...)`.
  - Worker consumes `domain=connectors`, `queue=default`.
- Worker process:
  - In-process startup toggle: `CONNECTORS_WORKER_ENABLED=true`
  - Sidecar entrypoint: `python -m tldw_Server_API.app.services.connectors_worker`

## Required Controls
- Feature flags:
  - `EMAIL_GMAIL_CONNECTOR_ENABLED`
  - `EMAIL_OPERATOR_SEARCH_ENABLED`
  - `EMAIL_MEDIA_SEARCH_DELEGATION_MODE`
- Sync retry/backoff knobs:
  - `EMAIL_SYNC_RETRY_MAX_ATTEMPTS` (default `5`)
  - `EMAIL_SYNC_RETRY_BASE_SECONDS` (default `60`)
  - `EMAIL_SYNC_RETRY_MAX_BACKOFF_SECONDS` (default `3600`)
- Cursor recovery knobs:
  - `EMAIL_SYNC_CURSOR_RECOVERY_WINDOW_DAYS` (default `7`)
  - `EMAIL_SYNC_CURSOR_RECOVERY_MAX_MESSAGES` (default `2000`)
- Worker throughput:
  - `CONNECTORS_POLL_INTERVAL_SECONDS` (default `1.0`)

## Observability
Primary health views:
- `GET /api/v1/email/sources` for per-source `sync.state`, `error_state`, `retry_backoff_count`, `cursor`.
- `GET /api/v1/jobs/list?domain=connectors` for queue backlog and failed/running jobs.
- `POST /api/v1/jobs/retry-now` for controlled retry after remediation.

Prometheus metrics:
- `email_sync_runs_total{provider,status}`
- `email_sync_failures_total{provider,reason}`
- `email_sync_recovery_events_total{provider,outcome}`
- `email_sync_lag_seconds{provider}`

Relevant alerts:
- `TLDWEmailSyncFailureRateHigh`
- `TLDWEmailSyncLagP95High`

## Incident Triage
1. Confirm worker is running and acquiring `connectors` jobs.
2. Identify impacted sources via `GET /api/v1/email/sources`.
3. Classify incident by `sync.error_state` and metrics:
  - Retry/backoff saturation.
  - Invalid cursor recovery/full-backfill required.
  - Provider quota/throttle.
4. Apply scoped mitigation, then trigger targeted source sync.
5. Verify source returns to `sync.state=healthy` and metrics stabilize.

## Playbook A: Retry/Backoff Saturation
Symptoms:
- `sync.state=retrying` for extended windows.
- Result payload shows `skipped=backoff_active` or `skipped=retry_budget_exhausted`.

Actions:
1. Inspect source state:
```bash
curl -sS "$BASE/api/v1/email/sources" -H "X-API-KEY: $API_KEY"
```
2. Inspect failed/skipped connectors jobs:
```bash
curl -sS "$BASE/api/v1/jobs/list?domain=connectors&status=failed&limit=50" \
  -H "X-API-KEY: $API_KEY"
```
3. Remediate root cause (most often auth/token/provider instability).
4. Retry failed jobs:
```bash
curl -sS -X POST "$BASE/api/v1/jobs/retry-now" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"domain":"connectors","only_failed":true,"dry_run":false}'
```
5. Trigger source sync:
```bash
curl -sS -X POST "$BASE/api/v1/email/sources/$SOURCE_ID/sync" \
  -H "X-API-KEY: $API_KEY"
```

Exit criteria:
- Source reaches `sync.state=healthy`.
- `retry_backoff_count` resets to `0` after success.

## Playbook B: Invalid Cursor / Full Backfill Required
Symptoms:
- `sync.error_state` starts with `cursor_invalid_full_backfill_required`.
- `email_sync_recovery_events_total{outcome="full_backfill_required"}` increments.

Actions:
1. Confirm current cursor failure pattern in `/api/v1/email/sources`.
2. Temporarily tune recovery window/message cap:
  - Increase `EMAIL_SYNC_CURSOR_RECOVERY_WINDOW_DAYS`.
  - Increase `EMAIL_SYNC_CURSOR_RECOVERY_MAX_MESSAGES` conservatively.
3. Narrow source scope (label/query/max_messages) to bound replay cost:
```bash
curl -sS -X PATCH "$BASE/api/v1/connectors/sources/$SOURCE_ID" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"options":{"query":"newer_than:14d","max_messages":500}}'
```
4. Re-trigger sync and observe whether recovery downgrades to bounded replay and then healthy.
5. If repeated full-backfill-required persists:
  - Reconnect Gmail account (refresh token likely stale).
  - Re-run controlled backfill with temporary scope limits.

Exit criteria:
- Recovery events trend to `bounded_replay` or no recovery path needed.
- Cursor advances and source returns to healthy.

## Playbook C: Quota/Throttle Incidents
Symptoms:
- Repeated provider errors reflected as retrying/failed runs.
- Failure-rate alert (`TLDWEmailSyncFailureRateHigh`) active.

Actions:
1. Reduce pressure temporarily:
  - Increase `CONNECTORS_POLL_INTERVAL_SECONDS`.
  - Narrow source query/label scope.
2. Let retry backoff absorb provider cooldown.
3. After provider window resets, trigger sync for a single source and validate.
4. Retry failed backlog only after first healthy canary source.

Exit criteria:
- Failure-rate alert clears.
- No sustained growth in failed connectors jobs.

## Staging Dry-Run Checklist
- [ ] `EMAIL_GMAIL_CONNECTOR_ENABLED=true` and `CONNECTORS_WORKER_ENABLED=true` in staging.
- [ ] Queue sync via `POST /api/v1/email/sources/{id}/sync` and verify `domain=connectors` job created.
- [ ] Confirm source status transitions (`never_synced/running -> healthy|retrying|failed`).
- [ ] Simulate retry/backoff path and confirm skip behavior surfaces in job results.
- [ ] Simulate invalid-cursor path and confirm bounded replay/full-backfill-required telemetry.
- [ ] Validate failure-rate and lag alert paths in monitoring.

If staging has no active Gmail account, execute the same control flow with targeted local tests, then repeat this checklist once a staging account is available.

## References
- Endpoint tests: `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_email_search_endpoint.py`
- Worker sync tests: `tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py`
- M2 gate checklist: `Docs/Operations/Email_M2_Gate_Validation_Checklist.md`
