# Watchlists Telemetry & Alerting (Foundational) Design (2026-02-23)

## Scope

Implement the first operational telemetry workstream for Watchlists with these fixed decisions:

1. Reuse the existing backend metrics module (`metrics_manager.py`) rather than creating a parallel telemetry system.
2. Hybrid signal model:
   - frontend pushes setup milestone events,
   - backend derives run/output success from DB truth.
3. Store setup telemetry as user-scoped events.
4. RC report reads live backend APIs (not direct DB access).
5. Execution cadence: `release/**` and `rc/**` plus `workflow_dispatch`.
6. Threshold policy: reporting-only in this phase (no threshold-based workflow failure).

## Existing Surfaces to Reuse

- Metrics registry:
  - `tldw_Server_API/app/core/Metrics/metrics_manager.py`
- Metrics API:
  - `tldw_Server_API/app/api/v1/endpoints/metrics.py`
- Watchlists telemetry API pattern (existing IA experiment):
  - `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
  - `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py`
  - `tldw_Server_API/app/core/DB_Management/Watchlists_DB.py`
- Frontend onboarding telemetry utility:
  - `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`

## Proposed Architecture

### 1) Backend Telemetry Ingest + Summary API

Add onboarding telemetry endpoints under Watchlists API:

- `POST /api/v1/watchlists/telemetry/onboarding`
  - ingests user-scoped setup milestone events
- `GET /api/v1/watchlists/telemetry/onboarding/summary`
  - summarizes setup event funnel and setup timing metrics over a time window
- `GET /api/v1/watchlists/telemetry/rc-summary`
  - returns a unified RC telemetry payload combining:
    - onboarding summary (event-driven),
    - backend-derived UC2 run/output success,
    - IA experiment summary,
    - baseline comparison blocks for report generation.

### 2) Hybrid Data Model

New DB table in watchlists DB management:

- `watchlist_onboarding_events`
  - `id`
  - `user_id`
  - `session_id`
  - `event_type`
  - `event_at`
  - `details_json`
  - `created_at`

Model rules:

- Setup milestones come from frontend POST events.
- First run/output success in RC summary is derived from backend runs/outputs records for the same users/time window, not trusted from frontend claims.
- Summary endpoint computes rates/timings required by monitoring policy:
  - setup completion rate
  - first run success rate
  - first output success rate
  - median seconds to setup completion
  - median seconds to first output success

### 3) Existing Metrics Module Integration

Register telemetry operational counters/histograms in existing registry:

- onboarding ingest request totals (`accepted` / `rejected` / `error`)
- onboarding summary request totals and duration
- RC summary request totals and duration

All metrics are emitted through existing metrics endpoints (`/api/v1/metrics/json` and `/api/v1/metrics/text`).

### 4) Frontend Integration

Update onboarding telemetry utility to best-effort post milestone events:

- utility remains non-blocking and resilient (failures do not affect onboarding UX).
- API client functions added in `apps/packages/ui/src/services/watchlists.ts`.
- payloads and responses typed in `apps/packages/ui/src/types/watchlists.ts`.

### 5) RC Reporting Workflow

Add dedicated reporting workflow:

- `.github/workflows/ui-watchlists-telemetry-rc-report.yml`
- triggers:
  - `push` to `release/**` and `rc/**`
  - `workflow_dispatch`
- starts backend in CI test mode, reads live APIs, evaluates thresholds, and writes markdown report to `$GITHUB_STEP_SUMMARY`.
- reporting-only: threshold breaches are surfaced in summary but do not fail the workflow.
- infrastructure failures (server startup/API fetch/script crash) still fail the workflow.

## Threshold Evaluation Contract (Foundational)

Use current monitoring-plan thresholds as report checks:

- setup completion drop >= 10pp (vs baseline)
- first output success drop >= 10pp (vs baseline)
- median first-output timing regression >= 25% (vs baseline)
- UC2 first output success drop >= 10pp (vs baseline)

Because this phase does not store RC-to-RC state, “2 consecutive RCs” conditions are labeled as:

- `potential_breach` (current run indicates risk),
- with note that consecutive confirmation requires next RC run.

## API Contract Outline

### POST `/watchlists/telemetry/onboarding`

Request fields (initial):

- `session_id`
- `event_type`
- `event_at` (ISO UTC)
- `details` (JSON object, optional)

Response:

- `accepted: boolean`
- optional diagnostic code on reject.

### GET `/watchlists/telemetry/onboarding/summary`

Query:

- `since`, `until` (optional ISO UTC)

Response:

- counters
- rates
- timings
- user/session counts

### GET `/watchlists/telemetry/rc-summary`

Query:

- `since`, `until` (optional)

Response:

- onboarding summary block
- UC2 backend-derived success block
- IA summary block
- baseline/delta block

## Failure Handling

1. Frontend event POST failures: swallow and continue local telemetry behavior.
2. Ingest validation failures: reject event cleanly, increment rejection metric.
3. Summary derivation errors: return explicit API error and increment error counters.
4. RC report script API fetch failures: mark workflow failed (operational failure).

## Non-Goals (Phase Boundary)

1. No automatic issue/ticket creation.
2. No dashboard provisioning/seed automation.
3. No hard-fail threshold enforcement yet.
4. No cross-product telemetry consolidation outside Watchlists.

## Validation Strategy

1. Backend unit/integration tests for ingest, summary, and RC summary routes.
2. Frontend utility tests for non-blocking event posting behavior.
3. RC report script tests for threshold evaluation and markdown output.
4. Security check (Bandit) over new reporting scripts and touched telemetry helper code.

## Rollout

1. Merge with reporting-only behavior.
2. Run on first RC cycle and validate summary readability and data correctness.
3. Use runbook observations to prepare Phase 2 (repeat-breach escalation and optional hard-fail policy).
