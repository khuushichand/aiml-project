# Claims Alerts Runbook

This runbook covers the Prometheus alerts in `Docs/Monitoring/claims_alerts_prometheus.yaml`.

## ClaimsUnsupportedRatioHigh
- **What it means**: The unsupported ratio for claims verification is above the threshold.
- **Immediate checks**:
  - Review recent provider changes or deploys.
  - Inspect `claims_monitoring_events` for recent `unsupported_ratio` entries.
  - Check `/api/v1/claims/analytics/dashboard` for spikes by provider/model.
- **Remediation**:
  - Lower `CLAIMS_ALERT_THRESHOLD_DEFAULT` if the threshold is too aggressive.
  - Switch to a fallback verifier/provider.
  - Trigger a targeted rebuild if ingestion-time extraction drifted.

## ClaimsRebuildQueueHigh
- **What it means**: Rebuild backlog exceeds the configured queue threshold.
- **Immediate checks**:
  - Verify rebuild worker is running (`/api/v1/claims/rebuild/health`).
  - Check worker logs for failures and retries.
- **Remediation**:
  - Increase worker capacity or concurrency.
  - Reduce scope (switch rebuild policy to `missing`).
  - Pause non-critical rebuilds until backlog clears.

## ClaimsRebuildHeartbeatStale
- **What it means**: Rebuild worker heartbeat is stale; worker may be down.
- **Immediate checks**:
  - Confirm the rebuild service process is running.
  - Inspect `claims_monitoring_health` persistence for last heartbeat.
- **Remediation**:
  - Restart the rebuild worker.
  - Check for DB locks or worker crashes before restart.

## ClaimsProviderErrorsSpike
- **What it means**: Claim provider errors are elevated.
- **Immediate checks**:
  - Review provider credentials, quotas, and rate limits.
  - Inspect logs for request failures or timeouts.
- **Remediation**:
  - Fail over to a backup provider/model.
  - Reduce concurrency or adjust retry settings.

## ClaimsAlertWebhookFailures
- **What it means**: Alert webhook delivery is failing.
- **Immediate checks**:
  - Inspect `claims_monitoring_events` for `webhook_delivery` failures.
  - Validate the destination URL and egress policy.
- **Remediation**:
  - Update webhook endpoints or allowlist domains.
  - Enable email digest delivery as a fallback channel.

## Related Docs
- Delivery setup: `Docs/Operations/Claims_Notifications_Delivery.md`
