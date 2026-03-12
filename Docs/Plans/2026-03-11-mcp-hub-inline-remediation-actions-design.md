# MCP Hub Inline Remediation Actions Design

Date: 2026-03-11
Status: Implemented

## Goal

Add the first inline remediation action to the MCP Hub `Audit` tab, but only
for findings that map to one exact target object and one exact low-risk,
reversible mutation.

This slice is intentionally narrower than the initial brainstorming list.

## Final Scope

This slice covers:

- one inline remediation action family:
  - `external_server_configuration_issue`
  - target object kind: `external_server`
  - safe mutation: deactivate the managed external server
- reuse of the existing external-server update endpoint
- lightweight confirmation and inline success/error feedback
- refresh of the audit feed after the mutation

This slice does not cover:

- assignment membership changes
- assignment policy-content edits
- clearing workspace-set references
- clearing path-scope references
- binding changes
- secret writes
- multi-option remediation flows
- bulk actions

## Review Corrections

### 1. Workspace-set reference clearing is not a single safe mutation

In the current branch, clearing a named workspace-set reference also requires a
coordinated `workspace_source_mode` change. That can reactivate preserved inline
workspace rows and is no longer a simple one-field reversible fix.

So:

- `Clear broken workspace set reference` is out of scope for v1

### 2. The audit feed does not yet expose dedicated broken-reference findings

The current audit view emits:

- `assignment_validation_blocker`
- `workspace_source_readiness_warning`
- `shared_workspace_overlap_warning`
- `external_server_configuration_issue`
- `external_binding_issue`

It does not currently emit dedicated structured findings like:

- `broken_path_scope_reference`
- `broken_workspace_set_reference`

So mutating assignment reference fields from the audit tab would require
guesswork from generic blocker text. That is out of scope for a safe first pass.

### 3. Mutating actions must be driven by structured finding data only

Read-only remediation suggestions may use message/detail fallbacks. Inline
mutations should not.

Eligibility must require:

- exact `finding_type`
- exact `object_kind`
- exact `object_id`
- deterministic mutation payload

### 4. `Deactivate server` is the clean v1 candidate

For managed external servers that are not runtime-executable, the existing
mutation is:

- local to one object
- reversible
- does not write secrets
- does not rewrite auth templates
- does not alter assignment policy content

That makes it the right first inline action.

## Remediation Action Model

An audit row may render:

- `Open`
- one optional inline action button when the finding is eligible

The action is shown only when all of the following are true:

- the finding maps to one exact object
- the mutation is one exact safe operation
- the mutation is reversible
- the mutation does not require user choice

Recommended UI behavior:

- keep the action secondary to `Open`
- use an explicit label:
  - `Deactivate server`
- include a lightweight confirmation step
- show pending state during mutation
- show inline success/error feedback after completion

## Initial Eligible Finding Family

### `external_server_configuration_issue`

Eligibility:

- `finding_type === "external_server_configuration_issue"`
- `object_kind === "external_server"`
- finding target is a managed external server
- server is currently runtime-non-executable or otherwise blocked by config

Exact mutation:

- call existing external server update mutation with:
  - `enabled: false`

Suggested action label:

- `Deactivate server`

Rationale:

- object-local
- deterministic
- reversible
- safe compared with editing auth templates, secrets, or bindings

## Explicitly Deferred Actions

These are intentionally out of scope for this first pass:

### Assignment reference clearing

Deferred until the backend emits dedicated structured broken-reference findings
and the mutation is proven to be a single deterministic safe update.

Examples deferred:

- `Clear broken workspace set reference`
- `Clear broken path scope reference`

### Binding and membership mutations

Deferred because they modify assignment-level access semantics and can carry
more surprising side effects.

Examples deferred:

- disable binding
- remove workspace membership
- switch assignment source modes

## UI And Interaction Design

Each eligible finding row should render:

- existing finding content
- existing `Suggested next steps`
- existing `Open`
- optional inline action button

Action flow:

1. user clicks `Deactivate server`
2. lightweight confirmation appears
3. on confirm, the action runs
4. success message is shown
5. audit findings reload

Failure behavior:

- keep the finding row visible
- show the returned API error inline
- do not optimistically hide the finding

## Action Helper Structure

Use one pure helper that maps findings to action descriptors.

Suggested API:

```ts
type GovernanceAuditInlineAction = {
  label: string
  confirm_title?: string | null
  confirm_description?: string | null
  kind: "deactivate_external_server"
  object_id: string
}

buildAuditInlineAction(finding): GovernanceAuditInlineAction | null
```

Rules:

- return `null` for all non-eligible findings
- use structured finding data only
- no message-string heuristics for mutation eligibility

## API Behavior

Do not add a special audit-mutation endpoint in v1.

Reuse the existing MCP Hub mutation endpoint for managed external servers.

The audit tab should:

- resolve the inline action descriptor
- execute the existing update mutation with `enabled: false`
- refresh audit findings on success

## Testing Focus

### Helper tests

- eligible external server finding returns `Deactivate server`
- non-eligible findings return `null`

### UI tests

- action button renders only for eligible findings
- confirmation appears before mutation
- success triggers audit refresh
- failure shows inline error feedback
- `Open` remains unchanged

## Follow-Up Slices

Future inline actions should only be added after the audit feed exposes exact
structured findings for them.

Likely future candidates:

- clear broken path-scope reference
- clear broken workspace-set reference

But only after:

- the finding family is explicit
- the mutation is one exact deterministic update
- no hidden source-mode or policy-content side effects remain
