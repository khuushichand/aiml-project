# Admin Budgets (Ops Governance) PRD

## Summary
Platform admins need a first-class way to define per-organization budgets, alert thresholds, and enforcement modes. This PRD defines the initial admin budget endpoints and data flow, focusing on stored configuration and auditability. Enforcement is a follow-on concern.

## Goals
- Provide admin endpoints to list and update org budget settings.
- Support spend caps (USD) and usage caps (tokens) at daily/monthly granularity.
- Capture alert thresholds and enforcement mode for future policy checks.
- Emit audit events for every budget update.

## Non-Goals
- Real-time enforcement or billing interruption logic.
- Full billing portal or subscription management UX.
- Alert delivery mechanisms (email/webhooks).

## Users and Use Cases
- Platform admin: set spend caps and alert thresholds for orgs.
- Compliance: review budget changes with clear audit trails.
- Ops: adjust budgets for incidents or cost control events.

## User Stories
- As an admin, I can view all org budgets and plan context in one list.
- As an admin, I can update daily/monthly USD and token budgets for an org.
- As an admin, I can configure alert thresholds and enforcement mode.
- As a reviewer, I can see who changed budgets and when.

## Functional Requirements
### Admin Budgets API
- List budgets for all orgs (with admin scoping).
- Update budgets for a specific org.
- Allow clearing specific budget fields (set field to null) or the entire budget section.
- Return plan and limit context alongside budget settings.

### Storage
- Store budgets inside `org_subscriptions.custom_limits_json` under a `budgets` key.
- Keep existing custom limit overrides intact when updating budgets.

## API Contract
### Admin
- GET `/api/v1/admin/budgets`
  - Query: `org_id?`, `page`, `limit`
  - Response: `{ items: OrgBudgetItem[], total, page, limit }`
- POST `/api/v1/admin/budgets`
  - Body: `{ org_id, budgets?, clear_budgets? }`
  - Semantics:
    - Merge (partial update) by default: `budgets` is merged into existing org budgets.
    - `clear_budgets` is a boolean. When `true`, all stored budgets are cleared and
      `budgets` is ignored for that request.
    - Per-field clearing uses `null` values inside `budgets` (e.g., `"budget_day_usd": null`
      removes that field from stored budgets).
  - Example (merge):
    - Existing: `{budget_day_usd: 100, budget_month_usd: 500}`
    - POST `{org_id: 1, budgets: {budget_day_usd: 150}}`
    - Result: `{budget_day_usd: 150, budget_month_usd: 500}` (month preserved)
  - Example (clear all):
    - Existing: `{budget_day_usd: 100, budget_month_usd: 500}`
    - POST `{org_id: 1, clear_budgets: true}`
    - Result: `{}` (all budgets removed)
  - Response: `OrgBudgetItem`
  - Errors:
    - `404 org_not_found` when the org does not exist.
    - `400 invalid_budget_update` for invalid budget values.
    - `422` validation errors for malformed request payloads.
    - `500 plan_not_found` or `subscription_not_found` when subscription metadata is missing.

### OrgBudgetItem (response)
- org_id, org_name, org_slug
- plan_name, plan_display_name
- budgets: { budget_day_usd?, budget_month_usd?, budget_day_tokens?, budget_month_tokens?, alert_thresholds?, enforcement_mode? }
- custom_limits: user-configured overrides stored on the org subscription (JSON),
  derived from admin budget updates; contains a `budgets` object with fields
  `budget_day_usd`, `budget_month_usd`, `budget_day_tokens`, `budget_month_tokens`,
  `alert_thresholds`, and `enforcement_mode`.
- effective_limits: computed limits returned by the API after applying fallback
  logic (use custom_limits when present; otherwise use plan defaults; if plan data
  is missing, fall back to global/system defaults).
- updated_at

