# MCP Hub Shared Workspace Registry Design

Status: Implemented

## Goal

Add an admin-managed shared workspace registry so MCP Hub can support reusable `team`, `org`, and `global` workspace sets without depending on user-local `workspace_id` meaning.

The design keeps the existing user-scoped workspace trust model intact. Shared scopes get a separate, explicit trust source instead of trying to infer shared workspace roots from user-owned sandbox state.

## Scope

This slice covers:

- a first-class shared workspace registry in MCP Hub
- admin-managed CRUD for trusted shared workspace roots
- runtime resolution of shared `workspace_id -> absolute_root`
- shared-scope reusable workspace sets validated against that registry
- effective preview/source metadata that distinguishes:
  - `user_local`
  - `shared_registry`

This slice does not cover:

- migrating user-scoped workspace handling into the new registry
- mixed user-local and shared workspace membership on one assignment
- one request/session activating multiple workspace roots
- approvable bypass for workspace membership denies
- arbitrary client-supplied shared root hints

## Current Gap

The branch now has:

- trusted user-scoped workspace resolution for sandbox, direct HTTP, and direct WebSocket callers
- user-scoped reusable workspace sets
- deny-only enforcement of `workspace_not_allowed_for_assignment`

What is still missing is:

- reusable workspace membership above user scope
- a server-owned source of truth for `team`, `org`, and `global` workspace roots

Without that, shared workspace sets remain unsafe because the same `workspace_id` can mean different things for different users.

## Review Corrections

### 1. Shared workspace registry CRUD must use a stricter auth boundary

Ordinary MCP Hub mutation permission is not enough for trusted shared roots.

For v1:

- shared workspace registry create/update/delete requires an admin or `system.configure`-class permission
- read access still follows normal MCP Hub visibility rules

This keeps trusted shared roots under an infrastructure-level control plane instead of ordinary persona-policy editing.

### 2. Registry lookup must have deterministic scope resolution

Runtime currently receives one active `workspace_id` plus assignment scope context. If the same `workspace_id` exists at more than one shared scope, the design must not guess.

Resolution order:

1. same-scope registry match
2. parent-scope registry match
3. never child-scope

If more than one registry entry is visible within the same scope tier, resolution fails closed as ambiguous.

### 3. Shared registry roots must use the same path safety model as existing trusted roots

On save:

- `absolute_root` is normalized to a canonical absolute path
- empty roots are rejected
- roots that fail the project’s existing path/symlink safety policy are rejected

This keeps shared registry entries from becoming a weaker trust source than the current sandbox/user path model.

### 4. Shared registry entries cannot be destructively changed while referenced

For v1:

- delete is blocked while any shared workspace set references the entry
- scope-changing updates are blocked while referenced
- root changes may also be blocked while referenced unless you explicitly choose to allow them later with stronger audit semantics

This prevents silent drift in referenced shared workspace sets.

### 5. Shared workspace-set member validation must be scope-compatible

For `team`, `org`, and `global` workspace sets:

- every member `workspace_id` must resolve through the shared registry
- the matching registry entry must be same-scope or parent-scope compatible with the workspace-set owner
- child-scope entries are never valid for a broader shared workspace set

### 6. Effective preview must expose trust-source identity explicitly

Showing only effective workspace ids is no longer enough once shared roots exist.

The effective policy summary should expose:

- `selected_workspace_trust_source`
  - `user_local`
  - `shared_registry`
- `selected_workspace_source_mode`
- `selected_workspace_set_object_id`
- `selected_workspace_set_object_name`
- `selected_assignment_workspace_ids`

Optionally:

- display names for resolved shared registry entries

### 7. Direct ingress stays unchanged in v1

HTTP and WebSocket callers still provide only:

- `workspace_id`
- `cwd`

No new client-supplied shared-root hints are added. Assignment scope plus workspace-source selection determine whether runtime resolves through the user-local path or the shared registry.

## Architecture

This slice introduces a new MCP Hub resource:

### SharedWorkspaceRegistryEntry

Suggested fields:

- `id`
- `workspace_id`
- `display_name`
- `absolute_root`
- `owner_scope_type`
- `owner_scope_id`
- `is_active`
- `created_by`
- `updated_by`
- timestamps

V1 restrictions:

- `owner_scope_type` must be one of:
  - `team`
  - `org`
  - `global`
- `user` is not supported in this new registry

This resource is infrastructure state, not persona policy state.

## Scope Compatibility Model

The shared registry follows the same broad owner-scope ordering already used elsewhere in MCP Hub:

