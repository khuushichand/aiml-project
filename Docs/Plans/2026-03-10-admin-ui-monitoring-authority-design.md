# Admin UI Monitoring Authority Design

## Goal

Replace the admin monitoring page's remaining local-only rule storage and client-only alert mutation behavior with authoritative backend-backed policy and state, without touching the private per-user `self_monitoring` subsystem and without rewriting alert generation in v1.

## Scope

This design applies only to the shared admin monitoring surface in `admin-ui/app/monitoring` and the admin/backend monitoring APIs it consumes.

Out of scope for v1:

- the private per-user `self_monitoring` routes and data model
- building a new alert-evaluation engine
- redesigning watchlists or notification delivery
- changing the existing acknowledge/dismiss UX beyond making it authoritative in the same state overlay model

## Product Intent

The admin monitoring page currently mixes authoritative runtime monitoring reads with browser-local alert rules and client-only assign/snooze/escalate actions. That is acceptable for a prototype, but not for a production admin surface where multiple operators need to see the same state and trust the outcome of an action.

V1 should make the page truthful and shared:

- alert rules become platform-wide shared policy
- assign, snooze, escalate, acknowledge, and dismiss all become backend-confirmed mutations
- alert history becomes server-backed and durable
- the UI stops synthesizing state locally

## Architecture

### High-level shape

Use an admin-owned control-plane persistence layer in the AuthNZ database for:

- platform-wide alert rules
- overlay state for mutable alert actions
- append-only admin alert history

Keep the current runtime alert source read-only. The backend will merge runtime alerts with persisted admin overlay state before returning alerts to the admin UI.

### Why this shape

This closes the production-readiness gap directly without coupling admin operations to the private guardian/self-monitoring system and without expanding scope into a full monitoring-engine rewrite.

## Data Model

### `admin_alert_rules`

Platform-wide shared rule definitions for the admin monitoring page.

Suggested fields:

- `id`
- `metric`
- `operator`
- `threshold`
- `duration_minutes`
- `severity`
- `enabled`
- `created_by_user_id`
- `updated_by_user_id`
- `created_at`
- `updated_at`
- optional soft-delete field if that matches the existing admin repository patterns

V1 rule scope:

- list
- create
- delete
- enabled state persisted

No dedicated edit flow is required unless implementation finds the current UI already depends on it.

### `admin_alert_state`

Authoritative overlay state for mutable admin alert actions. This is keyed by stable alert identity, not by mutable UI state.

Suggested fields:

- `alert_identity`
- `acknowledged_at`
- `dismissed_at`
- `assigned_to_user_id`
- `snoozed_until`
- `escalated_severity`
- `updated_by_user_id`
- `updated_at`

This table does not replace the runtime alert source. It only overlays operator-managed state.

### `admin_alert_events`

Append-only history for authoritative alert actions.

Suggested fields:

- `id`
- `alert_identity`
- `action`
- `actor_user_id`
- `details_json`
- `created_at`

This is distinct from admin audit logs. Audit events should still be emitted for compliance, but the UI should read from this dedicated alert-event table for efficient history rendering.

## Alert Identity

### Requirement

The design depends on a stable backend alert identity so persisted state can be merged back onto active alerts across refreshes.

### Implementation rule

The first implementation task must verify whether the current runtime alert source already provides stable `alert.id` values for still-active alerts.

If the current IDs are not stable enough, implementation must switch immediately to a backend-computed deterministic `alert_identity` rather than carrying the unstable ID further into the design.

The preferred fallback is a deterministic fingerprint derived from a stable tuple exposed by the backend source, not a UI-generated key.

## API Surface

### Admin rule management

New admin control-plane routes should live under `/admin/monitoring/...`, not the general `/monitoring` namespace.

Recommended routes:

- `GET /admin/monitoring/alert-rules`
- `POST /admin/monitoring/alert-rules`
- `DELETE /admin/monitoring/alert-rules/{rule_id}`

### Admin alert mutation routes

Recommended routes:

