# Claims Metrics

## Provider Metrics
- `claims_provider_requests_total{provider,model,mode}`
- `claims_provider_latency_seconds{provider,model}`
- `claims_provider_errors_total{provider,model,reason}`
- `claims_provider_estimated_cost_usd_total{provider,model}`
- `claims_provider_budget_exhausted_total{provider,model,mode,reason}`
- `claims_provider_throttled_total{provider,model,mode,reason}`

## Structured Output & Parse Metrics
- `claims_response_format_selected_total{provider,model,mode,response_format_type}`
- `claims_output_parse_events_total{provider,model,mode,parse_mode,outcome,reason}`
- `claims_fallback_total{provider,model,mode,reason}`

## Rebuild Metrics
- `claims_rebuild_queue_size`
- `claims_rebuild_processed_total`
- `claims_rebuild_failed_total`
- `claims_rebuild_job_duration_seconds`
- `claims_rebuild_worker_heartbeat_timestamp`

## Review Metrics
- `claims_review_queue_size`
- `claims_review_processed_total`
- `claims_review_latency_seconds`

## Alert Delivery Metrics
- `claims_alert_webhook_delivered_total{status}`
- `claims_alert_webhook_failed_total{reason}`
- `claims_alert_webhook_latency_seconds{status}`
- `claims_alert_email_delivered_total{status}`
- `claims_alert_email_failed_total{reason}`
- `claims_alert_email_latency_seconds{status}`

## Review Notification Metrics
- `claims_review_webhook_delivered_total{status}`
- `claims_review_webhook_failed_total{reason}`
- `claims_review_webhook_latency_seconds{status}`
- `claims_review_email_delivered_total{status}`
- `claims_review_email_failed_total{reason}`
- `claims_review_email_latency_seconds{status}`

## Post-Check Metrics
- `rag_total_claims_checked_total`
- `rag_unsupported_claims_total`

## Dashboards & Alerts
- Grafana dashboard JSON: `Docs/Monitoring/claims_grafana_dashboard.json`
- Prometheus alert rules: `Docs/Monitoring/claims_alerts_prometheus.yaml`
- Claims alerts runbook: `Docs/Operations/Claims_Alerts_Runbook.md`
