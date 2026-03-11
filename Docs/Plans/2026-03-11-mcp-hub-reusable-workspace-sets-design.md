# MCP Hub Reusable Workspace Sets Design

Status: Approved for planning

## Goal

Add reusable named workspace membership objects for MCP Hub assignments without weakening the current trusted-workspace path model.

The design keeps one active trusted `workspace_id` per request/session. Reuse is added at the assignment configuration layer, not by letting one tool call span multiple roots or by broadening approval behavior.

## Scope

This slice covers:

- first-class `WorkspaceSetObject` CRUD in MCP Hub
- explicit assignment workspace-source wiring via:
  - `workspace_source_mode`
  - `workspace_set_object_id`
- assignment choice of exactly one workspace membership source:
  - inline assignment rows
  - named workspace set object
- effective preview/provenance fields that identify workspace source explicitly
- save-time validation of named workspace-set members against the trusted workspace resolver model
- deny-only runtime enforcement of `workspace_not_allowed_for_assignment`

This slice does not cover:

- additive merging of named and inline workspace membership
- reusable workspace sets on profiles
- shared `team` / `org` / `global` workspace-set objects
- approvable workspace membership bypasses
- one request/session activating multiple workspace roots at once

## Current Gap

The branch now has:

- assignment-only inline workspace membership rows
- trusted `workspace_id -> workspace_root` resolution for sandbox, direct HTTP, and direct WebSocket callers
- reusable `PathScopeObject` support for relative path rules

What is still missing is:

- reuse of the same trusted workspace membership across many assignments
- clear workspace-source identity in effective previews and provenance

## Review Corrections

### 1. Reusable workspace sets must be user-scoped in v1

Trusted workspace resolution is currently keyed by `(user_id, workspace_id)`, not by a global workspace registry. That means shared-scope reusable workspace sets are not safe yet.

For v1:

- `WorkspaceSetObject` is `user` scope only
- `owner_scope_type` must be `user`
- `owner_scope_id` is required
- only user-scoped assignments with the same `owner_scope_id` may reference them

This avoids global or team assignments depending on a user-local workspace namespace.

### 2. Assignment workspace source must be explicit

Do not infer workspace mode from presence of rows or an object id.

Add explicit assignment fields:

- `workspace_source_mode: inline | named`
- `workspace_set_object_id: nullable`

This keeps source selection stable, auditable, and easy to render in the UI.

### 3. Inline workspace rows stay preserved but inactive under named mode

When an assignment switches from inline workspace membership to a named workspace set:

- existing inline rows are preserved in storage
- runtime ignores them while `workspace_source_mode = named`
- UI should make it clear they are inactive until switching back

This mirrors the current preservation approach for inline path rules when using named path-scope objects.

### 4. Workspace-set object deletion should be blocked while referenced

Do not copy the current hard-delete behavior from path-scope objects here.

For v1:

- deleting a `WorkspaceSetObject` that is referenced by any assignment should fail
- API returns a clear validation error
- user must detach references first

This avoids dangling assignment references and ambiguous fallback behavior.

### 5. Workspace membership validation must happen on write

Named workspace-set members should not be stored as unchecked strings that only fail later at runtime.

On create/update:

- each `workspace_id` must be non-empty
- each `workspace_id` must resolve through the same trusted workspace lookup model used at runtime
- validation is performed against the owning `user_id`

This keeps reusable workspace sets from becoming containers for junk or stale ids.

### 6. Effective preview needs workspace-source metadata

Showing only the final workspace id list is no longer enough.

The effective policy response should expose:

- `selected_workspace_source_mode`
- `selected_workspace_set_object_id`
- `selected_workspace_set_object_name`
- `selected_assignment_workspace_ids`

This lets MCP Hub explain whether membership came from inline rows or a named object.

## Data Model

### WorkspaceSetObject

Add a new MCP Hub object for reusable trusted workspace membership.

Suggested fields:

- `id`
- `name`
- `description`
- `owner_scope_type`
- `owner_scope_id`
- `is_active`
- `created_by`
- `updated_by`
- timestamps

