# MCP Hub Clear Broken Path Scope Inline Action Design

Date: 2026-03-11
Status: Approved for planning

## Goal

Add one new safe inline remediation action in the MCP Hub `Audit` tab:

- clear a broken `path_scope_object_id` reference

This extends the existing inline remediation model beyond `Deactivate server`
while preserving the same narrow safety boundary:

- one exact target object
- one exact deterministic mutation
- no secret writes
- no membership changes
- no source-mode changes
- no policy-content edits

## Scope

This slice covers two consumer kinds:

- `policy_assignment`
- `permission_profile`

Eligible findings must be:

- `finding_type === "broken_object_reference"`
- `details.reference_field === "path_scope_object_id"`
- `details.reference_object_kind === "path_scope_object"`

Eligible broken-reference reasons:

- `missing_reference`
- `inactive_reference`
- `scope_incompatible_reference`

This slice does not cover:

- `workspace_set_object_id` remediation
- replacement of the broken reference with a new object
- any mutation of inline policy content
- any backend audit-remediation endpoint

## Why This Is Safe

Unlike `workspace_set_object_id`, clearing `path_scope_object_id` does not force a
source-mode change or reactivate preserved membership data. It is a direct
`field -> null` mutation for both supported consumer types.

The underlying update flows already exist:

- assignment update
- permission profile update

So the audit tab only needs to map a structured finding to an exact existing
mutation call.

## Action Model

Add one new inline action kind:

- `clear_path_scope_reference`

The action descriptor should be a discriminated union alongside the existing:

- `deactivate_external_server`

Suggested action shape:

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

## Eligibility Rules

Inline mutation eligibility must be driven only by structured finding data.

Return the new action only when:

- `finding.finding_type === "broken_object_reference"`
- `finding.object_kind === "policy_assignment"` or `finding.object_kind === "permission_profile"`
- `details.reference_field === "path_scope_object_id"`
- `details.reference_object_kind === "path_scope_object"`

Return `null` otherwise.

No message-string parsing should be used for mutation eligibility.

## Mutation Mapping

Assignment:

- call the existing assignment update client with:
  - `{ path_scope_object_id: null }`

Permission profile:

- call the existing permission profile update client with:
  - `{ path_scope_object_id: null }`

No other fields should be sent.

This is important because the action must remove only the broken object
reference, not modify inline path policy or inherited profile behavior.

## UX And Messaging

Button label:

- `Clear broken path scope`

Confirmation copy should be object-kind-specific.

For assignments:

- title:
  - `Clear the broken path scope reference from this assignment?`
- description:
  - `This removes the broken path scope object reference only. Inline policy and other assignment settings stay unchanged.`

For permission profiles:

- title:
  - `Clear the broken path scope reference from this permission profile?`
- description:
  - `This removes the broken path scope object reference only. Policy content stays unchanged.`

Success copy should also be object-kind-specific:

- assignment:
  - `Broken path scope cleared from assignment.`
- profile:
  - `Broken path scope cleared from permission profile.`

Failure copy should be explicit but generic:

- assignment:
  - `Failed to clear broken path scope from assignment.`
- profile:
  - `Failed to clear broken path scope from permission profile.`

## Audit Tab Behavior

The audit tab should continue to:

1. render the finding
2. show `Open`
3. show the inline action when eligible
4. confirm before mutating
5. refresh the audit feed after success
6. show inline success/error feedback

The refreshed audit feed remains the source of truth. If the finding still
exists after refresh, the row stays visible.

## Testing

### Helper tests

- assignment broken path-scope reference -> action descriptor
- profile broken path-scope reference -> action descriptor
- broken workspace-set reference -> `null`

### Audit tab tests

- button renders for eligible assignment broken-reference finding
- button renders for eligible profile broken-reference finding
- assignment action calls assignment update with `path_scope_object_id: null`
- profile action calls profile update with `path_scope_object_id: null`
- success refreshes findings and shows correct success message
- failure shows correct error message

## Out Of Scope

- clearing broken `workspace_set_object_id`
- replacing broken references
- backend audit remediation endpoint
- bulk audit actions
- any new finding family

