# MCP Hub Multi-Root Path Scope Objects Design

Status: Implemented

## Goal

Add two related MCP Hub capabilities without weakening the current path-scope model:

- reusable named path-scope objects for relative path rules
- assignment-level multi-workspace authorization, with one active trusted workspace per request/session

The design keeps runtime enforcement anchored to a single resolved workspace root at execution time. Multi-root support means an assignment may operate in more than one trusted workspace overall, not that one tool call may span multiple roots.

## Scope

This slice covers:

- first-class `PathScopeObject` CRUD in MCP Hub
- explicit `path_scope_object_id` references on permission profiles and policy assignments
- assignment-only trusted workspace sets
- effective policy resolution that layers path-scope objects with existing inline and override path fields
- hard-deny runtime enforcement when the active trusted `workspace_id` is not allowed for the assignment
- MCP Hub UI for managing named path-scope objects and assignment workspace membership

This slice does not cover:

- one request/session activating multiple workspace roots at once
- reusable workspace-set objects
- child-scope path-scope object references
- approvable workspace-set bypasses
- multi-root path extraction for one tool invocation

## Current Gap

The branch now has:

- trusted `workspace_id -> workspace_root` resolution for sandbox, direct HTTP, and direct WebSocket ingress
- enforceable path scope with `workspace_root` and `cwd_descendants`
- inline `path_allowlist_prefixes`

What is still missing is:

- reuse of common path rules across many profiles and assignments
- a way for one assignment to be valid across more than one trusted workspace without duplicating policy objects

## Review Corrections

### 1. Path-scope object references must be first-class fields

Do not hide object references inside raw policy JSON. Add explicit nullable `path_scope_object_id` fields on:

- permission profiles
- policy assignments

This keeps wiring separate from the policy document itself and lets the resolver produce clean provenance.

### 2. Keep one concrete layer order

The effective path field order should be:

1. profile-linked path-scope object
2. profile inline path fields
3. assignment-linked path-scope object
4. assignment inline path fields
5. assignment override path fields

`path_allowlist_prefixes` stays a replacement field, not a union field.

### 3. Restrict object references by owner scope

Profiles and assignments may reference path-scope objects from:

- the same owner scope
- a parent owner scope

They may not reference child-scope objects. This avoids shared/global policy depending on user-owned path objects.

### 4. Workspace sets use the same trusted workspace model as runtime resolution

Assignment workspace membership stores only server-known `workspace_id` values. Validation and runtime checks must use the same trusted resolver path as the current direct/sandbox workspace-root logic. Arbitrary strings are not enough.

### 5. Workspace-set violations are deny-only

If an assignment has a workspace set and the active trusted `workspace_id` is not in it, runtime returns a hard deny:

- reason: `workspace_not_allowed_for_assignment`
- no runtime approval
- no approval reuse

### 6. UI must preserve inline path state when switching sources

Switching an assignment/profile from inline path rules to a named path-scope object must not silently discard existing inline path fields. Preserve them and surface clear helper text that inline path fields still replace object fields where present.

## Data Model

### PathScopeObject

Add a new MCP Hub object for reusable relative path rules.

Suggested fields:

- `id`
- `name`
- `description`
- `owner_scope_type`
- `owner_scope_id`
- `path_scope_document_json`
- `is_active`
- `created_by`
- `updated_by`
- timestamps

`path_scope_document_json` stores only existing normalized path-governance keys:

- `path_scope_mode`
- `path_scope_enforcement`
- `path_allowlist_prefixes`

It does not store workspace ids.

### Profile and Assignment References

Add nullable `path_scope_object_id` fields to:

- `mcp_permission_profiles`
- `mcp_policy_assignments`

These references are part of MCP Hub configuration wiring, not policy document JSON.

### Assignment Workspace Set

Add an assignment-only membership table:

- `assignment_id`
- `workspace_id`
- `created_by`
- timestamps

Enforce uniqueness on `(assignment_id, workspace_id)`.

No inheritance from profiles. Workspace membership remains contextual and assignment-specific.

## Effective Resolution

