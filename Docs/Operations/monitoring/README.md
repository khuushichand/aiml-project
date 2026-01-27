# Monitoring (Prometheus + Alertmanager)

This directory contains Prometheus alert rules and an Alertmanager configuration for tldw_server.

## Files

- `prometheus_alerts_tldw.yml` — Prometheus rules for HTTP 5xx error spikes
- `alertmanager_email_webhook.yml` — Alertmanager routes for email + webhook delivery

## Usage (docker-compose.monitoring.yml)

The monitoring compose file wires Prometheus + Alertmanager and mounts these configs:

```bash
# from repo root
cd Dockerfiles/Monitoring

# start Prometheus + Alertmanager + Grafana
docker compose -f docker-compose.monitoring.yml up -d
```

Prometheus scrapes tldw_server at:

- `http://host.docker.internal:8000/api/v1/metrics/text`

Alert rules are loaded from:

- `/etc/prometheus/alerts/tldw_alerts.yml`

Alertmanager listens on:

- `http://localhost:9093`

## Configure email/webhook alerts

Edit `Docs/Operations/monitoring/alertmanager_email_webhook.yml`:

- `email_configs`: set `to`, `from`, `smarthost`, `auth_username`, `auth_password`
- `webhook_configs`: set `url` to your alert endpoint

Example (replace values):

```yaml
receivers:
  - name: tldw-alerts
    email_configs:
      - to: "alerts@yourdomain.com"
        from: "alertmanager@yourdomain.com"
        smarthost: "smtp.yourdomain.com:587"
        auth_username: "alertmanager@yourdomain.com"
        auth_password: "REPLACE_ME"
        require_tls: true
        send_resolved: true
    webhook_configs:
      - url: "https://your-alert-endpoint.example.com/alertmanager"
        send_resolved: true
```

## Notes

- Ensure your tldw_server instance is reachable from the Prometheus container.
- If you’re not using Docker Desktop, replace `host.docker.internal` with the actual host IP.
- You can add more rules to `prometheus_alerts_tldw.yml` as needed.
