# MCP Hub Credential Slot Grant Authority And Audit Design

Date: 2026-03-10
Status: Approved for planning

## Summary

The next MCP Hub PR should make credential-slot grants privilege-aware and
audit-friendly.

This phase is intentionally narrow:

- `privilege_class` becomes a real enum: `read | write | admin`
- slot grants require matching grant-authority permissions
- server-level binding routes must still resolve the effective slot before
  enforcing authority
- assignment `disable` remains always allowed because it narrows access
- successful grant mutations emit richer audit metadata
- denied mutations return explicit `403` responses, but denied-attempt audit
  logging is deferred

The goal is to prevent users from attaching `write` or `admin` credential slots
to profiles or assignments unless they have explicit authority to grant that
level of external access.

## Why This Is The Next PR

The MCP Hub avenue now has:

- managed-vs-legacy external-server precedence
- explicit credential slots and slot secrets
- slot-level profile and assignment bindings
- managed auth-template authoring for websocket and stdio transports

The next remaining governance gap is configuration authority.

Right now:

- slot bindings can be created without privilege-aware grant checks
- slot metadata already records `privilege_class`, but it is still effectively a
  freeform string
- server-level binding routes still exist and may resolve a default slot for
  compatible single-slot servers
- MCP Hub audit events record binding mutations, but not the privilege level or
  required grant permission that justified the change

Without explicit grant-authority enforcement, slot privilege classes are useful
for labeling but not for actual containment.

## Goals

- Treat slot privilege classes as a real ordered ladder:
  - `read`
  - `write`
  - `admin`
- Require explicit grant-authority permissions for slot grants:
  - `grant.credentials.read`
  - `grant.credentials.write`
  - `grant.credentials.admin`
- Apply the same rules to both profile and assignment grants.
- Always allow assignment `disable`.
- Enforce authority for server-level binding routes by resolving the effective
  default slot when one exists.
- Make successful audit events record slot privilege and required grant
  permission.
- Enforce privilege-class authority on slot create/update when a slot is created
  or elevated to a broader class.

## Non-Goals

- Per-server or per-slot custom grant-permission names.
- A new admin UI for managing grant-authority policy.
- Denied-attempt audit persistence in this PR.
- Changes to runtime external-access resolution.
- Arbitrary new privilege levels beyond `read | write | admin`.

## Current Constraints

- The slot schema and repo currently accept freeform `privilege_class` strings.
- Public binding routes exist both with and without `slot_name`.
- Single-slot managed servers may still resolve a default slot in the resolver.
- Existing policy-document grant authority is enforced in the endpoint layer via
  `_require_grant_authority(...)`.
- Binding service methods currently receive `actor_id`, not the caller's
  permission set.
- MCP Hub audit emission is success-oriented best effort.

These constraints mean the next design should:

- normalize and validate `privilege_class` explicitly
- make the public HTTP endpoint layer the canonical grant-authority enforcement
  point for this phase
- enrich existing success audit events instead of inventing a separate failure
  audit pipeline

## Core Decisions

### 1. Slot privilege class is a strict enum with ordered ladder semantics

Credential slots may use only:

- `read`
- `write`
- `admin`

Unknown values should be rejected on save, not mapped implicitly.

Grant-authority semantics:

- `grant.credentials.admin` may grant `admin`, `write`, or `read`
- `grant.credentials.write` may grant `write` or `read`
- `grant.credentials.read` may grant `read` only

This keeps the model boring and avoids ambiguous privilege drift.

### 2. Binding grant authority is enforced for both explicit-slot and server-level routes

Public binding APIs exist in two shapes:

- explicit slot route: `{server_id}/{slot_name}`
- server-level route: `{server_id}`

For server-level routes:

- if the managed server resolves to a compatible default slot, grant authority
  must be evaluated against that slot's `privilege_class`
- if no default slot can be resolved, keep the existing binding behavior for
  now, because there is no slot privilege to evaluate

This prevents single-slot managed servers from bypassing slot privilege checks.

### 3. Assignment `disable` is always allowed

Assignment disable narrows access only.

Therefore:

- profile bindings may only use `grant`
- assignment bindings may use `grant` or `disable`
- assignment `disable` never requires grant authority
- delete operations never require grant authority

This mirrors the existing tool-policy model where narrowing changes are allowed
without broadened-access permissions.

### 4. Public HTTP routes are the canonical enforcement boundary for v1

The current binding service signatures only receive `actor_id`, not the
principal's roles or permissions.

For this phase:

- enforce credential-slot grant authority in `mcp_hub_management.py`
- implement shared helpers there for:
  - normalizing privilege class
  - mapping class to required permission
  - resolving the effective slot for a binding route
  - checking ladder semantics against the principal
