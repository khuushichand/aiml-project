# Admin Budgets (Ops Governance) PRD

## Summary
Platform admins need a first-class way to define per-organization budgets, alert thresholds, and enforcement modes. This PRD defines the initial admin budget endpoints and data flow, focusing on stored configuration and auditability. Enforcement is a follow-on concern.

## Goals
- Provide admin endpoints to list and update org budget settings.
- Support spend caps (USD) and usage caps (tokens) at daily/monthly granularity.
- Capture alert thresholds and enforcement mode for future policy checks.
- Emit audit events for every budget update.

## Non-Goals
- Real-time enforcement or billing interruption logic (enforcement modes are stored for future use only).
- Full billing portal or subscription management UX.
- Alert delivery mechanisms (email/webhooks).

## Users and Use Cases
- Platform admin: set spend caps and alert thresholds for orgs.
- Compliance: review budget changes with clear audit trails.
- Ops: adjust budgets for incidents or cost control events.

## User Stories
- Admins can view all org budgets and plan context in one list.
- Platform admins can update daily/monthly USD and token budgets for an org.
- Org admins can configure alert thresholds and enforcement mode (stored for future enforcement).
- Reviewers can see who changed budgets and when.

## Functional Requirements
### Admin Budgets API
- List budgets for all orgs (with admin scoping).
- Update budgets for a specific org.
- Allow clearing specific budget fields (set field to null) or the entire budget section.
- Return plan and limit context alongside budget settings.

### Storage
- Store budgets in a dedicated `org_budgets` table (`budgets_json` column).
- Keep existing custom limit overrides intact; budgets are no longer stored
  inside `org_subscriptions.custom_limits_json`.

## API Contract
### Admin
- GET `/api/v1/admin/budgets`
  - Query: `org_id?`, `page`, `limit`
  - Response: `{ items: OrgBudgetItem[], total, page, limit }`
- POST `/api/v1/admin/budgets`
  - Body: `{ org_id, budgets?, clear_budgets? }`
  - Semantics:
    - Merge (partial update) by default: `budgets` is merged into existing org budgets.
      Nested objects (`alert_thresholds`, `enforcement_mode`) are merged by key,
      and `per_metric` maps are merged by budget field name.
    - `clear_budgets` is a boolean. When `true`, all stored budgets are cleared and
      `budgets` is ignored for that request.
    - Per-field clearing uses `null` values inside `budgets` (e.g., `"budget_day_usd": null`
      removes that field from stored budgets). For nested objects:
      - `"alert_thresholds": null` clears all thresholds.
      - `"alert_thresholds": { "global": null }` clears only the global list.
      - `"alert_thresholds": { "per_metric": { "budget_day_usd": null } }` clears
        the per-metric list for that budget field.
      - `"enforcement_mode": null` clears all enforcement settings.
    - If no `org_budgets` row exists for the org, create it on first update.
    - `alert_thresholds` lists are normalized (de-duplicated and stored in
      ascending order); empty lists are rejected (use `null` to clear).
  - Example (merge):
    - Existing: `{budget_day_usd: 100, budget_month_usd: 500}`
    - POST `{org_id: 1, budgets: {budget_day_usd: 150}}`
    - Result: `{budget_day_usd: 150, budget_month_usd: 500}` (month preserved)
  - Example (clear all):
    - Existing: `{budget_day_usd: 100, budget_month_usd: 500}`
    - POST `{org_id: 1, clear_budgets: true}`
    - Result: `{}` (all budgets removed)
  - Example (per-metric merge + clear):
    - Existing:
      `{alert_thresholds: {global: [80], per_metric: {budget_day_usd: [90]}},
        enforcement_mode: {global: "soft"}}`
    - POST `{org_id: 1, budgets: {alert_thresholds: {per_metric: {budget_day_usd: null}},
      enforcement_mode: {per_metric: {budget_month_usd: "hard"}}}}`
    - Result:
      `{alert_thresholds: {global: [80], per_metric: {}},
        enforcement_mode: {global: "soft", per_metric: {budget_month_usd: "hard"}}}`
  - Example (alert thresholds normalization):
    - POST `{org_id: 1, budgets: {alert_thresholds: {global: [95, 80, 80]}}}`
    - Result: `{alert_thresholds: {global: [80, 95]}}`
  - Response: `OrgBudgetItem`
  - Errors:
    - `404 org_not_found` when the org does not exist.
    - `400 invalid_budget_update` for invalid budget values.
    - `422` validation errors for malformed request payloads.
    - `500 plan_not_found` or `subscription_not_found` when subscription metadata is missing.

### OrgBudgetItem (response)
- org_id, org_name, org_slug
- plan_name, plan_display_name
- budgets: {
    budget_day_usd?, budget_month_usd?, budget_day_tokens?, budget_month_tokens?,
    alert_thresholds?, enforcement_mode?
  }
  - `alert_thresholds`:
    - `global`: list of percent ints (1-100). Applied to all budgets.
    - `per_metric`: map of budget field name -> list of percent ints.
    - Lists are normalized (de-duplicated and stored in ascending order).
    - Unknown per-metric keys are rejected with `invalid_budget_update`.
  - `enforcement_mode`:
    - `global`: "none" | "soft" | "hard"
    - `per_metric`: map of budget field name -> "none" | "soft" | "hard"
  - Per-metric keys are budget field names: `budget_day_usd`, `budget_month_usd`,
    `budget_day_tokens`, `budget_month_tokens`.
- custom_limits: user-configured overrides stored on the org subscription (JSON),
  not modified by admin budget updates.
