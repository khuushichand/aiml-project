# MCP Hub Governance Audit View Design

Date: 2026-03-11
Status: Approved for planning

## Goal

Add a read-only `Audit` tab to MCP Hub that aggregates concrete, already
computed governance findings across all MCP Hub objects visible to the current
user.

This first release is intentionally narrow:

- read-only only
- concrete computed findings only
- drill-through into existing MCP Hub editors
- no inline remediation
- no heuristic risk scoring

## Scope

This slice covers:

- one normalized backend findings feed for MCP Hub governance findings
- a read-only `Audit` tab with counts, filters, and finding rows
- drill-through metadata that can open the correct MCP Hub tab/editor context
- all visible objects across scopes, with scope badges and filter chips

This slice does not cover:

- inline fixes or bulk actions
- subjective "too broad" risk heuristics
- historical audit timelines
- new enforcement semantics

## Review Corrections

### 1. Drill-through needs a real MCP Hub navigation contract

The current [McpHubPage.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx)
only stores a local `activeTab` string. It does not yet expose a way for one
tab to open another tab focused on a specific object.

This slice therefore includes a lightweight MCP Hub-local navigation model:

- `activeTab`
- `selectedObjectKind`
- `selectedObjectId`

The audit view will emit navigation intents into that model instead of trying
to invent route-level deep links immediately.

### 2. Assignment blockers need a non-throwing inspection path

The current assignment hardening in
[mcp_hub_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_service.py)
is write-time and exception-based via
`validate_multi_root_assignment_readiness(...)`.

That is correct for mutation, but the audit view needs listable blocker state.

This slice adds a non-throwing assignment inspection helper that mirrors the
same logic and returns a structured blocker summary instead of raising.

### 3. External server issues and external binding issues come from different sources

`ExternalServerResponse` already exposes listable configuration state:

- `runtime_executable`
- `auth_template_present`
- `auth_template_valid`
- `auth_template_blocked_reason`

Those are sufficient for `external_server_configuration_issue`.

Binding problems are different. They are assignment-scoped and emerge from
effective external access, not raw binding rows. This slice therefore models:

- `external_server_configuration_issue`
  - derived from external server list state
- `external_binding_issue`
  - derived from assignment-scoped effective external access inspection

### 4. The audit feed must be backend-composed, not client fan-out

The audit view should not load five existing tabs and compose findings in the
browser. That would be slow and would drift from enforcement logic.

This slice therefore adds a single backend-composed audit endpoint and one
shared finding DTO.

### 5. Workspace-source readiness must stay labeled as multi-root readiness

The new `readiness_summary` on workspace sources is advisory and specifically
about multi-root readiness under `workspace_root` semantics.

The audit view must preserve that nuance. It should not present those warnings
as universal "broken" states.

### 6. Root causes and affected consumers should both be visible

The same underlying issue may appear in three places:

- a shared workspace overlap warning
- a workspace-set readiness warning
- an assignment validation blocker

That is useful, but it can look like duplication. This slice adds lightweight
relationship metadata so a finding can indicate the related upstream/downstream
object when known.

## Finding Model

The audit feed should normalize all findings into one shared DTO.

Recommended fields:

- `finding_type`
- `severity`
- `scope_type`
- `scope_id`
- `object_kind`
- `object_id`
- `object_label`
- `message`
- `details`
- `navigate_to`
- `related_object_kind`
- `related_object_id`
- `related_object_label`

Recommended enums:

- `severity`
  - `error`
  - `warning`
- `finding_type`
  - `assignment_validation_blocker`
  - `workspace_source_readiness_warning`
  - `shared_workspace_overlap_warning`
  - `external_server_configuration_issue`
  - `external_binding_issue`

`navigate_to` should stay MCP-Hub-local and explicit, for example:

- `tab`
- `object_kind`
- `object_id`

## Concrete Finding Families

### Assignment Validation Blockers

Derived from the new non-throwing assignment inspection helper that mirrors
multi-root readiness validation.

Initial blocker coverage:

- `assignment_multi_root_overlap`
- `assignment_workspace_unresolvable`
- `assignment_workspace_source_invalid`

