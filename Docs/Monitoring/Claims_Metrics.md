# Claims Metrics

## Provider Metrics
- `claims_provider_requests_total{provider,model,mode}`
- `claims_provider_latency_seconds{provider,model}`
- `claims_provider_errors_total{provider,model,reason}`
- `claims_provider_estimated_cost_usd_total{provider,model}`

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

## Post-Check Metrics
- `rag_total_claims_checked_total`
- `rag_unsupported_claims_total`
