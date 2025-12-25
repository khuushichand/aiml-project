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
- Allow clearing specific budget fields or the entire budget section.
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
  - Response: `OrgBudgetItem`

### OrgBudgetItem (response)
- org_id, org_name, org_slug
- plan_name, plan_display_name
- budgets: { budget_day_usd?, budget_month_usd?, budget_day_tokens?, budget_month_tokens?, alert_thresholds?, enforcement_mode? }
- custom_limits, effective_limits
- updated_at

## Data Model
- `org_subscriptions.custom_limits_json` stores:
  - `budgets.budget_day_usd`
  - `budgets.budget_month_usd`
  - `budgets.budget_day_tokens`
  - `budgets.budget_month_tokens`
  - `budgets.alert_thresholds` (array of percent ints)
  - `budgets.enforcement_mode` ("none" | "soft" | "hard")

## Audit and Observability
- Budget updates emit `config.changed` events with org_id and actor_id.
- Updates include metadata describing changed fields.

## Edge Cases
- Org without an existing subscription row: create a default free subscription record before storing budgets.
- Budget update with null values: remove those fields from stored budgets.
- Missing plan data: fall back to default free plan limits.

## Open Questions
- Should budgets be stored outside `custom_limits_json` in a dedicated table?
- Should alert thresholds be per-metric or shared for all budgets?
- Should enforcement_mode be a global toggle or per-budget field?
