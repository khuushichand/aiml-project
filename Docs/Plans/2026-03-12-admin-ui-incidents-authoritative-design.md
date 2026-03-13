# Admin UI Incidents Authoritative Workflow Design

**Date:** 2026-03-12

## Goal

Replace browser-local incident assignment and post-mortem workflow state with shared backend-backed incident state so all admins see the same assignee, root cause, impact, and action items.

## Current Problem

The current incidents page persists workflow data in browser `localStorage` and only appends free-form timeline messages when the operator changes assignment or saves a post-mortem. Another admin opening the same incident does not see authoritative workflow state because the backend incident model only stores title, severity, status, summary, tags, and timeline events.

## Chosen Approach

Extend the existing incident record in `system_ops.json` and the current incident `PATCH` route rather than introducing separate incident-workflow endpoints.

This keeps reads and writes atomic in the current store model, minimizes API surface growth, and avoids recreating split-brain workflow state.

## Backend Design

### Incident Record

Each incident record in `system_ops.json` will be extended with:

- `assigned_to_user_id: int | null`
- `assigned_to_label: str | null`
- `root_cause: str | null`
- `impact: str | null`
- `action_items: list[{ id: str, text: str, done: bool }]`

Existing incidents load with safe defaults:

- `assigned_to_user_id = null`
- `assigned_to_label = null`
- `root_cause = null`
- `impact = null`
- `action_items = []`

### Assignment Semantics

The UI sends only `assigned_to_user_id`. The backend resolves the display label from the current user record and may persist that resolved snapshot in `assigned_to_label` for rendering convenience.

The backend will not trust a client-provided assignee label.

The v1 assignee contract is:

- assignees must be admin-capable users
- `assigned_to_label` is the primary display value returned by the backend
- the UI dropdown options are only the selectable set, not the source of truth for current assignee rendering
- if the current assignee is not present in the currently loaded option set, the page still renders the backend-confirmed `assigned_to_label`

### Partial Update Semantics

The incident `PATCH` path will use explicit partial-update behavior:

- omitted field: leave unchanged
- `null`: clear the field
- non-null value: replace the field after validation

This applies to `assigned_to_user_id`, `root_cause`, `impact`, and `action_items`.

Implementation must preserve the omitted-vs-null distinction explicitly, using request metadata such as `model_fields_set` or `model_dump(exclude_unset=True)` rather than relying on naive `None` checks alone.

### Timeline Behavior

Timeline entries remain append-only audit context, but they are no longer the source of truth for workflow state.

- assignment changes append `Assigned to <label>` or `Assignment cleared`
- post-mortem saves append the current post-mortem summary message

The backend update path must persist the structured workflow fields and append the timeline event inside the same store lock so the UI cannot observe partial success.

### Validation

To avoid unbounded JSON blobs in `system_ops.json`, the backend will:

- cap action item count
- cap action item text length
- drop blank action items on save
- normalize invalid/empty values to safe defaults

## Frontend Design

### Source of Truth

The incidents page reads assignment and post-mortem fields directly from `IncidentItem`.

`localStorage` is removed as the durable incident workflow store. Any helper logic in `admin-ui/lib/incident-workflow.ts` becomes pure normalization/formatting logic or is deleted if no longer needed.

### In-Memory Draft State

The page may keep unsaved assignment/post-mortem edits in memory while the operator is on the page, but those drafts do not survive reload and are never written to `localStorage`.

### Mutation Flow

- assignment changes call `PATCH /admin/incidents/{id}`
- post-mortem saves call `PATCH /admin/incidents/{id}`
- the page updates from the backend response or a subsequent reload

The v1 UI will not use optimistic durable assignment updates. Controls may be temporarily disabled while saving, and failures revert to the last backend-confirmed state.

### Failure Semantics

- assignment failure: show error toast and keep backend-confirmed state
- post-mortem failure: keep unsaved form text in memory only, show error toast, do not append fake success timeline text
- no browser-local fallback is used

## RBAC And Scope

This v1 keeps incidents platform-wide shared state, matching the current global incident store and admin incidents page behavior.

Mutation permissions remain aligned with the existing incidents surface unless a separate platform-admin tightening decision is made later.

## Testing

### Backend

- incident service tests for default workflow fields on create/list
- incident update tests for assignment persistence and clearing
- incident update tests for root cause, impact, and action item persistence
- tests proving timeline append happens only on successful authoritative workflow updates
- tests proving omitted fields remain unchanged while explicit `null` clears them

### Frontend

- incidents page tests no longer assert `localStorage` persistence
- assignment tests assert `updateIncident(...)` is called and backend-confirmed assignee survives reload
- post-mortem tests assert backend-backed workflow fields render and survive reload
- failure tests assert no fake durable local state remains after failed saves
- assignee rendering tests assert the page prefers `assigned_to_label` from `IncidentItem` even when the current assignee is not present in the currently loaded dropdown options

### Verification

- targeted pytest for incident service and endpoint behavior
- targeted vitest for incidents page
- Bandit on touched backend files

## Not Included

This v1 does not redesign incidents into organization-scoped state, does not add a separate incident workflow subsystem, and does not migrate stale browser-local post-mortem drafts into shared backend state.