### Path Rule Resolution

The resolver should load path-scope object documents as distinct layers, then merge them through the current policy merge pipeline.

Effective order:

1. profile-linked object document
2. profile inline policy path fields
3. assignment-linked object document
4. assignment inline policy path fields
5. assignment override path fields

All path fields continue to use the existing backend normalization pipeline. `path_allowlist_prefixes` remains replacement-only.

### Workspace Membership Resolution

Workspace membership is not merged across contexts. It belongs only to the selected assignment row.

Rules:

- if an assignment has no workspace set, current behavior remains unchanged
- if an assignment has one or more workspace ids, the active trusted `workspace_id` must match one of them
- active workspace validation happens before path extraction/enforcement

## Runtime Enforcement

Runtime keeps the existing one-root-at-a-time path model.

Flow:

1. resolve active trusted `workspace_id` and `workspace_root`
2. resolve effective assignment for the request context
3. if the assignment has a workspace set, require membership of the active `workspace_id`
4. resolve effective path fields from object + inline + override layers
5. run existing path root and allowlist enforcement against the resolved active root

Decision rules:

- workspace set miss:
  - hard deny
  - `workspace_not_allowed_for_assignment`
  - not approvable
- path or allowlist miss inside an allowed workspace:
  - keep current narrow approval model
- missing trusted workspace under required path scope:
  - keep current fail-closed behavior

Approval scope for path-related approvals should include the active `workspace_id` explicitly so approvals cannot be reused across different allowed workspaces.

## MCP Hub UI

### New Tab: Path Scopes

Add a new MCP Hub tab for `Path Scopes`.

This tab manages reusable path-scope objects with the same guided controls already used for inline path editing:

- local file scope
- allowed workspace paths

No workspace ids appear here.

### Profiles and Assignments

Profiles and assignments should gain:

- a `Path Scope Source` selector:
  - `Use inline rules`
  - `Use named path scope`
- a `PathScopeObject` picker when named scope is selected

Assignments also gain a `Workspace Access` section:

- select one or more trusted `workspace_id`s
- render current membership clearly

### Effective Preview

The preview and provenance UI should show:

- path object source, if any
- inline replacement layer
- current normalized allowlist prefixes
- workspace set membership
- explicit copy that assignment inline and override path fields replace inherited path object fields

### State Preservation

Switching between named and inline path sources preserves existing inline path fields. The UI should warn when preserved inline fields are still overriding object values.

## Validation Rules

### Path-Scope Object Validation

Use the same server-side normalization and validation already applied to inline path fields:

- valid `path_scope_mode`
- valid `path_scope_enforcement`
- normalized `path_allowlist_prefixes`
- no absolute paths or traversal in allowlist prefixes

### Reference Validation

On create/update:

- referenced `path_scope_object_id` must exist
- referenced object must be active
- referenced object must be same-scope or parent-scope

### Workspace Set Validation

On assignment workspace membership writes:

- `workspace_id` must be a non-empty string
- duplicate `(assignment_id, workspace_id)` entries are rejected
- runtime still performs the trusted `workspace_id -> workspace_root` resolution later

## Testing Strategy

Backend:

- path-scope object CRUD
- same-scope and parent-scope reference acceptance
- child-scope reference rejection
- assignment workspace-set CRUD and uniqueness
- effective path resolution from object + inline + override layers
- workspace-set hard deny
- backward compatibility when no workspace set exists
- approval scope changes when active `workspace_id` changes

Frontend:

- `Path Scopes` tab CRUD
- profile and assignment source switching
- inline path state preservation while toggling source mode
- assignment workspace selection
- effective preview/provenance for object vs inline replacement

Regression:

- existing inline path rules keep working unchanged
- assignments without workspace sets keep current behavior
- current path approval model still applies only to path/allowlist misses, not workspace-set misses

## Recommendation

Implement reusable path-scope objects and assignment workspace sets together, but keep runtime anchored to one active trusted workspace per request/session. That gives MCP Hub reusable policy intent plus multi-workspace deployment coverage without broadening a single tool call across multiple roots.