- `POST /admin/monitoring/alerts/{alert_identity}/assign`
- `POST /admin/monitoring/alerts/{alert_identity}/snooze`
- `POST /admin/monitoring/alerts/{alert_identity}/escalate`

The current acknowledge/dismiss routes can remain in place for compatibility, but their backend implementation should write through the same authoritative overlay state model rather than acting like destructive deletion.

### Alert history

Either:

- include merged recent alert history in the existing admin monitoring load path

or:

- add `GET /admin/monitoring/alerts/history`

V1 should support at least:

- `limit`
- optional `alert_identity`

so the contract can scale without a breaking change later.

## Backend Behavior

### Read path

1. Load runtime/admin monitoring alerts from the current backend source.
2. Resolve stable alert identity for each alert.
3. Load matching overlay state from `admin_alert_state`.
4. Merge:
   - acknowledgement
   - dismissal
   - assignment
   - snooze
   - escalated effective severity
5. Return the merged alert list to the admin UI.

### Mutation semantics

- Rules: create/delete fail closed; no local fallback
- Assignment: store canonical backend user id, not a display label
- Snooze: store `snoozed_until`; visibility filtering remains a UI concern using backend state
- Escalate: authoritative override of displayed effective severity for v1, not a new evaluation pass
- Acknowledge/dismiss: set overlay state and emit history/audit; do not destructively remove canonical history

### History semantics

Only backend-confirmed mutations create history entries.

The UI must not synthesize alert timeline entries locally.

## RBAC and Ownership

These rules and alert actions are platform-wide shared admin policy in v1.

That means:

- no org-level partitioning in the initial data model
- admin-only access through the existing admin monitoring authorization path
- canonical backend user ids for assignment state

## Frontend Changes

### Rules

`admin-ui/app/monitoring/use-alert-rules.ts` should stop hydrating from browser storage and instead:

- load rules from backend
- create rules through backend
- delete rules through backend
- refresh authoritative state after mutation

### Alert actions

`admin-ui/app/monitoring/use-alert-actions.ts` should stop mutating client-only state for:

- assign
- snooze
- escalate

Those actions should call backend endpoints first, then refresh alerts/history from backend-confirmed state.

### Copy

Remove the current “stored locally until backend endpoint exists” disclaimer from:

- `admin-ui/app/monitoring/components/MonitoringManagementPanels.tsx`

## Failure Semantics

The admin monitoring page must fail closed for rule and action mutations:

- no success toast when backend persistence fails
- no optimistic local rule/history fallback
- no locally fabricated alert history on failed mutations

If the backend action fails, the page should show the error and preserve the last authoritative backend state.

## Testing Strategy

### Backend

- repository tests for rule CRUD
- repository tests for alert overlay state and alert event persistence
- API tests for:
  - list/create/delete rules
  - assign/snooze/escalate
  - acknowledge/dismiss writing through the overlay state path
- merge tests proving persisted overlay state is reflected in returned alerts
- history tests proving only backend-confirmed actions appear in `admin_alert_events`

### Frontend

- replace local-storage rule tests with API-backed tests
- replace client-only assign/snooze/escalate tests with backend mutation tests
- verify the local-only disclaimer is removed
- verify failures do not create fake success state

### Integration

At least one integration path should prove:

- an alert action persists on the backend
- the page reloads
- the state remains visible after reload

## Risks and Mitigations

### Risk: unstable alert identity

Mitigation:

- validate early
- switch to deterministic backend fingerprint immediately if needed

### Risk: mixing admin control-plane and runtime read namespaces

Mitigation:

- put new shared policy routes under `/admin/monitoring/...`

### Risk: using audit log as the only history store

Mitigation:

- keep dedicated `admin_alert_events` for UI reads
- emit audit events separately

## Recommended V1 Outcome

At the end of this block:

- admin alert rules are shared and durable
- all admin alert actions are backend-authoritative
- alert history is truthful and shared
- the admin monitoring UI no longer depends on local browser state for policy or mutable alert state
