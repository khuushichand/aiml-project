# MCP Hub Path-Scoped Enforcement Design

Date: 2026-03-10
Status: Approved for planning

## Summary

The next MCP Hub PR should add the first enforceable local path-scope model for MCP tool usage.

This phase is intentionally narrow:

- workspace-derived scopes only
- sandbox-backed ACP/persona sessions only, unless a reusable workspace-root resolver already exists
- explicit first-wave allowlist of path-enforceable tools
- approval escalation when path enforcement cannot be applied safely

The goal is to make MCP Hub profiles like `Read Current Folder` and `RW Current Folder + Descendants` mean something enforceable at runtime, without claiming coverage for tools or session types the server cannot yet evaluate safely.

## Why This Is The Next PR

The MCP Hub avenue now has:

- durable policy storage
- profiles, assignments, approvals, and overrides
- effective-policy resolution with provenance
- registry-backed catalog and guided editing

What is still missing from the original containment goal is real local path scoping. The UI can classify tools and group them well, but the runtime still does not enforce workspace-bounded filesystem access for MCP tool calls.

That makes the next most important gap:

- `Read current folder only`
- `RW current folder + descendants`

These must become runtime guarantees for the subset of tools the server can evaluate safely.

## Goals

- Add MCP Hub policy fields for workspace-derived path scopes.
- Resolve an effective `workspace_root` and optional `cwd` for ACP/persona sessions.
- Enforce path scope for a conservative first-wave set of `path_boundable` tools.
- Fail closed for out-of-scope paths.
- Escalate to runtime approval when a local-file tool cannot be path-scoped safely.
- Expose the active path scope in MCP Hub editing and policy summaries.

## Non-Goals

- Arbitrary user-entered local path allowlists.
- Multi-root workspace support.
- Full path extraction for deeply nested or semantically complex tool arguments.
- Path-scoped guarantees for direct non-session MCP/API requests.
- Credential binding or external-server precedence work.
- Reworking the broader approval model beyond what path-scoped escalation needs.

## Current Constraints

- ACP session metadata persists `workspace_id` and `cwd`, but not a general `workspace_root`.
- The only concrete server-side workspace path resolver visible today is sandbox-backed session lookup.
- The current registry exposes `path_boundable`, but not yet extraction hints.
- Current approval reuse is keyed by tool name plus a coarse argument fingerprint, not by resolved absolute path scope.
- Existing path-hardening logic already lives in the sandbox code and should be reused instead of duplicated.

These constraints mean the first release should be scoped to traffic where the server can derive a trustworthy local workspace root.

## Core Decisions

### 1. Phase one is sandbox-backed unless a general workspace-root resolver exists

The first implementation should treat sandbox-backed ACP/persona sessions as the supported enforcement surface.

Reasons:

- ACP sessions already persist `workspace_id` and `cwd`
- sandbox services already persist and resolve concrete workspace paths
- this avoids inventing an abstract path boundary the runtime cannot prove

If a reusable `workspace_id -> absolute root path` service already exists and can serve non-sandbox sessions safely, it can be used. Otherwise, the first rollout should explicitly document that path-scoped enforcement requires a sandbox-backed session.

### 2. Path scope is workspace-derived only in this phase

Supported modes:

- `none`
- `workspace_root`
- `cwd_descendants`

No arbitrary path allowlists in this PR.

Reasons:

- keeps the UX understandable
- avoids a larger persistence and validation surface
- aligns with the original user-facing safety presets

### 3. Path-enforceable tools must be explicitly trusted in phase one

The current registry already exposes `path_boundable`, but category defaults and heuristics are too broad to rely on as an enforcement boundary by themselves.

The first rollout should require either:

- explicit tool metadata, or
- a server-maintained first-wave allowlist plus extraction hints

Heuristic or fallback-classified tools should be treated as not safely path-enforceable, even if the broader registry currently marks their category as path-capable.

### 4. Unenforceable local-file actions escalate, not silently bypass

If a profile uses path scope and a local-file tool:

- is not explicitly path-enforceable, or
- cannot yield concrete local target paths, or
- has no trustworthy workspace root,

the runtime should trigger approval rather than silently allowing the call.

This keeps the path-scoped promise honest while still letting the user continue with a bounded elevation flow.

### 5. Approval reuse for path escalations must be path-aware

Existing approval decisions are keyed from tool name plus a coarse argument fingerprint. That is not sufficient for path-scoped elevation.

Path-related approvals in this PR should include the resolved path context in the approval scope, specifically:

- tool name
- scope mode
- workspace root identity
- normalized resolved path or normalized path set

Without that, a session-level or conversation-level approval risks widening beyond the path the user intended to permit.

### 6. Reuse sandbox path canonicalization semantics

This PR should reuse the existing sandbox security posture for path normalization:

- canonical absolute path resolution
- traversal rejection
- symlink rejection where required
- explicit proof that `cwd` remains within `workspace_root`

The project already has hardened workspace traversal checks in sandbox snapshot logic. Path-scoped MCP enforcement should adopt the same semantics rather than inventing a second path-security implementation.

## Policy Model

### New policy fields

Add the following scalar fields to MCP Hub policy documents:

- `path_scope_mode`
  - `none`
  - `workspace_root`
  - `cwd_descendants`
- `path_scope_enforcement`
  - `approval_required_when_unenforceable`

This phase does not need a separate `enforce` mode because the intended runtime behavior is:

- enforce when possible
- escalate when safe enforcement is impossible

### Merge semantics

Path-scope fields are scalar replacement fields.

