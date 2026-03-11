# MCP Hub Multi-Root Overlap Hardening Design

Date: 2026-03-11
Status: Approved for planning

## Goal

Prevent assignments from becoming multi-root-eligible when their effective
workspace bundle contains overlapping trusted roots or unresolved workspace ids.

This slice is intentionally narrow:

- enforcement is assignment-scoped, not global
- overlap blocking applies only when an assignment is actually multi-root-eligible
- validation runs for both inline and named workspace sources
- runtime semantics stay unchanged except where shared helpers are reused

## Scope

This slice covers:

- save-time validation for assignments that become multi-root-eligible
- overlap detection across effective workspace bundles
- save-time rejection of unresolved bundle members for active assignment sources
- structured error payloads for assignment editing UX

This slice does not cover:

- global overlap bans on workspace-set objects
- global overlap bans on shared workspace registry entries
- changes to runtime approval semantics
- broader workspace trust-model migrations

## Current Gap

The branch now supports true multi-root path execution, but overlap handling is
still mostly runtime-only:

- overlapping roots are permitted in workspace sets and shared registry entries
- unresolved bundle members can still be stored and only fail later
- inline workspace membership can remain a bypass if validation only runs on
  assignment row writes

That means a user can save an assignment that looks valid in MCP Hub but can
never execute multi-root safely at runtime.

## Review Corrections

### 1. Validation must use the assignment's effective path mode

Assignments become multi-root-eligible based on effective path policy, not just
their local inline policy.

Validation must therefore use the same effective path-layer order already used
by the resolver:

1. profile-linked path-scope object
2. profile inline path fields
3. assignment-linked path-scope object
4. assignment inline path fields
5. assignment override path fields

Only after that merge can the validator decide whether the effective
`path_scope_mode` is `workspace_root`.

### 2. Validation must run on assignment membership writes too

Assignment state is currently mutated through more than one write path:

- assignment create/update
- switching `workspace_source_mode`
- setting `workspace_set_object_id`
- syncing inline assignment workspace ids

If validation runs only on assignment row updates, inline workspace writes
remain a bypass. The validator must run after any mutation that changes the
active workspace source or the active path-source readiness for that assignment.

### 3. Validation must use the assignment's effective workspace trust source

The branch now supports both:

- `user_local`
- `shared_registry`

Save-time validation must follow the assignment's effective trust source, not
just infer from owner scope alone. That keeps save-time behavior aligned with
runtime resolution for named workspace sets and parent-scope references.

### 4. Only the active workspace source should be validated

Assignments already preserve inactive data when switching between:

- inline vs named path scope
- inline vs named workspace source

This slice keeps that behavior:

- validate only the currently selected workspace source
- preserve inactive inline rows in storage
- do not delete inactive source data during validation failures

### 5. Object-level overlap warnings can be informational only

Blocking overlap globally on workspace-set objects or shared registry entries is
out of scope for this slice. At most, object views may surface a read-only
warning later. Hard blocking belongs only to assignments that actually become
multi-root-eligible.

## Multi-Root Eligibility

An assignment is multi-root-eligible only when all of the following are true:

- the effective active workspace source resolves to more than one workspace id
- the effective path mode is `workspace_root`
- the active workspace source is internally valid

An assignment is not multi-root-eligible when:

- effective workspace bundle size is `0` or `1`
- effective path mode is `cwd_descendants`
- effective path mode is unset or otherwise not compatible with multi-root

Only multi-root-eligible assignments are subject to overlap hardening.

## Overlap Semantics

Overlap must use the same canonical containment semantics already used by path
enforcement:

- canonicalize each resolved workspace root
- two roots conflict if:
  - they are equal
  - one is an ancestor of the other

Examples:

- `/repo` and `/repo/docs` -> conflict
- `/repo-a` and `/repo-b` -> allowed
- same absolute root under two different workspace ids -> conflict

The validator should fail on the first conflicting pair and return both the
workspace ids and canonical roots involved.

## Validation Model

Add an assignment-scoped readiness validator, for example:

- `validate_multi_root_assignment_readiness(...)`

Inputs should include enough information to reproduce runtime meaning:

- assignment id when present
- actor user id
- assignment owner scope
- effective workspace source mode
- active inline workspace ids or active `workspace_set_object_id`
- effective path mode
- effective workspace trust source

Validation flow:

1. resolve the active workspace source only
2. if active source is empty/invalid, fail with structured error
3. if active workspace count <= 1, pass without overlap checks
4. if effective path mode is not `workspace_root`, pass without overlap checks
5. resolve trusted roots for every active workspace id through the effective
   trust source
6. if any workspace id is unresolved, fail with structured error
7. compare every pair of canonical roots for overlap
8. if any pair overlaps, fail with structured error
9. otherwise pass

This is really assignment readiness validation, not just overlap validation.

## Enforcement Boundary

Validation must happen in the backend write path, not only in the UI.

It should run after any mutation that changes one of:

- the active workspace source
- the active workspace members
- the effective path mode

That means at minimum:

- assignment create
- assignment update
- assignment inline workspace sync
- switching `workspace_source_mode`
- updating `workspace_set_object_id`
- any assignment write that changes path policy inputs

## Error Model

Return structured validation failures that the UI can render without parsing
English.

Recommended error codes:

- `assignment_multi_root_overlap`
- `assignment_workspace_unresolvable`
- `assignment_workspace_source_invalid`

Recommended payload fields:

- `message`
- `code`
- `workspace_source_mode`
- `workspace_trust_source`
- `conflicting_workspace_ids`
- `conflicting_workspace_roots`
- `unresolved_workspace_ids`

That lets the assignment editor show exactly what the user needs to fix.

## MCP Hub UI Impact

No new top-level UI surface is required.

Assignment editing should:

- surface structured overlap/unresolved-workspace validation errors near the
  workspace source controls
- keep inactive inline workspace rows preserved when named source is selected
- keep inactive named source wiring preserved when inline source is selected

Effective preview can remain unchanged for this slice, though it may later gain
an informational warning for overlapping named workspace sets.

## Testing Strategy

Backend coverage should include:

- inline workspace source + `workspace_root` -> overlap rejected
- named workspace source + `workspace_root` -> overlap rejected
- same bundle in `cwd_descendants` -> save allowed
- unresolved workspace id -> save rejected
- identical canonical roots under different workspace ids -> rejected
- disjoint roots -> allowed
- switching from single-workspace to multi-workspace -> validation triggers
- switching effective path mode into `workspace_root` -> validation triggers

Frontend coverage should include:

- assignment editor surfaces structured overlap error
- assignment editor surfaces unresolved-workspace error
- switching inline/named source preserves inactive data
- only the active source is validated on save

## Recommendation

Keep this slice tightly scoped to assignment save validation.

That gives immediate safety value:

- no new runtime ambiguity
- no global over-restriction on reusable objects
- no inline-source bypass

It also creates a clean base for any later optional read-only overlap warnings
on workspace-set objects or shared registry entries.