V1 restriction:

- `owner_scope_type` must be `user`
- `owner_scope_id` must be non-null

### WorkspaceSetObject Members

Store members separately:

- `workspace_set_object_id`
- `workspace_id`
- `created_by`
- timestamps

Enforce uniqueness on `(workspace_set_object_id, workspace_id)`.

### Assignment Workspace Source

Add explicit fields to `mcp_policy_assignments`:

- `workspace_source_mode`
- `workspace_set_object_id`

Rules:

- `workspace_source_mode = inline`
  - runtime uses existing `mcp_policy_assignment_workspaces` rows
  - `workspace_set_object_id` must be null
- `workspace_source_mode = named`
  - runtime uses the referenced `WorkspaceSetObject`
  - inline rows are preserved but ignored
- if neither inline rows nor a named object exists, current backward-compatible behavior remains unchanged

## Effective Resolution

Workspace membership is still not merged like policy documents. One source is selected and enforced directly.

Resolution order:

1. resolve active trusted `workspace_id`
2. resolve selected assignment
3. read `workspace_source_mode`
4. load membership from:
   - inline assignment rows, or
   - referenced named workspace set
5. if membership exists and active workspace is absent:
   - hard deny
   - `workspace_not_allowed_for_assignment`
   - no approval
6. continue with existing path-scope enforcement

Backward compatibility:

- assignments with no workspace source configured keep current behavior
- existing inline assignment rows continue to work without named workspace sets

## Validation Rules

### WorkspaceSetObject Validation

On create/update:

- `owner_scope_type` must be `user`
- `owner_scope_id` must be present
- `name` must be unique within `(owner_scope_type, owner_scope_id)`

### Workspace Member Validation

On create/update:

- `workspace_id` must be trimmed and non-empty
- duplicates are rejected
- each member must resolve through the trusted workspace lookup path for the owning `user_id`
- unresolved or ambiguous members are rejected on save

### Assignment Reference Validation

On assignment create/update:

- `workspace_source_mode` must be one of `inline | named`
- if `named`, `workspace_set_object_id` must exist and be active
- if `named`, assignment must be `user` scope with matching `owner_scope_id`
- if `inline`, `workspace_set_object_id` must be null

## Runtime Enforcement

Workspace membership remains a deny-only boundary.

Decision rules:

- active workspace not in selected named set:
  - hard deny
  - `workspace_not_allowed_for_assignment`
  - no approval payload
- active workspace not in selected inline rows:
  - same hard deny
- path or allowlist misses inside an allowed workspace:
  - keep current narrow path approval model

Approvals must not bypass workspace membership. Approval scope may continue including active `workspace_id`, but workspace membership violations never become approval candidates.

## MCP Hub UI

### New Tab: Workspace Sets

Add a new `Workspace Sets` tab in MCP Hub.

This tab manages reusable workspace-set objects:

- name
- description
- active/inactive
- workspace id list

The UI should clearly state that these are trusted workspace ids for one user and are not shared cross-scope in v1.

### Assignments

Assignments gain a `Workspace Access Source` selector:

- `Use inline workspace list`
- `Use named workspace set`

If inline:

- show the existing assignment workspace editor

If named:

- show a workspace-set picker
- show preserved inline rows as inactive if any exist

### Effective Preview

Show:

- workspace source mode
- named workspace set name if selected
- effective workspace ids
- clear deny-only semantics for workspace membership

## Migration And Compatibility

No existing assignment is forced to adopt named workspace sets.

Compatibility rules:

- existing inline assignment workspace rows remain valid
- assignments with no workspace rows and no named set remain valid under current behavior
- switching to named mode is reversible without data loss because inline rows remain stored

## Testing Focus

Key coverage for this slice:

- `WorkspaceSetObject` CRUD and member uniqueness
- write-time validation of workspace ids against trusted user-scoped resolution
- user-scope-only object restrictions
- assignment source switching and preservation of inline rows
- deny-only runtime behavior for named workspace-set misses
- effective preview showing workspace source identity
