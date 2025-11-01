# Claims Monitoring & Observability PRD

## 1. Background
- Claims extraction, verification, and rebuild workflows already emit logs and basic metrics (unsupported ratio, rebuild stats). However, observability is fragmented and largely manual.
- As reviewer workflow and claim accuracy initiatives grow, teams need richer telemetry to detect regressions, understand provider behavior, and manage operational load.
- Current monitoring gaps:
  - Provider-level performance (latency, error rate, cost) is opaque.
  - Unsupported claim spikes are only visible after downstream complaints.
  - Rebuild services run in the background without consolidated dashboards.
  - Data quality trends (review approvals, stale claims) aren’t surfaced proactively.

## 2. Problem Statement
Operators lack actionable visibility into claim extraction health. Without granular metrics, alerts, and dashboards:
- Incidents are detected late (e.g., provider outages causing unsupported claims).
- Cost/performance tuning is guesswork.
- Background tasks (rebuild, review queue) can silently fail.
- Product teams cannot quantify improvements from reviewer workflow or extractor tuning.

## 3. Goals & Success Criteria
1. Instrument per-provider metrics to understand latency, error, throughput, and estimated cost.
2. Automatically alert stakeholders when unsupported claim ratios exceed thresholds.
3. Provide dashboards to monitor rebuild queues, worker heartbeat, and data quality signals.
4. Support proactive decision-making through analytics on claims per media, review outcomes, and stale items.

**Success Metrics**
- 100% of extractor/verifier providers reporting Prometheus metrics (latency/error/cost) within 90 days.
- Alerts triggered within <5 minutes when unsupported ratio exceeds configured thresholds.
- Rebuild scheduler heartbeat monitored with <1% false positives; incidents logged with MTTR < 30 minutes.
- Data quality dashboards adopted by research team (weekly usage).
- Reduction in unsupported claim incidents by 30% quarter-over-quarter due to early warning.

## 4. Out of Scope (v1)
- Automated remediation (e.g., auto-switching providers) beyond alerts.
- Full cost accounting pipeline; cost estimates are coarse projections.
- SLA contractual reporting (focus is internal operations).
- Real-time streaming dashboards (update cadence can be 1-5 minutes).

## 5. Personas & Use Cases
- **Platform Operator / SRE**: Monitors system-wide health, responds to alerts.
  - Needs per-provider performance graphs, alert routing, rebuild service visibility.
- **Claims Lead / Research Program Manager**: Tracks data quality and reviewer throughput.
  - Needs dashboards for approval rates, unsupported trends, stale claims.
- **ML Engineer / Extractor Owner**: Analyzes provider behavior and cost to tune models.
  - Needs latency/error histograms, cost estimates, delta reports after changes.
- **Product Manager**: Evaluates feature impact via trend reports and dashboards.
  - Needs aggregated KPIs that can be shared in reviews.

## 6. Functional Requirements

### 6.1 Per-Provider Metrics
- Extend metrics pipeline to emit Prometheus counters/gauges per extractor and verifier:
  - `claims_provider_requests_total{provider, model, mode}`
  - `claims_provider_latency_seconds{provider, model}` histogram.
  - `claims_provider_errors_total{provider, model, reason}`.
  - `claims_provider_estimated_cost_usd_total{provider, model}` (rough estimate, configurable multipliers).
  - `claims_turnaround_seconds{stage}` histogram capturing ingestion → review → approval timelines.
- Instrument both ingestion-time extractors and answer-time verifiers.
- Include tags for `workspace_id` or `client_id` when multi-tenant metrics required.
- Provide `mcp` metrics integration if available.
- Document metric names in `Docs/Monitoring`.

### 6.2 Unsupported Ratio Alerts
- Define per-workspace thresholds for unsupported vs. total claims.
  - Config via `claims_alerts.yaml` or admin API (`/api/v1/claims/alerts`).
- Alert logic:
  - Evaluate ratio over sliding window (e.g., last 15 minutes) and baseline (last 24 hours).
  - Trigger when ratio > threshold or drift > X%.
- Notification channels:
  - Slack webhook integration (configurable channel, severity).
  - Generic webhooks for automation (payload includes workspace, current ratio, baseline, top sources).
  - Optional email digest.
- Alert suppression/exponential backoff to avoid flapping.
- Provide dashboard card showing current ratio vs. threshold.

### 6.3 Rebuild Scheduler & Worker Observability
- Metrics:
  - `claims_rebuild_queue_size`, `claims_rebuild_processed_total`, `claims_rebuild_failed_total`.
  - `claims_rebuild_job_duration_seconds` histogram.
  - `claims_rebuild_worker_heartbeat_timestamp` gauge (UNIX epoch).
- Health checks:
  - Add `/api/v1/claims/rebuild/health` returning heartbeat age, queue depth, last failure.
  - Integrate with existing health endpoint for readiness/liveness.
