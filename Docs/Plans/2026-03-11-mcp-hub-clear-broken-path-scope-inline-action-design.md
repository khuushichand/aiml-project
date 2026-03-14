# MCP Hub Clear Broken Path Scope Inline Action Design

Date: 2026-03-11
Status: Implemented

## Goal

Add one new safe inline remediation action in the MCP Hub `Audit` tab:

- clear a broken `path_scope_object_id` reference

This extends the audit view beyond read-only remediation guidance and the
existing `Deactivate server` action, while keeping the scope strictly within the
same low-risk mutation boundary:

- one exact target object
- one exact deterministic mutation
- no secret writes
- no membership edits
- no source-mode changes
- no policy-content rewrites

## Scope

Eligible consumer objects:

- `policy_assignment`
- `permission_profile`

Eligible findings:

- `finding_type === "broken_object_reference"`
- `details.reference_field === "path_scope_object_id"`
- `details.reference_object_kind === "path_scope_object"`

Supported broken-reference reasons:

- `missing_reference`
- `inactive_reference`
- `scope_incompatible_reference`

Out of scope:

- `workspace_set_object_id` remediation
- replacement of the broken reference with another object
- any backend audit-remediation endpoint
- any bulk or multi-choice audit action

## Why This Is Safe

Clearing `path_scope_object_id` is a direct `field -> null` mutation for both
supported consumer types.

It does not:

- reactivate preserved inline workspace membership
- force a source-mode switch
- mutate inline path policy
- alter approval policy or profile linkage

That makes it materially safer than `workspace_set_object_id` remediation under
the current branch semantics.

## Action Model

Extend the existing audit inline-action descriptor into a discriminated union.

Suggested shape:

```ts
type GovernanceAuditInlineAction =
  | {
      kind: "deactivate_external_server"
      label: string
      object_id: string
      confirm_title?: string | null
      confirm_description?: string | null
      success_message?: string | null
      error_message?: string | null
    }
  | {
      kind: "clear_path_scope_reference"
      label: string
      object_kind: "policy_assignment" | "permission_profile"
      object_id: string
      confirm_title?: string | null
      confirm_description?: string | null
      success_message?: string | null
      error_message?: string | null
    }
```

This avoids hardcoding action-specific success/error text into the audit tab and
keeps the component from turning into a branching mutation switchboard.

## Eligibility Rules

Inline mutation eligibility must be derived only from structured finding data.

Return the new action only when all of these are true:

- `finding.finding_type === "broken_object_reference"`
- `finding.object_kind === "policy_assignment"` or `finding.object_kind === "permission_profile"`
- `details.reference_field === "path_scope_object_id"`
- `details.reference_object_kind === "path_scope_object"`
- `finding.object_id` is present

Return `null` for:

- broken workspace-set references
- generic blockers
- readiness warnings
- any finding that would require inferring intent from message strings

No message-string parsing should be used for action eligibility.

## Mutation Mapping

Reuse the existing MCP Hub client update functions.

For assignments:

- call `updatePolicyAssignment(id, { path_scope_object_id: null })`

For permission profiles:

- call `updatePermissionProfile(id, { path_scope_object_id: null })`

This slice should remain UI-only. No new backend endpoint is needed.

The payload must remain minimal:

- only `path_scope_object_id: null`

No other field should be sent.

That ensures the action removes only the broken path-scope object reference and
does not implicitly alter any other path-policy state.

## UX And Messaging

Button label:

- `Clear broken path scope`

### Assignment confirmation

- title:
  - `Clear the broken path scope reference from this assignment?`
- description:
  - `This removes the broken path scope object reference only. Inline policy and other assignment settings stay unchanged.`

### Permission profile confirmation

- title:
  - `Clear the broken path scope reference from this permission profile?`
- description:
  - `This removes the broken path scope object reference only. Policy content stays unchanged.`

### Success messages

- assignment:
  - `Broken path scope cleared from assignment.`
- profile:
  - `Broken path scope cleared from permission profile.`

### Error messages

- assignment:
  - `Failed to clear broken path scope from assignment.`
- profile:
  - `Failed to clear broken path scope from permission profile.`

This object-kind-specific copy is important so the user understands what is
being changed and what is not.

## Audit Tab Behavior

The audit tab should continue to:

1. render the finding row
2. render `Open`
3. render the inline action only when eligible
4. confirm before mutating
5. show pending state while the mutation runs
6. refresh the audit feed after success
7. show inline success/error feedback

The refreshed audit feed remains the source of truth. If the finding still
exists after refresh, the row remains visible.

## Testing

### Helper tests

- assignment broken path-scope reference -> `clear_path_scope_reference`
- profile broken path-scope reference -> `clear_path_scope_reference`
- broken workspace-set reference -> `null`

### Audit tab tests

- assignment broken-reference finding renders `Clear broken path scope`
- permission-profile broken-reference finding renders `Clear broken path scope`
- assignment action calls `updatePolicyAssignment(id, { path_scope_object_id: null })`
- profile action calls `updatePermissionProfile(id, { path_scope_object_id: null })`
- assignment success refreshes findings and shows assignment-specific success text
- profile success refreshes findings and shows profile-specific success text
- failure shows the correct object-kind-specific error text

## Out Of Scope

- clearing broken `workspace_set_object_id`
- replacing broken references
- backend audit-remediation endpoint
- bulk actions
- confirmation flows with user choices