## Data Model
- `org_subscriptions.custom_limits_json` stores:
  - `budgets.budget_day_usd`
  - `budgets.budget_month_usd`
  - `budgets.budget_day_tokens`
  - `budgets.budget_month_tokens`
  - `budgets.alert_thresholds` (array of percent ints; e.g., `[80, 95]` means emit
    alerts at 80% and 95% of a budget. Order is not significant; duplicates are
    allowed but should be avoided. Values must be 1-100 inclusive.)
  - `budgets.enforcement_mode` ("none" | "soft" | "hard"):
    - `none`: no enforcement or alerting actions are triggered.
    - `soft`: record and warn on threshold/overage but allow usage to continue.
    - `hard`: block further usage when a budget is exceeded.
  - Other custom limit overrides (if present) remain untouched by budget updates.

### custom_limits / effective_limits relationship
- `custom_limits` is the raw JSON override persisted on the org subscription.
  Budget updates only affect the `custom_limits.budgets` object.
- `effective_limits` is derived as:
  ```
  base_limits = plan_limits_from_subscription
    or get_plan_limits(plan_name)  # global/system defaults
  effective_limits = base_limits
  if custom_limits:
      effective_limits.update(custom_limits)
  ```
- Budget fields included in `custom_limits.budgets` (and reflected in
  `effective_limits.budgets` when set): `budget_day_usd`, `budget_month_usd`,
  `budget_day_tokens`, `budget_month_tokens`, `alert_thresholds`,
  `enforcement_mode`.
- Validation/rounding: values must be >= 0; token budgets are integers; alert
  thresholds are integer percentages between 1 and 100; no rounding is applied
  beyond these validations.

## Audit and Observability
- Budget updates emit `config.changed` events (AuditEventType.CONFIG_CHANGED) tied
  to the org budget resource.
- Event payload (canonical audit event shape):
  - Required top-level fields: `event_type`, `timestamp`, `org_id`, `actor_id`,
    `resource_type`, `resource_id`, `correlation_id`, `version`.
  - `changes`: array of change entries:
    - `field_name` (string)
    - `old_value` (any)
    - `new_value` (any)
    - `data_type` (string; e.g., "number", "integer", "string", "array", "object", "null")
    - `reason` (optional string)
    - `notes` (optional string)
  - Optional metadata: `actor_role`, `source_ip`, `user_agent`, `request_id`.
- Example (single-field update):
  ```
  {
    "event_type": "config.changed",
    "timestamp": "2025-01-02T03:04:05Z",
    "org_id": 42,
    "actor_id": 7,
    "resource_type": "org_budget",
    "resource_id": "42",
    "correlation_id": "req_abc123",
    "version": 1,
    "changes": [
      {
        "field_name": "budgets.budget_day_usd",
        "old_value": 100,
        "new_value": 150,
        "data_type": "number"
      }
    ],
    "metadata": {
      "actor_role": "admin",
      "source_ip": "203.0.113.10"
    }
  }
  ```
- Example (clear all budgets):
  ```
  {
    "event_type": "config.changed",
    "timestamp": "2025-01-02T03:04:05Z",
    "org_id": 42,
    "actor_id": 7,
    "resource_type": "org_budget",
    "resource_id": "42",
    "correlation_id": "req_def456",
    "version": 1,
    "changes": [
      {
        "field_name": "budgets",
        "old_value": {
          "budget_day_usd": 100,
          "budget_month_usd": 500
        },
        "new_value": null,
        "data_type": "object",
        "notes": "clear_budgets=true"
      }
    ]
  }
  ```

## Edge Cases
- Org without an existing subscription row: create a default free subscription record before storing budgets.
- Budget update with null values: remove those fields from stored budgets.
- Missing plan data: fall back to default free plan limits.

## Open Questions
- Should budgets be stored outside `custom_limits_json` in a dedicated table?
- Should alert thresholds be per-metric or shared for all budgets?
- Should enforcement_mode be a global toggle or per-budget field?
