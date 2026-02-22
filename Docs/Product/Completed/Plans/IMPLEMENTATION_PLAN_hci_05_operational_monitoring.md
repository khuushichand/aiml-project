# Implementation Plan: HCI Review - Operational Monitoring

## Scope

Pages: `app/monitoring/`, `app/jobs/`, `app/incidents/`, `app/logs/`
Finding IDs: `5.1` through `5.10`

## Finding Coverage

- `5.1` (Critical): No custom time range selection for metrics
- `5.2` (Important): Only CPU and Memory shown in metrics chart
- `5.3` (Important): No threshold configuration for alerts
- `5.4` (Important): Alert management limited to acknowledge/dismiss
- `5.5` (Important): Monitoring covers only 4 subsystems
- `5.6` (Nice-to-Have): Jobs page has no job dependency visualization
- `5.7` (Important): Incidents lack assignment and on-call integration
- `5.8` (Important): Logs page lacks regex search
- `5.9` (Nice-to-Have): No log correlation across services
- `5.10` (Nice-to-Have): Incidents have no post-mortem or root cause tracking

## Key Files

- `admin-ui/app/monitoring/page.tsx` -- Metrics chart (CPU/memory, 288 points), health grid (4 subsystems), alerts (ack/dismiss), watchlists, notifications
- `admin-ui/app/jobs/page.tsx` -- Queue stats, job list with filters, job detail modal, SLA policies, stale detection
- `admin-ui/app/incidents/page.tsx` -- Incident CRUD, status/severity management, timeline events
- `admin-ui/app/logs/page.tsx` -- Log search with time range, level, service, query, org/user filters
- `admin-ui/lib/api-client.ts` -- All monitoring/jobs/incidents/logs API methods

## Stage 1: Custom Time Ranges + Expanded Metrics

**Goal**: Let admins view metrics over meaningful time windows and see more than just CPU/memory.
**Success Criteria**:
- Monitoring page has time range selector: 1h, 6h, 24h (default), 7d, 30d, Custom.
- Custom range shows date-time pickers for start/end.
- Selecting a range adjusts data fetch parameters and chart x-axis granularity.
- Metrics chart supports additional series beyond CPU/memory: disk usage, request throughput, active connections, queue depth.
- Series toggleable via legend clicks (show/hide individual metrics).
- Chart uses appropriate y-axis scaling per metric type (% for utilization, count for throughput).
**Tests**:
- Unit test for time range selector state and parameter construction.
- Unit test for chart series toggle logic.
- Unit test for multi-axis chart rendering with mixed metric types.
- Test for date range validation (start < end).
**Status**: Complete

## Stage 2: Alert Thresholds + Enhanced Alert Management

**Goal**: Let admins configure when alerts fire and manage them beyond acknowledge/dismiss.
**Success Criteria**:
- New "Alert Rules" section on monitoring page: define threshold rules per metric (e.g., CPU > 85% for 5m → warning, CPU > 95% for 2m → critical).
- Rule form: metric selector, operator (>, <, ==), threshold value, duration, severity.
- Alert cards add: "Assign to" user dropdown, "Snooze" button (15m, 1h, 4h, 24h options), "Escalate" button.
- Snoozed alerts hidden from active view with "Show snoozed (N)" toggle.
- Alert history view: all alerts including resolved, with timeline of state changes.
**Tests**:
- Unit test for alert rule form validation.
- Unit test for snooze countdown display.
- Unit test for alert assignment dropdown.
- Unit test for alert history timeline rendering.
**Status**: Complete

## Stage 3: Expanded Subsystem Health + Incident Improvements

**Goal**: Monitor all platform subsystems and improve incident management workflows.
**Success Criteria**:
- System Status Panel expanded to 8+ subsystems: API, Database, LLM, RAG, TTS, STT, Embeddings, Cache, Queue.
- Each subsystem card shows: status badge, last-checked timestamp, response time (ms).
- Subsystem health sourced from dedicated health endpoints where available, Prometheus metrics as fallback.
- Incident cards add "Assigned To" field: user selector from admin users list.
- Incident detail adds structured fields: "Root Cause" (text area), "Impact" (text area), "Action Items" (checklist).
- Incident status "resolved" automatically populates resolved_at timestamp.
**Tests**:
- Unit test for expanded health grid rendering with 8+ subsystems.
- Unit test for subsystem response time display.
- Unit test for incident assignment flow.
- Unit test for root cause / action items form on resolved incidents.
**Status**: Complete

## Stage 4: Log Enhancements + Job Dependencies

**Goal**: Make log search more powerful and add job relationship visibility.
**Success Criteria**:
- Logs page search field has "Regex" toggle: when enabled, search input treated as regex pattern.
- Regex toggle shows validation state (valid/invalid regex with error message).
- Request ID column in logs table is clickable: filters all logs to that request_id to show correlated entries across services.
- "View correlated logs" action on log entry context menu.
- Jobs page adds optional dependency view: for jobs with parent/child relationships, show a simple tree or list of related jobs.
- Job detail modal shows "Related Jobs" section if job has parent_id or child jobs.
**Tests**:
- Unit test for regex toggle and validation.
- Unit test for request ID click-to-filter behavior.
- Unit test for job dependency tree rendering.
**Status**: Complete

## Dependencies

- Stage 1 time ranges require the backend `/monitoring/metrics` endpoint to accept `start`/`end`/`granularity` parameters. Verify backend support.
- Stage 2 alert rules may require a new backend endpoint `POST /monitoring/alert-rules` for persistence. Alternatively, alert rules can be stored in watchlists with threshold configuration.
- Stage 3 subsystem health now uses dedicated health endpoints when available and falls back to Prometheus metrics in the frontend when subsystem endpoints are unavailable.
- Stage 4 regex search and request-correlation filtering are implemented client-side; backend regex query support remains an optional enhancement.
