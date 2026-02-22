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

## ClaimsOutputParseErrorsSpike
- **What it means**: Structured parse failures are elevated for claims extraction or verification output.
- **Alert threshold**: 10-minute parse errors are at least 20 and parse-error ratio is above 8% of provider requests.
- **Immediate checks**:
  - Inspect `claims_output_parse_events_total{outcome="error"}` by `provider`, `model`, and `mode`.
  - Compare `claims_response_format_selected_total` to ensure `json_schema`/`json_object` is still applied.
  - Review recent prompt/schema or provider adapter changes.
- **Remediation**:
  - Force strict structured output where supported (`response_format`).
  - Roll back prompt changes that introduced schema drift.
  - Temporarily increase heuristic fallback coverage while parser regressions are fixed.

## ClaimsFallbackSpike
- **What it means**: Claims flows are frequently degrading to fallback paths.
- **Alert threshold**: 10-minute fallback events are at least 30 and fallback ratio is above 15% of provider requests.
- **Immediate checks**:
  - Inspect `claims_fallback_total` by `reason` (`throttle`, `budget`, `parse_error`, `provider_error`, `empty_claims`).
  - Cross-check provider health in `claims_provider_errors_total` and latency histograms.
  - Check budget/throttle settings for overly strict limits.
- **Remediation**:
  - Adjust budget/throttle thresholds to match current traffic.
  - Shift traffic to healthier provider/model combinations.
  - Fix upstream parse/provider failures causing repeat fallback.

## Threshold Tuning Guidance
- Start with the default ratio thresholds (`8%` parse errors, `15%` fallback) for at least one full weekday traffic cycle.
- If low-traffic tenants trigger noisy alerts, increase minimum-event gates before changing ratios.
- If high-traffic tenants miss incidents, reduce ratio thresholds in `1-2%` increments and re-evaluate with dashboard trends.

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
