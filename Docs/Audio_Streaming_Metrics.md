Audio Streaming Metrics & Monitoring
===================================

Overview
--------
The audio streaming subsystem exports lightweight metrics via the built-in registry and the `/metrics` HTTP endpoint suitable for Prometheus scraping. These metrics capture live usage and quota violations:

- Gauges (canonical)
  - `audio_streaming_active` labels: `user_id`
  - `audio_jobs_active` labels: `user_id`
- Counters (canonical)
  - `audio_quota_violations_total` labels: `type` (one of `daily_minutes`, `concurrent_streams`, `concurrent_jobs`)

Backward-compatibility
- Dot-name aliases are also emitted for compatibility: `audio.streaming.active`, `audio.jobs.active`, `audio.quota_violations_total`.

Notes
- Metric names include dots (`.`). Prometheus selectors can reference these using a label match on `__name__`.
- If you prefer underscore metric names, consider recording rules or a sidecar to rename metrics.

Endpoints
---------
- Prometheus text: `GET /metrics`
- JSON snapshot: `GET /api/v1/metrics`
- Status/probe for streaming variants: `GET /api/v1/audio/stream/status`

Prometheus Scrape Example
-------------------------

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'tldw_server'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['localhost:8000']
```

PromQL Examples
---------------

# Current concurrent streams (all users)
sum({__name__="audio_streaming_active"})

# Concurrent streams by user
sum by(user_id) ({__name__="audio_streaming_active"})

# Current active jobs (all users)
sum({__name__="audio_jobs_active"})

# Quota violations rate (per minute) by type
sum by(type) (rate({__name__="audio_quota_violations_total"}[5m])) * 60

# Alert idea: sustained quota violations for daily minutes
sum(rate({__name__="audio_quota_violations_total", type="daily_minutes"}[15m])) > 0

Grafana Panel Ideas
-------------------
- Stat: “Active Streams” → `sum({__name__="audio_streaming_active"})`
- Time series: “Active Streams by User” → `sum by(user_id) ({__name__="audio_streaming_active"})`
- Bar gauge: “Quota Violations (5m)” → `sum by(type) (rate({__name__="audio_quota_violations_total"}[5m]))`
- Single stat: “Active Jobs” → `sum({__name__="audio_jobs_active"})`

OpenTelemetry (Optional)
------------------------
- The project’s metrics manager coexists with OTEL; if you enable OTLP export elsewhere, keep `/metrics` for Prometheus scraping or bridge to Grafana Agent/OTEL Collector. No extra setup is required for audio metrics beyond running the server.

Operational Tips
----------------
- Redis is optional but recommended for accurate concurrent stream counting across processes and TTL-based cleanup on abrupt disconnects. See `[Audio-Quota].stream_ttl_seconds` in config and `AUDIO_STREAM_TTL_SECONDS` env.
- Health endpoint `/api/v1/audio/stream/status` is a quick feature probe to confirm variant availability before load testing.