They should follow the existing layer order:

1. default assignment
2. group assignment
3. persona assignment
4. assignment override

Within a single assignment:

1. profile policy
2. assignment inline policy
3. assignment override policy

The current resolver already uses replacement semantics for non-list fields, so these keys should remain outside the list-union merge set.

## Runtime Scope Resolution

### Inputs

The path-scope resolver needs:

- effective MCP Hub policy
- active ACP/persona session id
- session `workspace_id`
- session `cwd`
- concrete `workspace_root`

### Effective scope rules

- `none`
  - no additional local path restriction
- `workspace_root`
  - allow local file targets at or below the resolved workspace root
- `cwd_descendants`
  - allow local file targets at or below the session `cwd`
  - only valid if `cwd` resolves inside `workspace_root`

If `cwd` is missing, outside the workspace root, or cannot be normalized safely:

- do not silently widen to `workspace_root`
- fail closed and escalate through approval

## Tool Registry Changes

The registry needs one canonical DTO expansion for this PR.

### New fields

Add:

- `path_argument_hints`
  - a small normalized list of argument keys or extraction hints used by the runtime path extractor
- optionally `path_scope_support`
  - `explicit`
  - `heuristic`
  - `unsupported`

At minimum, `path_argument_hints` must be added to the shared backend and frontend registry schemas so the extractor and UI consume the same contract.

### Phase-one support rules

A tool is path-enforceable in this PR only if:

- it is explicitly trusted for phase one, and
- its path arguments can be resolved from a simple supported shape

Supported first-wave shapes should be intentionally boring:

- `path`
- `file_path`
- `target_path`
- `cwd`
- `paths`
- `file_paths`
- `files[].path`

Anything more complex should escalate rather than guessing.

## Backend Architecture

### Path scope resolver

Add a small runtime service that:

- resolves the effective MCP Hub path-scope policy
- resolves `workspace_root`
- normalizes `cwd`
- returns a structured scope object used by execution enforcement

### Tool path extractor

Add a focused extractor that:

- uses registry-provided `path_argument_hints`
- extracts candidate local paths from tool args
- returns normalized candidate paths or an `unenforceable` result

### Path scope enforcer

Add a service that:

- checks every resolved path against the effective scope
- returns `allow`, `deny`, or `approval_required`
- includes a machine-readable reason code

Recommended reason codes:

- `path_outside_workspace_scope`
- `path_outside_cwd_scope`
- `tool_not_path_enforceable`
- `path_resolution_unavailable`
- `workspace_root_unavailable`
- `cwd_outside_workspace_scope`

### Approval bridge

When the outcome is `approval_required`, the runtime should produce an approval payload that includes:

- the reason code
- the resolved scope mode
- a bounded summary of normalized target paths
- whether the tool was unenforceable or simply out of scope

The approval scope key for path-related decisions should incorporate:

- tool name
- reason code
- scope mode
- normalized path fingerprint
- workspace root identity

This must be stricter than the current generic argument-based approval fingerprint.

## UI Changes

### MCP Hub guided editor

For profiles and assignments that include local filesystem capability, add:

- `Local file scope`
  - `No additional path restriction`
  - `Workspace root`
  - `Current folder and descendants`

The helper text should state:

- path restriction applies only to tools the runtime can path-scope safely
- other local-file tools will require approval

### Catalog tab

Add:

- `path-enforceable` badge for explicitly trusted tools
- warning badge for local-file tools that are not path-enforceable in phase one
- metadata warning text for heuristic/fallback entries

### Effective policy summary

Show:

- active path scope mode
- whether approval fallback is active for unenforceable local-file tools

Persona summary should stay compact and indicate only:

- current path scope
- whether local-file escalation may still occur

## Testing

### Backend unit tests

- path-scope scalar merge semantics
- workspace-root and cwd resolution
- traversal rejection
- fail-closed behavior when workspace root is unavailable
- extractor behavior for supported hint shapes
- approval scope-key generation for path-related prompts

### Backend integration tests

- allow a path-enforceable tool inside workspace scope
- deny or escalate when target path escapes workspace root
- deny or escalate when target path escapes `cwd_descendants`
- escalate when tool is local-file capable but not explicitly path-enforceable
- escalate when no trusted workspace root exists

### Frontend tests

- guided editor path controls appear only for local-file-capable policy
- policy documents preserve advanced fields while adding path-scope fields
- effective summaries render path scope
- approval cards render path-specific reason text

### Registry tests

- explicit `path_argument_hints` normalization
- heuristic/fallback entries are not surfaced as safely path-enforceable in phase one

## Risks

### Workspace root drift

If session `workspace_id` cannot reliably resolve to a concrete root for all supported traffic, the path-scoped promise becomes advisory. The first rollout must scope itself around the traffic where this mapping is trustworthy.

### False trust in registry metadata

If a tool is marked path-enforceable too early, MCP Hub will claim containment it cannot actually provide.

### Approval over-broadening

If path-scoped approval reuse remains keyed only by coarse args, a single approval could accidentally cover unrelated path targets.

### Cross-platform path differences

Normalization must account for symlinks, traversal, casing, and absolute-path behavior across supported environments.

## Rollout Recommendation

Ship this PR as:

1. path-scope policy fields
2. registry/schema support for explicit extraction hints
3. sandbox-backed workspace-root resolution path
4. conservative first-wave path enforcement for explicitly trusted tools
5. path-aware approval escalation
6. MCP Hub editor and summary updates

Do not expand to arbitrary path allowlists or non-session traffic in the same PR.

