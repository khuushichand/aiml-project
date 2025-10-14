# Grafana Alerting

This folder contains sample Grafana managed alert rules (YAML) and guidance. Mount this directory into Grafana at `/etc/grafana/provisioning/alerting` to auto‑load rules on startup.

How to enable
- In Docker Compose, add a volume: `./Docs/Deployment/Monitoring/Alerts:/etc/grafana/provisioning/alerting`
- Ensure your Prometheus datasource UID is `prometheus` (rules reference it).

Included files
- `app-alerts.yml` – App/API alerts (HTTP 5xx ratio, high p95 latency)
- `mcp-alerts.yml` – MCP Unified alerts (p95 latency, rate limit spikes)

Notes
- The YAML uses Grafana’s unified alerting provisioning (apiVersion: 1).
- Adjust thresholds, folders, and intervals to match your environment.
- If you don’t see rules, check Grafana logs for provisioning errors.

Recommended PromQL (examples)
- HTTP 5xx ratio (5m): `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`
- HTTP p95 per endpoint: `histogram_quantile(0.95, sum by (le,endpoint) (rate(http_request_duration_seconds_bucket[5m])))`
- MCP p95 per method: `histogram_quantile(0.95, sum(rate(mcp_request_duration_seconds_bucket[5m])) by (le, method))`
- RAG cache hit rate: `sum(rate(rag_cache_hits_total[5m])) / (sum(rate(rag_cache_hits_total[5m])) + sum(rate(rag_cache_misses_total[5m])))`