- effective_limits: computed limits returned by the API after applying fallback
  logic (use custom_limits when present; otherwise use plan defaults; if plan data
  is missing, fall back to global/system defaults).
- updated_at

## Data Model
- New table: `org_budgets`
  - `org_id` (PK, FK to organizations.id)
  - `budgets_json` (JSON object)
  - `created_at`, `updated_at`
- `budgets_json` shape:
  - `budget_day_usd`
  - `budget_month_usd`
  - `budget_day_tokens`
  - `budget_month_tokens`
  - `alert_thresholds.global` (array of percent ints; e.g., `[80, 95]`)
  - `alert_thresholds.per_metric` (map of budget field -> array of percent ints)
  - `enforcement_mode.global` ("none" | "soft" | "hard")
  - `enforcement_mode.per_metric` (map of budget field -> "none" | "soft" | "hard")
  - Other custom limit overrides (if present) remain untouched in `org_subscriptions.custom_limits_json`.
- `alert_thresholds` rules:
  - Arrays contain integer percentages 1-100 inclusive (e.g., `[80, 95]`).
  - Order is not significant; the service should de-duplicate and store values
    in ascending order.
  - Empty arrays are rejected; use `null` to clear.
- `enforcement_mode` rules (intended future behavior; currently stored only):
  - `none`: no enforcement or alerting actions are triggered.
  - `soft`: record and warn on threshold/overage but allow usage to continue.
  - `hard`: block further usage when a budget is exceeded.
  - `per_metric` overrides `global`; if `global` is missing, default to `none`.

### custom_limits / effective_limits relationship
- `custom_limits` is the raw JSON override persisted on the org subscription.
  Budget updates do not modify this payload.
- `effective_limits` is derived as:
  ```
  base_limits = plan_limits_from_subscription
    or get_plan_limits(plan_name)  # global/system defaults
  effective_limits = base_limits
  if custom_limits:
      effective_limits.update(custom_limits)
  if budgets_json:
      effective_limits["budgets"] = budgets_json
  ```
- Budget fields included in `effective_limits.budgets` when set:
  `budget_day_usd`, `budget_month_usd`, `budget_day_tokens`, `budget_month_tokens`,
  `alert_thresholds`, `enforcement_mode`.
- Validation/rounding: values must be >= 0 (or `null` to clear); token budgets are
  integers; alert thresholds are integer percentages between 1 and 100; no rounding
  is applied beyond these validations.

## Audit and Observability
- Budget updates emit unified audit events using `AuditEventType.CONFIG_CHANGED`
  and `AuditEventCategory.SYSTEM`, tied to the `org_budget` resource.
- Event payload mirrors the current unified audit service (`AuditEvent.to_dict`):
  - Core fields: `event_id`, `timestamp`, `category`, `event_type`, `severity`.
  - Context fields (prefixed): `context_request_id`, `context_correlation_id`,
    `context_session_id`, `context_user_id`, `context_api_key_hash`,
    `context_ip_address`, `context_user_agent`, `context_endpoint`,
    `context_method`.
  - Event details: `resource_type`, `resource_id`, `action`, `result`,
    `error_message`.
  - Metrics: `duration_ms`, `tokens_used`, `estimated_cost`, `result_count`.
- Risk/compliance: `risk_score`, `pii_detected`, `compliance_flags`.
- Additional data: `metadata` (JSON object; free-form, PII-scrubbed). In the
  stored payload, both `metadata` and `compliance_flags` are JSON-encoded text
  and should be decoded by consumers when needed.
- Budget update metadata should include: `org_id`, `clear_budgets`, and `updates`
  (the serialized `budgets` fields applied in the request). Optionally include a
  `changes` array for downstream consumers, but keep it inside `metadata`.
- Example (single-field update, full payload fields):
  ```
  {
    "event_id": "3f1c5b7d-8e2e-4cbe-9d9a-6b0f5f5b9c35",
    "timestamp": "2025-01-02T03:04:05Z",
    "category": "system",
    "event_type": "config.changed",
    "severity": "info",
    "context_request_id": "req_abc123",
    "context_correlation_id": "corr_789",
    "context_session_id": "sess_456",
    "context_user_id": "7",
    "context_api_key_hash": null,
    "context_ip_address": "203.0.113.10",
    "context_user_agent": "Mozilla/5.0",
    "context_endpoint": "/api/v1/admin/budgets",
    "context_method": "POST",
    "resource_type": "org_budget",
    "resource_id": "42",
    "action": "budget.update",
    "result": "success",
    "error_message": null,
    "duration_ms": 12.7,
    "tokens_used": null,
    "estimated_cost": null,
    "result_count": 1,
    "risk_score": 0,
    "pii_detected": false,
    "compliance_flags": "[]",
    "metadata": "{\"org_id\":42,\"clear_budgets\":false,\"updates\":{\"budget_day_usd\":150},\"changes\":[{\"field_name\":\"budgets.budget_day_usd\",\"old_value\":100,\"new_value\":150,\"data_type\":\"number\"}]}"
  }
  ```

## Edge Cases
- Org without an existing subscription row: create a default free subscription record before storing budgets.
- Budget update with null values: remove those fields from stored budgets.
- Missing plan data: fall back to default free plan limits.

## Open Questions (Resolved)
- Budgets are stored outside `custom_limits_json` in a dedicated `org_budgets` table.
- Alert thresholds are per-metric with an additional global set for cross-budget signals.
- Enforcement mode supports a global default with optional per-budget overrides.
