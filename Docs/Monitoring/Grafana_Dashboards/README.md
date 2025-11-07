Grafana Dashboards for tldw_server

Overview
- This folder contains an example Grafana dashboard JSON for visualizing the LLM Gateway metrics exposed at `/metrics`.
- The dashboard targets the internal Prometheus-style metrics emitted by `tldw_Server_API.app.core.Metrics.metrics_manager` and the HTTP middleware.

Prometheus Scrape (example)
Add a scrape job pointing to your server (adjust host/port):

  scrape_configs:
    - job_name: 'tldw_server'
      metrics_path: /metrics
      static_configs:
        - targets: ['127.0.0.1:8000']

Importing the Dashboard
1) In Grafana: Dashboards -> New -> Import.
2) Upload `llm_gateway_dashboard.json`.
3) Set the Prometheus datasource when prompted.

Variables
- DS_PROMETHEUS: Prometheus datasource selector (choose your Prometheus instance).
- endpoint: HTTP endpoint label (defaults to `/api/v1/chat/completions`).
- method: HTTP method label (defaults to `POST`).
- provider: LLM provider label (e.g., `openai`).
- model: LLM model label (e.g., `gpt-4o-mini`).

Notes
- If you run the server in mock mode for benchmarking (`CHAT_FORCE_MOCK=1`), the upstream LLM panels still work since metrics are recorded by the gateway (decorators and usage tracker).
- The HTTP latency panels are driven by `http_request_duration_seconds_bucket`. LLM latency panels are driven by `llm_request_duration_seconds_bucket`.