1. `global`
2. `org`
3. `team`

Compatibility rules:

- a `team` assignment or workspace set may use:
  - same `team`
  - parent `org`
  - parent `global`
- an `org` assignment or workspace set may use:
  - same `org`
  - parent `global`
- a `global` assignment or workspace set may use:
  - `global` only

Child-scope references are never allowed.

## Data Model Changes

### Shared Workspace Registry

Add a new table for registry entries:

- unique identity on `(owner_scope_type, owner_scope_id, workspace_id)`
- audit metadata
- active flag

### Shared Workspace Sets

Extend reusable workspace sets so they are no longer permanently user-scoped in the long term, but for this slice:

- existing user-scoped sets remain unchanged
- shared-scope sets become legal only when their owner scope is:
  - `team`
  - `org`
  - `global`
- shared-scope workspace-set members must validate through the shared registry instead of the user-local resolver

### Assignment Source

Assignments continue to use the existing explicit source selection:

- `workspace_source_mode`
- `workspace_set_object_id`

No merge behavior is added.

## Validation Rules

### Shared Registry Entry Validation

On create/update:

- require shared-scope owner type
- require canonical non-empty `absolute_root`
- reject invalid or unsafe roots
- reject duplicates within the same owner scope

### Shared Workspace Set Validation

On create/update/member add:

- if the workspace set owner scope is `user`
  - keep existing user-local validation
- if the owner scope is shared
  - validate member `workspace_id`s only against the shared registry
  - require same-scope or parent-scope compatibility
  - reject ambiguous matches

### Assignment Validation

On assignment create/update:

- user-scoped assignments may continue to use user-scoped workspace sets
- shared-scope assignments may reference shared-scope workspace sets with same-scope or parent-scope compatibility
- mixing user-local and shared workspace sources in one assignment is still not supported

## Runtime Resolution

The trust source is determined by the selected workspace source and assignment scope, not by client input.

Runtime flow:

1. resolve active assignment
2. resolve selected workspace source
3. determine trust source:
   - `user_local` for user-scoped workspace sets / inline user membership
   - `shared_registry` for shared-scope workspace sets
4. resolve active `workspace_id` through the required trust source
5. if the active workspace is missing from membership or not resolvable:
   - hard deny
   - no approval
6. continue with existing path-scope and allowlist enforcement

Shared registry resolution order:

1. same-scope match
2. parent-scope match
3. fail closed on ambiguity
4. fail closed if no valid match exists

## Effective Policy Output

Extend effective policy output with:

- `selected_workspace_trust_source`
- existing workspace source fields
- optional shared registry display labels if available

This lets MCP Hub and persona summaries explain not only which workspaces are allowed, but which trust model is currently active.

## MCP Hub UI

### New Tab: Shared Workspaces

Add an admin-focused tab for shared workspace registry CRUD.

Fields:

- workspace id
- display name
- absolute root
- owner scope
- active/inactive

This tab should be clearly framed as trusted infrastructure configuration.

### Workspace Sets UI

When editing a shared-scope workspace set:

- workspace selection should come from the shared registry
- prefer a picker over freeform text

When editing a user-scoped workspace set:

- keep the current user-local validation path

### Assignments And Summaries

Assignments still select one workspace set as today.

Effective preview and persona summary should show:

- workspace source mode
- workspace trust source
- named workspace set
- effective workspace ids

## Runtime And Approval Semantics

This slice does not change the deny-only behavior for workspace membership.

If the active workspace is not allowed by the selected source:

- return `workspace_not_allowed_for_assignment`
- do not emit approval payloads

If the active workspace cannot be resolved through the required trust source:

- return a clear hard-deny reason
- do not fall back to the other trust source

## Testing Strategy

Backend:

- shared registry CRUD
- save-time canonicalization of `absolute_root`
- scope-compatible registry lookups
- ambiguous lookup rejection
- shared workspace-set member validation
- runtime shared-root resolution
- hard deny on missing or disallowed shared workspace

Frontend:

- Shared Workspaces tab CRUD
- shared-scope workspace-set editing uses registry-backed selection
- effective preview shows `shared_registry` vs `user_local`

Regression:

- existing user-scoped workspace-set flows remain unchanged
- direct HTTP/WS ingress still uses only `workspace_id` and `cwd`

## Rollout

Implement in this order:

1. shared registry storage and API
2. service-level validation and shared-root resolver
3. shared workspace-set validation path
4. runtime trust-source selection and effective summary updates
5. MCP Hub admin UI

This keeps the shared trust source additive and avoids destabilizing the user-local path model already in use.
