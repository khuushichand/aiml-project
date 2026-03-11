# MCP Hub Path Allowlist Prefixes Design

Date: 2026-03-10
Status: Implemented

## Summary

The next MCP Hub path-scope slice should add a small inline allowlist model for local filesystem access:

- `path_allowlist_prefixes: string[]`

This field narrows an already-active path scope. It does not replace `path_scope_mode`, and it is not a separate reusable object type.

Phase one is intentionally narrow:

- workspace-root-relative prefixes only
- no absolute paths
- no globs or regex
- no reusable path objects
- no multi-root support

The goal is to let MCP Hub express policies like:

- workspace root, but only under `src/`
- current folder descendants, but only when the target also lives under `docs/api/`

without inventing a larger path-rule DSL.

## Why This Is The Next PR

The MCP Hub avenue now supports:

- policy profiles, assignments, overrides, and approvals
- runtime path scoping
- trusted workspace resolution for sandbox, HTTP, and WebSocket ingress

The main remaining local-filesystem gap is finer narrowing inside a trusted workspace. `workspace_root` and `cwd_descendants` are useful, but they still do not express the common need to confine a persona to a known subset like `src/` or `docs/`.

Inline allowlist prefixes are the smallest next step that adds real containment value without introducing another reusable policy object family.

## Goals

- Add `path_allowlist_prefixes` to MCP Hub policy documents.
- Treat allowlist prefixes as workspace-root-relative narrowing only.
- Normalize and validate prefixes on the backend save path.
- Enforce allowlists using canonical absolute-path ancestry checks, not string prefix matching.
- Keep allowlist misses compatible with the current runtime approval model.
- Surface allowlists cleanly in the guided editor, effective preview, and provenance.

## Non-Goals

- Reusable named path-scope objects.
- Absolute paths supplied by users.
- Globs, regex, or pattern DSLs.
- Multi-root workspaces.
- CWD-relative allowlist semantics.
- A broader redesign of path approvals.

## Review Corrections Folded Into This Design

This design explicitly incorporates the review corrections:

- backend normalization and validation, not UI-only checks
- canonical ancestry matching under `workspace_root`
- allowlist-aware approval scoping
- first-class guided-editor support
- explicit replacement semantics in preview and provenance
- broadened-access detection for path allowlist and path-scope changes

## Policy Model

### New field

Add one optional policy field:

- `path_allowlist_prefixes: string[]`

Rules:

- entries are workspace-root-relative prefixes only
- the field is valid only when `path_scope_mode` is not `none`
- empty or missing means no extra narrowing
- this field narrows the effective path scope, it does not create a new scope mode

### Examples

- `path_scope_mode = workspace_root`
- `path_allowlist_prefixes = ["src", "docs/api"]`

means:

- path must remain inside the workspace root
- path must also remain inside `workspace_root/src` or `workspace_root/docs/api`

With `cwd_descendants`, both conditions must hold:

- path must remain under the active `cwd`
- path must also remain under one of the allowed workspace-relative prefixes

## Normalization And Storage

### Save-time normalization

Each allowlist entry must be normalized on the backend before storage:

- trim whitespace
- convert `\` to `/`
- strip leading `./`
- collapse redundant separators
- reject empty results
- reject absolute paths
- reject `..` traversal segments
- dedupe after normalization
- sort normalized results for stable diffs and approval hashing

Examples:

- `src`
- `src/`
- `./src`

all normalize to:

- `src`

### Backend validation is required

UI validation is not enough because policy documents are still generic dict payloads. MCP Hub API write paths must normalize and validate:

- profile `policy_document`
- assignment `inline_policy_document`
- assignment `override_policy_document`

Invalid input should fail with a `400` and a clear reason.

## Merge Semantics

`path_allowlist_prefixes` is a replacement field, not a union field.

That means the active list follows the same layer order as the rest of MCP Hub path policy:

1. default assignment
2. group assignment
3. persona assignment
4. assignment override

And within one assignment:

1. profile policy
2. assignment inline policy
3. assignment override policy

This is intentionally strict. Users should not have to reason about inherited path prefix unions across layers.

## Grant-Authority Implications

This PR must extend broadened-access detection to cover path policy, not only capabilities and tool grants.

Changes that broaden local filesystem reach include:

- changing `path_scope_mode` from `cwd_descendants` to `workspace_root`
- removing `path_allowlist_prefixes`
- replacing a smaller allowlist with a wider one

Examples:

- `["src"] -> ["src", "docs"]` is broader
- `["src", "docs"] -> ["src"]` is narrower

The existing MCP Hub grant-authority delta logic must be updated to recognize these cases. Otherwise the allowlist feature would create an authorization bypass for broader filesystem access.

## Runtime Enforcement Model

### Canonical matching only

Allowlist enforcement must not use raw string-prefix checks.

Instead:

1. normalize each stored allowlist prefix
2. compile it to an absolute allowed root under `workspace_root`
3. normalize each candidate target path as today
4. require the candidate path to be within:
   - the active path scope root
   - and at least one compiled allowlist root

The same ancestry predicate already used by path-scope enforcement should be reused here.

This avoids incorrect matches like:

- `src` matching `src2`

### New denial reason

Add a distinct reason code for allowlist misses:

- `path_outside_allowlist_scope`

This allows the protocol and UI to distinguish:

- outside workspace scope
- outside current-folder scope
- outside allowed workspace paths

## Approval Behavior

For v1, allowlist misses remain approvable under the same runtime approval model already used for path-scope misses.

That means approval is still narrow and context-bound:

- exact tool
- exact normalized path set
- exact path-scope context
- exact allowlist context

### Approval scope hashing

Approval scope must include normalized allowlist context. Otherwise a stale approval could be reused after the allowlist changes.

The scope payload should include either:

- the sorted normalized allowlist prefixes

or:

- a stable allowlist fingerprint derived from them

This should be added alongside existing path scope metadata such as:

- `path_scope_mode`
- `workspace_root`
- `scope_root`
- `normalized_paths`

## UI And Explainability

### Guided editor

The allowlist field should be a first-class guided control.

When `path_scope_mode` is not `none`, show:

- `Allowed workspace paths`

Users can add workspace-relative prefixes like:

- `src`
- `docs/api`
- `configs`

### Important editor behavior

- reject absolute paths in the form
- reject traversal-like entries
- show normalized saved values back to the user
- when scope is set back to `none`, clear:
  - `path_scope_mode`
  - `path_scope_enforcement`
  - `path_allowlist_prefixes`

This avoids hidden narrowing state.

### Effective preview and provenance

Preview should show:

- active path scope
- current normalized allowlist prefixes
- source layer

Copy should be explicit that inherited allowed paths are replaced, not merged. For example:

- `Override replaces inherited allowed workspace paths`

## Testing

### Backend

- normalization rejects absolute paths
- normalization rejects `..`
- prefixes are deduped and sorted
- `src` does not match `src2`
- candidate path must satisfy both scope root and allowlist root
- allowlist misses return `path_outside_allowlist_scope`
- approval scope changes when allowlist changes
- broadened-access detection catches allowlist widening

### Frontend

- guided editor add/remove prefixes
- invalid prefixes rejected
- scope set to `none` clears allowlist state
- preview shows normalized allowlists
- advanced-field warning does not trigger for `path_allowlist_prefixes`

## Risks

- forgetting backend normalization and trusting only the UI
- implementing string-prefix matching instead of ancestry matching
- omitting allowlist context from approval hashing
- widening path access without updating grant-authority deltas
- preserving hidden allowlist state after scope is disabled

## Recommendation

Build this as a narrow extension of the existing path-scope model:

- inline workspace-relative prefixes
- replacement semantics
- backend normalization
- ancestry-based runtime enforcement
- allowlist-aware approval hashing
- explicit UI/provenance behavior

That keeps the feature consistent with the current MCP Hub policy architecture and avoids a premature path-rule DSL.
