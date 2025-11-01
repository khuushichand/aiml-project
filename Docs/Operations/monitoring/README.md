# Monitoring TLDW Embeddings Orchestrator

This folder contains a ready-to-import Grafana dashboard and basic guidance to scrape Prometheus metrics from both the API process and the worker orchestrator (if you run it as a separate process).

## Prometheus Scrape Setup

The API exposes Prometheus text metrics under `/metrics` (root) and also JSON/text under the API namespace:

- Root: `GET /metrics` (if enabled by your deployment)
- API JSON: `GET /api/v1/metrics/json`
- API text: `GET /api/v1/metrics/text` (Prometheus format)

The embeddings worker orchestrator process (started via `python -m tldw_Server_API.app.core.Embeddings.worker_orchestrator`) runs its own Prometheus exporter via `start_http_server(PORT)` when configured. In the provided compose, it listens on port 9090.

Example `prometheus.yml` snippet to scrape both:

```yaml
scrape_configs:
  # API process (aggregates API metrics;
  # text endpoint can be proxied at /api/v1/metrics/text)
  - job_name: 'tldw-api'
    metrics_path: '/api/v1/metrics/text'
    static_configs:
      - targets: ['api:8000']

  # Embeddings worker orchestrator (separate process)
  - job_name: 'tldw-worker-orchestrator'
    static_configs:
      - targets: ['worker-orchestrator:9090']
```

Notes:
- If you terminate SSL at a reverse proxy, ensure the metrics paths are reachable inside the cluster/VPC.
- For local dev, you can scrape `http://127.0.0.1:8000/api/v1/metrics/text` and `http://127.0.0.1:9090/`.

## Grafana

Import the provided dashboards:

- Embeddings Orchestrator: `monitoring/grafana_embeddings_orchestrator.json`
- Workflows: `monitoring/grafana_workflows.json`
- Service Overview: `monitoring/grafana_service_overview.json`
- Tenant Overview: `monitoring/grafana_tenant_overview.json`
  - Panels:
    - SSE Connections, Disconnects, Summary Failures
    - Queue Depth by queue
    - DLQ Depth by queue
    - Queue Age p95 (10m window; from orchestrator histogram)
    - Stage processed/s and failed/s
    - Stage flags (paused/drain)

In Grafana:
1. Dashboards → New → Import
2. Upload `grafana_embeddings_orchestrator.json`, `grafana_workflows.json`, `grafana_service_overview.json`, or `grafana_tenant_overview.json`
3. For dashboards with variables, set the Prometheus data source and use the top-left dropdowns to filter (Provider / Model / Pipeline / Tenant).

## Alertmanager

An example Alertmanager configuration is provided at `monitoring/alertmanager_example.yml` with Slack and PagerDuty receivers. Replace placeholders with your credentials/integration keys and point your Alertmanager to this file via its `--config.file` or mounted configmap.
3. Select the correct Prometheus data source

SLO alert rules for the embeddings pipeline are provided in `monitoring/alerts/embeddings_slos.yaml` and include:

- Error budget burn (>0.5% failures over 1h)
- Queue age p95 > 2 minutes per queue
- Stage latency p99 > 10 seconds

Add the file to your Prometheus `rule_files` section, for example:

```yaml
rule_files:
  - monitoring/alerts/*.yaml
```

## Metrics Primer

Key embeddings orchestrator metrics exported by the API process:

- `orchestrator_sse_connections` (gauge): active SSE connections to `/api/v1/embeddings/orchestrator/events`
- `orchestrator_sse_disconnects_total` (counter): total disconnect events observed
- `orchestrator_summary_failures_total` (counter): number of summary fallbacks returned when Redis/orchestrator unavailable
- `embedding_queue_age_current_seconds{queue_name}` (gauge): current oldest age per queue measured at time of summary build
- `embedding_stage_flag{stage,flag}` (gauge): stage admin flags (`paused` and `drain`) exposed as 1/0

Worker orchestrator metrics (from `worker_orchestrator.py`):

- `embedding_queue_depth{queue_name}` (gauge)
- `embedding_dlq_queue_depth{queue_name}` (gauge)
- `embedding_queue_age_seconds_bucket` (histogram) - use histogram_quantile for p95
- `embedding_stage_jobs_processed_total{stage}` (counter)
- `embedding_stage_jobs_failed_total{stage}` (counter)

## Troubleshooting

- Zeroed summary (all empty maps) indicates Redis/unavailable orchestrator - the WebUI shows a small fallback badge; alert if sustained.
- If metrics endpoints return 401/403, use admin credentials (single-user API key or admin JWT role).
