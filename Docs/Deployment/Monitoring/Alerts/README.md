# Grafana Alerting

This folder contains sample Grafana managed alert rules (YAML) and guidance. Mount this directory into Grafana at `/etc/grafana/provisioning/alerting` to auto‑load rules on startup.

How to enable
- In Docker Compose, add a volume: `./Docs/Deployment/Monitoring/Alerts:/etc/grafana/provisioning/alerting`
- Ensure your Prometheus datasource UID is `prometheus` (rules reference it).

Included files
- `app-alerts.yml` – App/API alerts (HTTP 5xx ratio, high p95 latency)
- `mcp-alerts.yml` – MCP Unified alerts (p95 latency, rate limit spikes)
- `rag-alerts.yml` – RAG reranker alerts (LLM timeouts, exceptions, budget exhaustions)
- `rag-slo-alerts.yml` – RAG SLOs (p95 latency, faithfulness ratio, burn-rate)

Notes
- The YAML uses Grafana’s unified alerting provisioning (apiVersion: 1).
- Adjust thresholds, folders, and intervals to match your environment.
- If you don’t see rules, check Grafana logs for provisioning errors.

Recommended PromQL (examples)
- HTTP 5xx ratio (5m): `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`
- HTTP p95 per endpoint: `histogram_quantile(0.95, sum by (le,endpoint) (rate(http_request_duration_seconds_bucket[5m])))`
- MCP p95 per method: `histogram_quantile(0.95, sum(rate(mcp_request_duration_seconds_bucket[5m])) by (le, method))`
- RAG cache hit rate: `sum(rate(rag_cache_hits_total[5m])) / (sum(rate(rag_cache_hits_total[5m])) + sum(rate(rag_cache_misses_total[5m])))`
- RAG reranker timeouts: `sum(rate(rag_reranker_llm_timeouts_total[5m]))`
- RAG reranker budget exhaustions: `sum(rate(rag_reranker_llm_budget_exhausted_total[5m]))`
- RAG reranker exceptions: `sum(rate(rag_reranker_llm_exceptions_total[5m]))`

## AuthNZ Security Alerts

The AuthNZ scheduler now emits structured security alerts (auth failure spikes, rate-limit storms). To deliver them:

1. Provide settings via environment or `.env` (preferred):
   ```
   SECURITY_ALERTS_ENABLED=true
   SECURITY_ALERT_MIN_SEVERITY=high
   SECURITY_ALERT_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
   # Optional headers as JSON (e.g., for custom auth):
   SECURITY_ALERT_WEBHOOK_HEADERS={"Authorization":"Bearer ${SLACK_TOKEN}"}
   ```
2. For email delivery, also set:
   ```
   SECURITY_ALERT_EMAIL_TO=secops@example.com
   SECURITY_ALERT_EMAIL_FROM=authnz-alerts@example.com
   SECURITY_ALERT_SMTP_HOST=smtp.example.com
   SECURITY_ALERT_SMTP_PORT=587
   SECURITY_ALERT_SMTP_STARTTLS=true
   SECURITY_ALERT_SMTP_USERNAME=smtp-user
   SECURITY_ALERT_SMTP_PASSWORD=${SMTP_PASSWORD}
   ```
3. (Optional) Override the JSONL sink path (defaults to `Databases/security_alerts.log`):
   ```
   SECURITY_ALERT_FILE_PATH=/var/log/tldw/security_alerts.log
   ```

4. (Optional) Tune per-sink severity floors so noisier channels stay quiet:
   ```
   SECURITY_ALERT_WEBHOOK_MIN_SEVERITY=medium
   SECURITY_ALERT_EMAIL_MIN_SEVERITY=critical
   SECURITY_ALERT_FILE_MIN_SEVERITY=low
   ```

5. (Optional) Extend the retry backoff after delivery failures (seconds):
   ```
   SECURITY_ALERT_BACKOFF_SECONDS=45
   ```

 All values can also be supplied via `[AuthNZ]` in `Config_Files/config.txt` (see `Env_Vars.md` for keys). The dispatcher writes to the file sink even when webhooks or SMTP fail, so operators can tail the log during setup.

## Runbook: RAG Reranker Alerts

When RAG reranker alerts fire, use this quick triage:

- Timeout spikes (rag_reranker_llm_timeouts_total)
  - Check provider status/latency (OpenAI/Anthropic/etc.).
  - Verify network egress and DNS. Inspect app logs around reranking calls.
  - Consider lowering `top_k` or switching to `flashrank`/`cross_encoder` temporarily.
  - Tune guardrails if appropriate: `RAG_LLM_RERANK_TIMEOUT_SEC`, `RAG_LLM_RERANK_TOTAL_BUDGET_SEC`.

- Budget exhausted (rag_reranker_llm_budget_exhausted_total)
  - Indicates many docs or slow LLM scoring. Confirm `RAG_LLM_RERANK_MAX_DOCS` and `top_k` are reasonable.
  - Prefer hybrid or FlashRank to reduce LLM reliance. Validate vector store responsiveness.

- Exceptions (rag_reranker_llm_exceptions_total)
  - Inspect server logs for stack traces in reranker; check provider API errors and quotas.
  - Validate credentials and model IDs in config/env.

- Docs scored near zero
  - Confirm there is active RAG traffic. If traffic exists, check that reranking is enabled and strategy isn’t `none`.
  - Ensure guardrails aren’t overly strict (e.g., `RAG_LLM_RERANK_MAX_DOCS=0`).
  - If using a custom LLM reranker provider, validate model availability.

Dashboards
- Import `Docs/Deployment/Monitoring/rag-reranker-dashboard.json` for quick visibility into reranker behavior.
