# Monitoring Dashboards

This directory contains Grafana dashboards and monitoring docs for tldw_server.

Dashboards (JSON):
- `Grafana_LLM_Cost_Top_Providers.json` – Cost and token rates by provider/model
- `Grafana_LLM_Daily_Spend.json` – Daily cost/tokens with top-N breakdowns
- `app-observability-dashboard.json` – HTTP, RAG cache, LLM, chat streaming
- `mcp-dashboard.json` – MCP Unified: requests, latency, rate limits, errors
- `web-scraping-dashboard.json` – Scraping throughput, success ratio, latency
- `security-dashboard.json` – HTTP status, p95 latency, headers, quotas, uploads
- `rag-reranker-dashboard.json` – RAG reranker guardrails (timeouts, exceptions, budget, docs scored)

Notes
- Dashboards assume a Prometheus datasource with UID `prometheus`.
- Default refresh is 30s and rate windows use `$__rate_interval`.
- See `Metrics_Cheatsheet.md` for metrics catalog, PromQL, and provisioning.
- Environment variables reference (telemetry, Prometheus/Grafana): `../../Env_Vars.md`

Provisioning
- Example provisioning files: `Samples/Grafana/provisioning/*`
- Map this directory into `/var/lib/grafana/dashboards` to auto‑load all dashboards.

Prometheus Scrape
- See `prometheus-scrape-sample.yml` for a ready-to-use scrape config that targets `http://<tldw_host>:8000/metrics`.
