# MCP Hub Broken Reference Audit Findings Design

Date: 2026-03-11
Status: Approved for planning

## Goal

Add a dedicated audit finding family for broken MCP Hub object references so the
Audit tab can distinguish exact broken-reference problems from generic blocker
or readiness findings.

This slice is a prerequisite for future safe inline actions beyond
`Deactivate server`.

## Final Scope

This slice covers one new audit finding family:

- `broken_object_reference`

Initial direct stored references covered:

- `policy_assignment.path_scope_object_id`
- `policy_assignment.workspace_set_object_id`
- `permission_profile.path_scope_object_id`

Broken-reference reasons covered:

- `missing_reference`
- `inactive_reference`
- `scope_incompatible_reference`

This slice does not cover:

- inherited/effective reference inspection
- inline remediation mutations
- runtime policy changes
- broader reference-health checks across all MCP Hub object types

## Review Corrections

### 1. Workspace-set missing references are defensive, not the mainline case

Under the current branch, workspace-set deletion is blocked while referenced,
but path-scope deletion is not.

That means:

- `missing_reference` is a normal realistic case for `path_scope_object_id`
- `workspace_set_object_id` missing-reference support should still exist
  defensively
- but tests and messaging should not imply it is the usual workspace-set failure
  mode under current CRUD rules

### 2. Use dedicated non-throwing inspection helpers

The current validators raise:

- `ResourceNotFoundError`
- `BadRequestError`

That is correct for mutation paths, but the audit view needs exact typed results,
not exception parsing.

This slice should add dedicated inspection helpers such as:

- `inspect_path_scope_object_reference(...)`
- `inspect_workspace_set_object_reference(...)`

These should return structured inspection results or `null`.

### 3. Inspect only direct stored references in v1

Assignments can inherit references indirectly through profiles and path-scope
resolution layers. If this slice inspects effective references, one broken
profile reference would fan out into many duplicate assignment findings.

So the first slice should inspect only direct stored reference fields:

- assignment row’s own `path_scope_object_id`
- assignment row’s own `workspace_set_object_id`
- profile row’s own `path_scope_object_id`

### 4. Missing referenced rows cannot always supply scope or label metadata

For `missing_reference`, the referenced row may not exist.

So:

- always include the stored `reference_object_id`
- always include `reference_object_kind`
- include `reference_label` only when available
- allow `reference_scope_type` and `reference_scope_id` to be null

### 5. The new finding family must be wired through both backend and UI enums

This slice requires:

- backend finding DTO support
- frontend finding type enum support
- fixed section ordering
- human label
- remediation-rule branch

Without that, the finding will exist only partially.

## Broken-Reference Finding Model

New finding family:

- `finding_type: "broken_object_reference"`

Severity:

- always `error`

Why:

- a broken stored reference means the current configuration is structurally
  invalid
- even if the user has not attempted a new write recently

Covered consumer objects:

- `policy_assignment`
- `permission_profile`

Broken-reference reasons:

- `missing_reference`
- `inactive_reference`
- `scope_incompatible_reference`

## Detection Rules

The audit service should inspect only direct stored fields.

### Assignment reference inspection

Inspect:

- `path_scope_object_id`
- `workspace_set_object_id`

For each non-null reference:

1. fetch the referenced object
2. if row missing:
   - return `missing_reference`
3. if row inactive:
   - return `inactive_reference`
4. if row exists but violates current MCP Hub scope-reference rules:
   - return `scope_incompatible_reference`
5. otherwise:
   - return `null`

### Permission-profile reference inspection

Inspect:

- `path_scope_object_id`

Apply the same result rules.

## Inspection Helper Shape

Use separate non-throwing helpers in the MCP Hub service layer.

Suggested result shape:

```python
{
  "reference_field": "path_scope_object_id",
  "reference_object_kind": "path_scope_object",
  "reference_object_id": "17",
  "reference_reason": "inactive_reference",
  "reference_label": "Docs Paths",
  "reference_scope_type": "team",
  "reference_scope_id": 4,
}
```

Or `None` when valid.

Rules:

- no exceptions for normal audit flow
- no message-string parsing
- reuse the same scope-compatibility rules as write-time validation

## Audit Finding Shape

Each finding should include:

- `finding_type: "broken_object_reference"`
- `severity: "error"`
- consumer identity:
  - `object_kind`
  - `object_id`
  - `object_label`
- consumer navigation target
- structured details:
  - `reference_field`
  - `reference_object_kind`
  - `reference_object_id`
  - `reference_reason`
  - `reference_scope_type`
  - `reference_scope_id`
  - `reference_label`

Example messages:

- `Assignment references a missing path scope object.`
- `Assignment references an inactive workspace set object.`
- `Permission profile references a path scope object from an incompatible owner scope.`

## Navigation And Relationship Metadata

Primary navigation should stay on the consumer object:

- assignments -> `Assignments`
- permission profiles -> `Profiles`

Related-object metadata should point to the broken referenced object:

- `related_object_kind`
- `related_object_id`
- `related_object_label`

Rules:

- if referenced row exists, use its name/label when available
- if referenced row is missing, fall back to the stored object id

This keeps audit summaries and future inline remediation logic useful.

## UI Changes

UI additions required:

- add `broken_object_reference` to finding type enums
- add fixed grouping order entry
- add a human label such as:
  - `Broken references`
- add remediation suggestion rules for the new structured details

Suggested remediation examples:

### Missing path-scope reference

1. Open the affected assignment or profile.
2. Clear or replace the broken path scope reference.
3. Save again and re-run the audit.

### Inactive workspace-set reference

1. Open the affected assignment.
2. Reactivate or replace the referenced workspace set.
3. Save again and re-run the audit.

### Scope-incompatible reference

1. Open the affected assignment or profile.
2. Replace the reference with an object from the same or parent scope.
3. Save again and re-run the audit.

This slice should still keep the only inline mutation action as:

- `Deactivate server`

## Testing Focus

Backend:

- assignment direct `path_scope_object_id` missing -> finding
- assignment direct `path_scope_object_id` inactive -> finding
- assignment direct `path_scope_object_id` scope-incompatible -> finding
- assignment direct `workspace_set_object_id` inactive -> finding
- assignment direct `workspace_set_object_id` scope-incompatible -> finding
- permission profile direct `path_scope_object_id` missing -> finding
- no finding when reference is valid

Frontend:

- new finding type is grouped and labeled correctly
- remediation text uses structured broken-reference details
- related-object labels render correctly for missing and non-missing references
- `Open` still targets the consumer object

## Follow-Up Enabled By This Slice

Once this finding family exists, the next safe inline remediation candidate can
be evaluated more rigorously:

- clear broken `path_scope_object_id`

But only after confirming the action stays one exact deterministic mutation for
the eligible consumer type.
