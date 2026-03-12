# MCP Hub Broken Profile Reference Inline Action Design

Date: 2026-03-11
Status: Implemented

## Goal

Add the next safe audit remediation slice after broken path-scope clears:

- detect broken assignment `profile_id` references as dedicated audit findings
- allow one deterministic inline action to clear the broken permission-profile reference

This extends the current `broken_object_reference` family without broadening the
mutation model beyond the existing safety boundary:

- one exact target object
- one exact deterministic mutation
- no source-mode changes
- no workspace membership edits
- no policy-content edits

## Scope

Covered consumer object:

- `policy_assignment`

Covered direct stored reference:

- `profile_id`

Covered broken-reference reasons:

- `missing_reference`
- `inactive_reference`
- `scope_incompatible_reference`

Out of scope:

- any inherited/effective profile usage
- any permission-profile-to-profile references
- any backend audit-remediation endpoint
- any mutation of `workspace_set_object_id`

## Why This Is Safe

Unlike `workspace_set_object_id`, clearing `profile_id` is a direct one-field
mutation on the assignment row:

```json
{ "profile_id": null }
```

It does not:

- switch workspace source mode
- reactivate preserved workspace rows
- rewrite inline policy
- modify approvals or bindings

That makes it analogous in safety to clearing `path_scope_object_id`.

## Finding Model

Reuse the existing audit family:

- `finding_type: "broken_object_reference"`

Add one more structured broken-reference case for assignments:

- `details.reference_field === "profile_id"`
- `details.reference_object_kind === "permission_profile"`

Required detail fields:

- `reference_field`
- `reference_object_kind`
- `reference_object_id`
- `reference_reason`
- `reference_scope_type`
- `reference_scope_id`
- `reference_label` when available

Navigation stays on the consumer:

- `Assignments`

Related-object metadata should point at the broken permission profile when
available.

## Detection Rules

Use a dedicated non-throwing inspection helper in MCP Hub service code:

```python
inspect_permission_profile_reference(
    profile_id: int | None,
    target_scope_type: str,
    target_scope_id: int | None,
) -> dict[str, Any] | None
```

Behavior:

1. `profile_id is None` -> `None`
2. missing row -> `missing_reference`
3. inactive row -> `inactive_reference`
4. present but scope-incompatible with the assignment owner scope -> `scope_incompatible_reference`
5. otherwise -> `None`

Scope compatibility should reuse the same same-scope-or-parent rule already used
for other MCP Hub object references.

## Action Model

Extend the current client-side audit action union with one more deterministic
case:

```ts
{
  kind: "clear_permission_profile_reference"
  label: "Clear broken profile"
  object_kind: "policy_assignment"
  object_id: string
  confirm_title: string
  confirm_description: string
  success_message: string
  error_message: string
}
```

Eligibility must be fully structured-data-driven:

- `finding_type === "broken_object_reference"`
- `object_kind === "policy_assignment"`
- `details.reference_field === "profile_id"`
- `details.reference_object_kind === "permission_profile"`

No message-string parsing should be used for action eligibility.

## Mutation Mapping

Reuse the existing MCP Hub client update function:

- `updatePolicyAssignment(assignmentId, { profile_id: null })`

No backend audit-remediation endpoint is needed.

## Copy

Action label:

- `Clear broken profile`

Confirmation:

- title:
  - `Clear the broken permission profile reference from this assignment?`
- description:
  - `This removes the broken permission profile reference only. Inline policy and other assignment settings stay unchanged.`

Feedback:

- success:
  - `Broken permission profile cleared from assignment.`
- error:
  - `Failed to clear broken permission profile from assignment.`

## UI Behavior

The new finding should:

- appear under `Broken references`
- get specific remediation text
- optionally show the new inline action

The action remains visually parallel to:

- `Deactivate server`
- `Clear broken path scope`

## Testing

Backend:

- broken `profile_id` missing -> structured `broken_object_reference`
- broken `profile_id` inactive -> structured `broken_object_reference`
- broken `profile_id` scope-incompatible -> structured `broken_object_reference`
- valid `profile_id` -> no finding

Frontend:

- helper returns `clear_permission_profile_reference` only for eligible findings
- action calls `updatePolicyAssignment(id, { profile_id: null })`
- success refreshes the audit feed
- failure leaves the finding visible and shows error feedback

## Non-Goals

This slice does not:

- fix broken references automatically on the backend
- add bulk cleanup
- clear workspace-set references
- mutate permission profiles themselves
