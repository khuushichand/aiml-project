# MCP Hub Workspace Source Readiness Warnings Design

Date: 2026-03-11
Status: Approved for planning

## Goal

Add advisory, read-only multi-root readiness warnings for reusable workspace
sources and surface them in:

- `Workspace Sets`
- `Shared Workspaces`
- the assignment editor's named workspace-set picker

These warnings are informational only. Assignment save validation remains the
only enforcement boundary.

## Scope

This slice covers:

- a shared readiness-summary DTO for reusable workspace sources
- server-side batched readiness summary generation for workspace-set and
  shared-workspace list responses
- UI rendering of advisory warnings in tabs and named workspace-set picker

This slice does not cover:

- new blocking behavior on workspace-set or shared-workspace objects
- changes to assignment save validation
- a cross-object governance dashboard

## Advisory Meaning

Object-level readiness here means:

- "this source appears multi-root-ready if later used under `workspace_root`
  semantics"

It does **not** mean:

- the object is globally valid for every assignment
- the object is invalid for single-root use
- the object is a runtime error by itself

That distinction matters because multi-root hardening only applies to concrete
assignments after effective path mode and active workspace source are known.

## Shared DTO

Add one shared summary shape for list responses:

- `is_multi_root_ready: bool`
- `warning_codes: string[]`
- `warning_message: str | null`
- `conflicting_workspace_ids: string[]`
- `conflicting_workspace_roots: string[]`
- `unresolved_workspace_ids: string[]`

Recommended warning codes:

- `multi_root_overlap_warning`
- `workspace_unresolvable_warning`

This DTO should be embedded directly in:

- `WorkspaceSetObjectResponse`
- `SharedWorkspaceResponse`

The frontend should mirror the same type in `mcp-hub.ts`.

## Backend Computation Model

Readiness must be computed server-side and returned inline with list rows.

Recommended service helpers:

- `get_workspace_set_readiness_summary(...)`
- `get_shared_workspace_readiness_summary(...)`

Rules:

- never raise or block
- tolerate unresolved or overlapping roots as normal warning outcomes
- batch-friendly for list rendering

### Workspace Set Summaries

For `WorkspaceSetObject`:

- use the same trust source semantics already in the branch
- `user` scope -> `user_local`
- shared scopes -> `shared_registry`
- resolve member workspace ids through the correct trust path
- if unresolved ids exist, surface `workspace_unresolvable_warning`
- if two resolved roots overlap by canonical ancestry/equality, surface
  `multi_root_overlap_warning`

This is advisory only and intentionally does not inspect assignment-level path
mode.

### Shared Workspace Summaries

For `SharedWorkspaceRegistryEntry`:

- compare against only same-scope and parent-scope visible shared entries
- never compare against hidden child scopes or unrelated sibling scopes
- use the same safe canonicalization rules already used elsewhere in path
  governance
- if another visible shared root overlaps, surface
  `multi_root_overlap_warning`

This gives a useful "may conflict in multi-root bundles" signal without
claiming that the entry is unusable on its own.

## UI Behavior

### Workspace Sets Tab

- show readiness badge/tag on each list row
- show inline warning details when present:
  - conflicting workspace ids
  - conflicting roots
  - unresolved workspace ids

### Shared Workspaces Tab

- show readiness badge/tag on each list row
- message should stay advisory:
  - "May conflict with other visible shared roots in multi-root assignments"

### Assignment Picker

- consume the same `listWorkspaceSetObjects()` response
- render readiness next to each named workspace-set option
- when a non-ready set is selected, show a local warning near the picker
- do not block selection

This keeps all warning surfaces on one backend source of truth.

## Performance Constraint

Do not implement readiness as an extra per-row UI fetch path.

The branch already does additional per-object member loading in
`WorkspaceSetsTab`, so readiness should be included in list responses to avoid
turning the tabs and picker into further N+1 request chains.

## Testing Strategy

Backend coverage should include:

- workspace-set list rows include readiness summaries
- shared-workspace list rows include readiness summaries
- overlap produces advisory warning, not error
- unresolved workspace ids produce advisory warning, not error

Frontend coverage should include:

- `Workspace Sets` renders readiness warning state
- `Shared Workspaces` renders readiness warning state
- assignment named workspace-set picker shows readiness labels

## Recommendation

Keep this slice narrow and advisory.

That gives users earlier visibility into problematic reusable workspace sources
without moving the enforcement boundary away from concrete assignments. It also
creates the reusable DTO needed for the later governance audit view.