- Grafana dashboard panels:
  - Queue depth over time.
  - Success vs. failure counts.
  - Worker heartbeat with alert when stale greater than threshold.
- Logging:
  - Structured ENRICHED logs for job start/stop, failure reasons, retry attempts.

### 6.4 Data Quality Dashboards
- Aggregate metrics:
  - Claims per media (mean, P95), broken down by source/provider.
  - Reviewer approval rate, average review latency, backlog size.
  - Stale claims age distribution (time since extraction vs. review).
  - Unsupported ratio trends, segmented by extractor/verifier mode.
  - Source metadata overlays (language, ingestion mode).
- Tools:
  - Grafana dashboards with pre-built panels.
  - Optional CSV export for analytics teams (`/api/v1/claims/analytics/export`).
- Derived metrics:
  - `claims_hotspot_index` scoring media/source combos with high unsupported or flagged rates.
- UI integration:
  - Provide summary cards in admin dashboard linking to Grafana panels.

### 6.5 Configurability
- Settings in config (`config.txt` / ENV):
  - `CLAIMS_MONITORING_ENABLED`.
  - `CLAIMS_PROVIDER_COST_MULTIPLIERS`.
  - `CLAIMS_ALERT_THRESHOLD_DEFAULT`, per-workspace overrides.
  - `CLAIMS_REBUILD_MAX_QUEUE_ALERT`, `CLAIMS_REBUILD_HEARTBEAT_WARN_SEC`.
- Admin API for runtime updates (`PATCH /api/v1/claims/monitoring/config`).

## 7. Non-Functional Requirements
- **Performance**: Metric emission overhead <5% CPU; avoid blocking critical paths (async counters).
- **Reliability**: Metrics resilient to provider errors; no data loss on exporter failures (buffered).
- **Security**: Redact sensitive info (API keys) from metrics; per-tenant data isolation.
- **Scalability**: Support hundreds of workspaces/providers; metrics cardinality managed (bounded label sets).
- **Maintainability**: Work with existing Prometheus/Grafana stack; modular code for new providers.

## 8. Data Model & Storage
- Minimal schema changes; store alert configs per workspace (e.g., `ClaimsMonitoringConfig` table).
- Persist alert events into `ClaimsMonitoringEvents` for audit/history.
- Optionally store aggregated metrics in timeseries DB (Prometheus) + long-term export to data lake.

## 9. APIs & Interfaces
| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/v1/claims/alerts` | GET/POST/PATCH/DELETE | Manage workspace thresholds & channels | claims_admin |
| `/api/v1/claims/rebuild/health` | GET | Worker heartbeat and queue stats | claims_admin/SRE |
| `/api/v1/claims/monitoring/config` | GET/PATCH | View/update monitoring settings | claims_admin |
| `/api/v1/claims/analytics/export` | POST | Export data quality metrics (CSV/JSON) | claims_admin |

## 10. Dashboard & Alerting Assets
- Grafana dashboards:
  - Claims Provider Performance.
  - Unsupported Ratio & Alerts.
  - Rebuild Scheduler Health.
  - Data Quality Overview.
- Alertmanager rules for:
  - Provider latency/error anomalies.
  - Unsupported ratio breaches.
  - Rebuild heartbeat missing.
- Slack/webhook templates with context and remediation guidance.

## 11. Implementation Phases
1. **Phase 1**: Instrument metrics (provider counters, rebuild queue), create health endpoint, baseline Grafana panels.
2. **Phase 2**: Unsupported ratio alerting (threshold config, notifications), provider cost estimates.
3. **Phase 3**: Data quality dashboards, analytics export.
4. **Phase 4**: Advanced analytics (hotspot index), integration with reviewer metrics.

## 12. Risks & Mitigations
- **High metric cardinality**: Limit label combinations; aggregate rare providers; use sampling if needed.
- **Alert fatigue**: Implement deduplication, adjustable thresholds, multi-level severity.
- **Data accuracy**: Cost estimation depends on provider pricing; maintain calibrations.
- **Operational overhead**: Provide scripted dashboard/alert deployment; document runbooks.

## 13. Dependencies
- Prometheus/Grafana stack accessible in deployment environments.
- Notification infrastructure (Slack webhook, email service).
- Reviewer workflow PRD for data quality metrics integration.
- Config management for new settings.

## 14. Roadmap & Open Questions
- Should cost metrics integrate with billing system? (Future item.)
- Do tenants require self-service dashboards or ops-managed only?
- How to handle private deployments without Prometheus? Consider fallback logging or stats.
- Should alerts support escalation policies (pager duty integration)?

## 15. References
- Claims Module PRD (`Docs/Product/Claims_Module_PRD.md`).
- Reviewer Workflow PRD (`Docs/Product/Claims_Reviewer_Workflow_PRD.md`).
- Metrics subsystem (`tldw_Server_API/app/core/Metrics`).
- Rebuild service (`tldw_Server_API/app/services/claims_rebuild_service.py`).
