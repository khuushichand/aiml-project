# Monitoring Dashboards

This directory contains Grafana dashboards and monitoring docs for tldw_server.

Dashboards (JSON):
- `Grafana_LLM_Cost_Top_Providers.json` - Cost and token rates by provider/model
- `Grafana_LLM_Daily_Spend.json` - Daily cost/tokens with top-N breakdowns
- `app-observability-dashboard.json` - HTTP, RAG cache, LLM, chat streaming
- `mcp-dashboard.json` - MCP Unified: requests, latency, rate limits, errors
- `web-scraping-dashboard.json` - Scraping throughput, success ratio, latency
- `security-dashboard.json` - HTTP status, p95 latency, headers, quotas, uploads
- `rag-reranker-dashboard.json` - RAG reranker guardrails (timeouts, exceptions, budget, docs scored)
- `rag-quality-dashboard.json` - Nightly eval faithfulness/coverage trends (dataset-labeled)
- `streaming-dashboard.json` - Streaming observability (SSE/WS): latencies, idle timeouts, ping failures, SSE queue depth
- `Grafana_Streaming_Basics.json` - Streaming basics + HTTP client metrics:
  - Egress denials (5m) by reason: `http_client_egress_denials_total`
  - Retries (5m) by reason: `http_client_retries_total`
  - Panels are pre-wired for a Prometheus datasource UID `prometheus`.
  - Persona WS series appear with labels `{component: persona, endpoint: persona_ws, transport: ws}` and show up in the WS panels (send latency, pings, idle timeouts).

Exemplars
- Redacted payload exemplars for debugging failed adaptive checks are written to `Databases/observability/rag_payload_exemplars.jsonl` by default.
- Control with env: `RAG_PAYLOAD_EXEMPLAR_SAMPLING` (0..1), `RAG_PAYLOAD_EXEMPLAR_PATH`.
- See `Exemplars/README.md` and `exemplar-sink-sample.yml` for ingestion patterns.

Notes
- Dashboards assume a Prometheus datasource with UID `prometheus`.
- Default refresh is 30s and rate windows use `$__rate_interval`.
- See `Metrics_Cheatsheet.md` for metrics catalog, PromQL, and provisioning.
- Environment variables reference (telemetry, Prometheus/Grafana): `../../Env_Vars.md`

Tracing quick check (OTLP)
- Enable tracing exporters:
  - `export ENABLE_TRACING=true`
  - `export OTEL_TRACES_EXPORTER=console,otlp`
  - `export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`
  - Optional: `export OTEL_EXPORTER_OTLP_INSECURE=true`
- Run the server and perform a request that triggers outbound HTTP (e.g., RAG provider call).
- Verify traces in your collector/Jaeger; outbound calls use span name `http.client` with attributes `http.method`, `net.host.name`, `url.full`, and `http.status_code`.
- Providers that support `traceparent` will receive the header injected by the HTTP client.

Provisioning
- Example provisioning files: `Samples/Grafana/provisioning/*`
- Map this directory into `/var/lib/grafana/dashboards` to auto-load all dashboards.

Prometheus Scrape
- See `prometheus-scrape-sample.yml` for a ready-to-use scrape config that targets `http://<tldw_host>:8000/metrics`.

Nightly Quality Evaluations
- Enable scheduler: `RAG_QUALITY_EVAL_ENABLED=true` (interval via `RAG_QUALITY_EVAL_INTERVAL_SEC`).
- Dataset: `Docs/Deployment/Monitoring/Evals/nightly_rag_eval.jsonl` (override with `RAG_QUALITY_EVAL_DATASET`).
- Metrics: `rag_eval_faithfulness_score{dataset=...}`, `rag_eval_coverage_score{dataset=...}`, `rag_eval_last_run_timestamp{dataset=...}`.

## Reverse Proxy Heartbeats (SSE)

When running behind reverse proxies/CDNs (NGINX, Caddy, Cloudflare), comment-based SSE heartbeats (`":"`) can be buffered and delay delivery. For more reliable flushing:

- Prefer data-mode heartbeats in the server:
  - `export STREAM_HEARTBEAT_MODE=data`
  - Optionally shorten for dev/tests: `export STREAM_HEARTBEAT_INTERVAL_S=5`
- Disable proxy buffering on SSE routes:
  - NGINX location example:
    ```nginx
    location /api/ {
      proxy_buffering off;
      proxy_http_version 1.1;
      chunked_transfer_encoding on;
      proxy_set_header Connection "";  # HTTP/2 ignores Connection; harmless in HTTP/1.1
    }
    ```
- For HTTP/2, do not rely on `Connection: keep-alive`; instead ensure buffering is off and the upstream emits periodic data heartbeats.
