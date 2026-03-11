# MCP Hub Assignment Overrides And Provenance Design

Date: 2026-03-10
Status: Approved for planning

## Summary

The next MCP Hub checkpoint should add assignment-bound overrides and effective-policy provenance.

This work does not introduce standalone overrides. An override may only exist as a single 1:1 record attached to an existing `mcp_policy_assignment`. The MCP Hub UI remains centered on `Assignments`, and the resolver returns both the effective policy and enough provenance to explain how that result was built.

## Why This Is The Next Slice

The capability-registry and guided-editor checkpoint now gives MCP Hub:

- derived tool metadata
- a registry-backed catalog
- guided editing for profiles and assignments

What is still missing is a clear way to express "base policy here, targeted delta here" and then explain the result back to the user. Today the assignment inline policy and the effective preview are still too flat for that. The schema already reserves `mcp_policy_overrides`, but the repo, service, API, resolver, and UI do not expose it.

## Goals

- Add a single optional override record per policy assignment.
- Keep overrides attached only to assignments, never standalone.
- Extend the resolver to apply overrides after profile and inline assignment policy.
- Return compact field-level provenance in effective-policy responses.
- Add MCP Hub assignment UI for create, edit, disable, and delete override.
- Show override presence in assignment lists and persona policy summary.

## Non-Goals

- Standalone overrides.
- Multiple overrides per assignment.
- A top-level `Overrides` tab.
- Element-by-element diff visualization for array fields.
- Credential bindings or external-server precedence work.
- Path-scoped enforcement redesign.

## Reviewed Constraints And Corrections

### 1. Override semantics must match current resolver merge behavior

The current resolver unions list fields such as:

- `allowed_tools`
- `denied_tools`
- `tool_names`
- `tool_patterns`
- `capabilities`

This checkpoint should not invent a second merge model only for overrides. Override application should reuse the same policy merge semantics that assignments already use. Provenance must label these fields as `merged`, not `replaced`, unless the field is actually overwritten.

### 2. Provenance should stay field-level

The first provenance version should explain policy assembly by field, not by exact per-item diff set algebra.

Good example:

- `field = allowed_tools`
- `values = ["remote.fetch"]`
- `source_kind = assignment_override`
- `effect = merged`

This is enough to explain behavior without creating a noisy diff engine.

### 3. Grant-authority checks must evaluate broadened effective access

Override writes cannot be validated only against the override document in isolation.

The server must:

1. resolve the effective assignment state without override
2. simulate application of the proposed override
3. detect whether the effective result broadens capabilities or tool reach
4. require grant authority for the broadened delta

This prevents a seemingly small override document from widening the effective result in ways a local document-only validator would miss.

### 4. One-to-one must be enforced explicitly

The reserved `mcp_policy_overrides` table exists in bootstrap, but this checkpoint must verify and enforce 1:1 behavior on `assignment_id` in both SQLite and Postgres migration paths.

### 5. Deletion behavior must be explicit

Deleting an assignment should delete its override through service/repo behavior, not only by hoping DB cascade behavior is consistent across backends and migration states.

## Data Model

### PolicyAssignment

The existing assignment remains the contextual anchor and may include:

- `target_type`
- `target_id`
- `owner_scope_type`
- `owner_scope_id`
- `profile_id`
- `inline_policy_document`
- `approval_policy_id`
- `is_active`

### PolicyOverride

Add repo/service/API support for a separate record:

- `id`
- `assignment_id` (unique)
- `override_policy_document`
- `is_active`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`

Rules:

- override cannot exist without an assignment
- only one override row may exist per assignment
- inactive overrides are skipped by the resolver
- deleting an assignment removes the override

## Effective Policy Resolution

Resolution remains deterministic and assignment-anchored.

For a single assignment:

1. start with referenced profile policy, if present and active
2. merge assignment inline policy
3. merge assignment override policy, if present and active

Across contexts, keep the current order:

1. `default`
2. `group`
3. `persona`

So the final chain is:

1. default profile
2. default inline
3. default override
4. group profile
5. group inline
6. group override
7. persona profile
8. persona inline
9. persona override

## Provenance Model

Keep the existing high-level `sources` array for compatibility, but add a compact `provenance` array on effective-policy responses.

Each provenance entry should include:

- `field`
- `values`
- `source_kind`
  - `profile`
  - `assignment_inline`
  - `assignment_override`
- `assignment_id`
- `profile_id`
- `override_id`
- `effect`
  - `added`
  - `merged`
  - `replaced`

Field-level guidance:

- list fields use `merged`
- scalar replacement uses `replaced`
- first introduction of a previously-empty field may use `added`

## Backend API Shape

Keep overrides nested under assignments instead of creating a top-level collection.

Add:

- `GET /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`
- `PUT /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`
- `DELETE /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`

Also extend assignment list responses with lightweight summary fields:

- `has_override`
- `override_active`
- `override_id`
- `override_updated_at`

This lets the UI show override state without a second fetch per row.

## UI Design

### Assignments Tab

Keep `Assignments` as the main editing surface.

Each assignment row should show:

- whether an override exists
- whether the override is active
- quick entry into edit mode

The assignment editor should show distinct sections:

- `Base Assignment Policy`
- `Assignment Override`
- `Effective Policy Preview`

Use the existing `PolicyDocumentEditor` for both base policy and override policy, but with explicit labels and helper text so users know which layer they are editing.

### Effective Preview

The effective preview should show:

- effective capabilities
- allowed tools
- denied tools
- approval mode
- provenance entries grouped by field

The first version should emphasize readability over diff exhaustiveness.

### Persona Summary

The persona summary should remain compact and add:

- override present or not
- override active or not
- linked profile name if available

It should not attempt to show the full provenance stream.

## Testing Strategy

### Backend

- unit tests for override repo CRUD and uniqueness
- service tests for assignment deletion cleaning up override
- resolver tests for merge order and provenance output
- grant-authority tests for broadened override writes
- API tests for nested override routes and assignment summary fields

### Frontend

- assignment editor tests for create/edit/delete override
- effective preview tests for provenance rendering
- helper tests for merge semantics and advanced-field preservation
- persona summary tests for override presence badge

## Rollout

1. add repo and migration enforcement for 1:1 overrides
2. add service and nested API routes
3. extend resolver output with provenance
4. wire assignment UI to nested override CRUD
5. add compact persona summary indicator
6. verify with targeted pytest, Vitest, and Bandit

## Recommendation

Implement this as one focused checkpoint after the capability-registry work. Keep it assignment-bound, explainability-first, and consistent with existing merge semantics. Do not broaden scope into standalone overrides or a full policy diff engine.
