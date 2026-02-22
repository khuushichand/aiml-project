# Implementation Plan: HCI Review - Governance & Compliance

## Scope

Pages: `app/security/`, `app/audit/`, `app/usage/`, `app/budgets/`, `app/flags/`
Finding IDs: `6.1` through `6.9`

## Finding Coverage

- `6.1` (Critical): Budget page is read-only with no edit capability
- `6.2` (Critical): No budget alerts or threshold notifications
- `6.3` (Important): Security risk score lacks actionable remediation guidance
- `6.4` (Important): Audit log has no saved searches or alert-on-pattern
- `6.5` (Important): No compliance report generation (SOC2, GDPR)
- `6.6` (Important): Feature flags are on/off only, no percentage rollout
- `6.7` (Important): No cost forecasting or trend projection on usage page
- `6.8` (Important): Usage page lacks per-org cost attribution
- `6.9` (Nice-to-Have): Feature flag change history shows actor but no diff

## Key Files

- `admin-ui/app/budgets/page.tsx` -- Read-only budget display with org caps, thresholds, enforcement modes
- `admin-ui/app/budgets/__tests__/page.test.tsx` -- Budget page tests
- `admin-ui/app/security/page.tsx` -- Risk score, security stats (24h), recent events, quick actions
- `admin-ui/app/audit/page.tsx` -- Audit log with filters (user_id, action, resource, date range), export (CSV/JSON)
- `admin-ui/app/usage/page.tsx` -- Two tabs: API Usage (daily + top users) and LLM Usage (grouped summary + top spenders)
- `admin-ui/app/flags/page.tsx` -- Maintenance mode + feature flags with scope (global/org/user), change history
- `admin-ui/lib/api-client.ts` -- Budget, security, audit, usage, flag endpoints

## Stage 1: Budget Editing + Alert Threshold Wiring

**Goal**: Make budget management functional instead of read-only.
**Success Criteria**:
- Budget page removes "read-only" badge and "disabled in Stage 5.1" notice.
- Each org budget row has "Edit" button opening a dialog with editable fields: daily/monthly USD cap, daily/monthly token cap.
- Edit dialog includes alert threshold configuration: warning % and critical % per metric.
- Enforcement mode selector per metric: none, soft (log + alert), hard (block + alert).
- Save triggers `PUT /admin/budgets/{org_id}` with confirmation dialog for hard enforcement changes.
- Budget alerts wired to notification system: when threshold crossed, notification sent via configured channels (from monitoring page notification settings).
**Tests**:
- Unit test for budget edit dialog form validation (caps must be positive numbers).
- Unit test for enforcement mode selector interaction.
- Unit test for save confirmation with enforcement mode warning.
- Update existing budget page tests to cover edit flow.
**Status**: Complete

## Stage 2: Security Risk Factor Breakdown + Audit Saved Searches

**Goal**: Make the risk score actionable and the audit log more efficient for repeat queries.
**Success Criteria**:
- Security page risk score section expanded to show contributing factors (e.g., "3 users without MFA", "5 API keys >180 days old", "12 failed logins in 24h").
- Each factor has severity weight and specific remediation link ("Go to Users → filter MFA disabled").
- Risk score breakdown shows calculation: factor weights × values = total score.
- Audit page adds "Saved Searches" panel: save current filter configuration with a name.
- Saved searches stored in localStorage (v1) with option for backend persistence (v2).
- Saved search list appears as pill buttons above filters; click to apply.
- "Alert on Pattern" option per saved search: when enabled, runs this query periodically and triggers notification if new matches found.
**Tests**:
- Unit test for risk factor breakdown rendering.
- Unit test for remediation link navigation.
- Unit test for saved search CRUD (save, load, delete, apply).
- Unit test for alert-on-pattern toggle.
**Status**: Complete

## Stage 3: Cost Forecasting + Per-Org Attribution

**Goal**: Help admins predict future costs and attribute them to organizations.
**Success Criteria**:
- Usage page LLM tab adds "Forecast" section showing projected spend for next 7/30/90 days based on linear regression of historical data.
- Forecast shows confidence band (high/medium/low estimate).
- Forecast card includes "At this rate, monthly budget will be exceeded by [date]" warning if applicable.
- LLM usage summary adds "Organization" as a `group_by` dimension.
- Per-org cost table shows: org name, requests, tokens, cost, % of total.
- Per-org view links to org detail page for further investigation.
**Tests**:
- Unit test for linear regression calculation.
- Unit test for forecast confidence band rendering.
- Unit test for budget exceeded projection date calculation.
- Unit test for per-org cost table rendering and sorting.
**Status**: Complete

## Stage 4: Feature Flag Rollout + Compliance Reports + Change Diffs

**Goal**: Upgrade feature flags beyond on/off and enable compliance reporting.
**Success Criteria**:
- Feature flag form adds "Rollout %" field (0-100): flag applies to that percentage of matching scope.
- Rollout percentage shown on flag row as progress bar.
- Flag targeting adds "User List" option: comma-separated user IDs for targeted rollout.
- A/B variant support: flag can have string value (not just boolean) for variant testing.
- Audit page adds "Generate Compliance Report" button: select date range and report type (Activity Summary, Access Review, Data Access).
- Report generates a downloadable PDF or formatted HTML with: period, total events, events by category, user activity summary, anomaly highlights.
- Feature flag change history shows before/after diff for scope, targeting, and rollout % changes.
**Tests**:
- Unit test for rollout percentage input and progress bar.
- Unit test for user targeting list parsing and validation.
- Unit test for compliance report generation trigger and download.
- Unit test for change history diff rendering.
**Status**: Complete

## Dependencies

- Stage 1 `PUT /admin/budgets/{org_id}` backend endpoint is implemented and accepts the planned payload (`OrgBudgetSelfUpdateRequest` -> `OrgBudgetUpdateRequest` conversion).
- Stage 1 alert wiring requires integration with the notification system already present on the monitoring page.
- Stage 2 risk factor breakdown is currently computed client-side from security health + user/key data (no new backend endpoint required for v1).
- Stage 3 forecasting is client-side calculation from historical usage data.
- Stage 4 rollout percentage requires backend support for partial flag evaluation. Feature flag change diffs require the backend to return previous state in change history.
