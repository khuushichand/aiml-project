# Grafana Provisioning (Samples)

This folder contains provisioning examples for Grafana so it can auto-load a Prometheus datasource and dashboards at startup.

- Provisioning files:
  - `provisioning/datasources/prometheus.yml`
  - `provisioning/dashboards/dashboards.yml`

Dashboards to load (copy into `/var/lib/grafana/dashboards` in your Grafana container/host):
- `Docs/Deployment/Monitoring/Grafana_LLM_Cost_Top_Providers.json`
- `Docs/Deployment/Monitoring/Grafana_LLM_Daily_Spend.json`
- `Docs/Deployment/Monitoring/overview.json`
- `Docs/Deployment/Monitoring/app-observability-dashboard.json`
- `Docs/Deployment/Monitoring/mcp-dashboard.json`
- `Docs/Deployment/Monitoring/web-scraping-dashboard.json`

Docker Compose snippet:

```yaml
services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
    volumes:
      - ./Samples/Grafana/provisioning/datasources:/etc/grafana/provisioning/datasources
      - ./Samples/Grafana/provisioning/dashboards:/etc/grafana/provisioning/dashboards
      - ./Docs/Deployment/Monitoring:/var/lib/grafana/dashboards
```

Notes
- The datasource UID is set to `prometheus` in dashboards; change the UID if your datasource differs.
- The dashboards are read directly from `Docs/Deployment/Monitoring` in the example; adapt the mounted path as needed.
 - Annotations: a sample Prometheus-backed Deploys annotation is provisioned from `Samples/Grafana/provisioning/annotations/deploys.yml`. Push a `tldw_deploy_info{version,git_sha}` metric at deploy time to see markers on dashboards.