- keep the service layer authority-agnostic for now

This matches the current policy-document grant-authority pattern and keeps the
diff narrow.

### 5. Slot create/update must also respect privilege escalation

If a slot's `privilege_class` changes from `read` to `admin`, that is a real
governance escalation even before any new binding is created.

Therefore:

- creating a slot with `write` or `admin` requires matching grant authority
- updating a slot to a broader class requires matching grant authority
- lowering a slot privilege class requires only normal mutation permission

This prevents administrators from bypassing binding checks by relabeling slot
metadata after the fact.

### 6. Successful audit events become privilege-aware; denied-attempt audit is deferred

This PR should enrich the existing success audit path only.

For successful binding grants and slot privilege-class elevations, audit
metadata should include:

- `external_server_id`
- `slot_name`
- `privilege_class`
- `binding_target_type`
- `binding_target_id`
- `binding_mode`
- `required_permission`
- relevant granted-permission snapshot

Denied writes should still return explicit `403` responses naming the missing
permission, but denied-attempt audit persistence is deferred to a later slice.

## Permission Model

### Privilege Class Ladder

```text
read < write < admin
```

### Required Permissions

- `read` -> `grant.credentials.read`
- `write` -> `grant.credentials.write`
- `admin` -> `grant.credentials.admin`

### Satisfaction Rules

A principal satisfies a requirement when any of the following are true:

- role `admin`
- permission `*`
- exact required permission is present
- a higher credential grant permission is present

Examples:

- `grant.credentials.admin` satisfies `write`
- `grant.credentials.write` does not satisfy `admin`
- `grant.credentials.read` does not satisfy `write`

## Data And API Changes

### Schema Tightening

Tighten slot privilege fields to the canonical enum in:

- slot create request
- slot update request
- slot response

### Endpoint Helpers

Add small HTTP-layer helpers for:

- privilege normalization
- privilege rank lookup
- required-permission mapping
- principal authority check
- default-slot resolution for server-level binding routes

### Response Behavior

No response shape change is required for binding APIs in this PR.

Error behavior:

- insufficient authority -> `403`
- detail names the missing required permission
- unknown or invalid privilege class on slot create/update -> `400`

## Audit Behavior

### Successful Binding Grant Audit

When a profile or assignment `grant` succeeds:

- emit the existing MCP Hub audit event
- include privilege-aware metadata:
  - server
  - slot
  - privilege class
  - required permission
  - binding target
  - binding mode

### Successful Slot Elevation Audit

When slot create/update writes a privilege class:

- include the effective privilege class
- on updates, include prior and next class when available
- include the required permission if the change broadened privilege

### Deferred Failure Audit

Denied grant attempts are out of scope for this PR.

They should:

- return explicit `403` detail
- be covered by tests
- remain visible through normal API error handling

## UI Impact

UI changes should stay intentionally small.

Recommended behavior:

- preserve existing slot privilege labels in slot and binding views
- surface backend `403` details cleanly in MCP Hub binding flows
- optionally add short helper text that `write` and `admin` slots require
  elevated grant authority

Do not build a separate grant-authority management UI in this phase.

## Testing Strategy

### Backend Tests

Add or extend tests for:

- profile `read` slot grant succeeds with `grant.credentials.read`
- profile `write` slot grant fails with only `grant.credentials.read`
- profile `admin` slot grant succeeds with `grant.credentials.admin`
- assignment `disable` succeeds without credential grant permissions
- server-level binding route for a compatible default slot requires the slot's
  privilege authority
- slot create with `admin` privilege fails without `grant.credentials.admin`
- slot update from `read` to `write` fails without `grant.credentials.write`
- successful audit metadata includes slot privilege and required permission

### Frontend Tests

Add or extend tests for:

- binding failure surfaces `Grant authority required: ...`
- slot privilege labels remain visible in binding surfaces

## Risks

- Missing a public binding route and leaving a privilege bypass.
- Allowing freeform privilege classes to persist in old data.
- Treating server-level binding as authority-free when a default slot exists.
- Expanding scope into denied-attempt audit before the current success-audit
  model is stable.

## Rollout

1. Tighten privilege-class normalization and validation.
2. Add endpoint-layer grant-authority helpers for slot grants.
3. Apply checks to:
   - profile binding grants
   - assignment binding grants
   - slot create
   - slot privilege elevation updates
4. Enrich successful audit metadata.
5. Update UI error surfacing and tests.
6. Verify with focused pytest, Vitest, and Bandit runs.

## Recommendation

Implement this as one narrow MCP Hub PR focused on write-time governance.

Do not combine it with:

- denied-attempt audit persistence
- new admin grant-authority UI
- runtime external-access changes
- new privilege levels