These are `error` severity findings.

### Workspace Source Readiness Warnings

Derived from the existing workspace-set `readiness_summary`.

Initial warning coverage:

- `multi_root_overlap_warning`
- `workspace_unresolvable_warning`

These remain `warning` severity findings and should be labeled as:

- `Multi-root readiness warning`

### Shared Workspace Overlap Warnings

Derived from shared workspace `readiness_summary` and same-scope / parent-scope
visibility rules.

These are `warning` severity findings and represent a root-cause style object
finding.

### External Server Configuration Issues

Derived from listable external server state.

Initial issue coverage:

- missing required slot secret
- invalid auth template
- no auth template
- unsupported auth-template transport target
- not runtime executable

These are usually `error` severity findings for managed servers. Legacy
inventory rows can be excluded or downgraded if needed, but v1 should focus on
managed MCP Hub state.

### External Binding Issues

Derived from assignment-scoped effective external access inspection, not raw
binding rows.

Initial issue coverage:

- required slot not granted
- missing required slot secret at assignment-effective level
- slot disabled by assignment when required for expected use
- binding targets a non-usable managed server state

These are assignment-scoped and should carry `related_object_*` metadata back
to the underlying server where useful.

## Backend Architecture

Add one service entry point:

- `list_governance_audit_findings(...)`

This should live in
[mcp_hub_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_service.py)
and compose existing helpers rather than re-implementing logic.

Recommended helper breakdown:

- `inspect_assignment_governance_findings(...)`
- `get_workspace_set_readiness_summary(...)`
- `get_shared_workspace_readiness_summary(...)`
- external-server list inspection based on current server response state
- assignment external-access inspection for binding issues

Important rules:

- all visibility filtering stays server-side
- the service returns only findings the acting user can already see
- stable sorting should group `error` before `warning`, then by scope/object

## API Shape

Add one MCP Hub endpoint:

- `GET /api/v1/mcp/hub/audit/findings`

Recommended query params:

- `severity`
- `finding_type`
- `object_kind`
- `scope_type`

These are filter conveniences only. The UI can also filter client-side after
loading everything, but the endpoint should support basic server-side filters so
the data contract is reusable later.

## UI Design

Add a new top-level MCP Hub tab:

- `Audit`

### Top Summary Row

Show:

- total findings
- total errors
- total warnings

### Filters

Use compact filter chips or selects for:

- scope
- severity
- finding type
- object kind

Default:

- all visible findings

### Main List

Each finding row should show:

- severity badge
- main message
- object label
- scope badge
- finding type label
- related object label when present
- `Open` action

### Open Action

`Open` should update the MCP Hub-local navigation context:

- switch tabs
- focus the target object if the destination tab supports it

This slice only needs the state model and plumbed props/context. It does not
need full route/query-param deep linking.

## Initial Destination Mapping

- assignment blockers -> `Assignments`
- workspace-source readiness warnings -> `Workspace Sets`
- shared-workspace overlap warnings -> `Shared Workspaces`
- external server configuration issues -> `Credentials`
- external binding issues -> `Assignments`

## Relationship Semantics

Use `related_object_*` fields to keep findings understandable:

- assignment blocker can point to a workspace set
- workspace-set warning can point to a shared workspace
- external binding issue can point to an external server

This is not meant to build a full graph. It is just enough to reduce apparent
duplication in the audit list.

## Testing Strategy

Backend coverage should include:

- normalized finding DTOs from each source family
- assignment blockers returned without raising
- external server issues derived from current list state
- external binding issues derived from assignment-effective inspection
- visibility and filter behavior

Frontend coverage should include:

- Audit tab renders counts and finding rows
- filters narrow the visible findings
- `Open` action switches MCP Hub tab/context correctly
- multi-root readiness findings remain labeled as advisories

## Recommendation

Keep v1 of the governance audit view as a backend-composed, read-only finding
dashboard over concrete truths the branch already knows how to derive.

That gives users one place to inspect governance problems without weakening the
existing enforcement model or introducing a second editing surface.
