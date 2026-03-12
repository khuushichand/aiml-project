# MCP Hub External Slot Runtime Approval Design

Date: 2026-03-10
Status: Implemented

## Summary

The next MCP Hub PR should make runtime approval for external tools slot-aware
and fail closed.

This phase is intentionally narrow:

- approvals cover only already-bound and configured credential slot sets
- approvals are scoped to the exact `tool_name + server_id + requested slot set`
- missing bindings are hard deny
- missing secrets are hard deny
- runtime must return explicit external-auth denial reasons instead of falling
  back to generic `Tool not found` or generic approval prompts

The goal is to make external runtime approval a confirmation mechanism, not a
temporary access-grant mechanism.

## Why This Is The Next PR

The MCP Hub avenue now has:

- managed vs legacy external-server precedence
- explicit credential slots and slot-level bindings
- managed auth templates with required slot mappings
- grant-authority checks for slot privilege escalation

The remaining gap is runtime behavior when an external tool invocation needs
credentials.

Today:

- external access is resolved mostly at the server aggregate level
- approval scoping does not include slot bundles
- protocol feeds blocked external access into the generic approval path
- managed runtime registry can drop misconfigured external servers early,
  producing poor end-user errors

Without a slot-aware runtime layer, the policy model stays precise in MCP Hub
but imprecise in live tool execution.

## Goals

- Evaluate the exact auth-template-required slot set for the external tool's
  server.
- Allow runtime approval only when that exact slot set is already bound and all
  required secrets are configured.
- Hard deny when required slots are not granted by policy.
- Hard deny when required slot secrets are missing.
- Scope approvals to the exact tool, server, and normalized slot set.
- Surface explicit runtime reasons and user-facing messaging for approval vs
  hard deny cases.

## Non-Goals

- Approval-driven temporary widening of external bindings.
- Approval-driven temporary secret overrides.
- Per-slot interactive approval prompts.
- Server-wide approval reuse across tools.
- New MCP Hub editor surfaces beyond optional preview enrichment.

## Current Constraints

- Protocol resolves the module/tool before external access is evaluated in
  [protocol.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/core/MCP_unified/protocol.py).
- Managed runtime registry may skip a server entirely when a required slot
  secret is missing in
  [mcp_hub_external_registry_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_external_registry_service.py).
- Effective external access currently aggregates at the server level using
  `any(slot.runtime_usable)`.
- Approval scope hashing currently includes `server_id` and `reason`, but not
  requested slot bundles.
- Persona runtime approval UI renders generic approval cards and does not yet
  render external slot context as first-class display elements.

These constraints mean the next design must explicitly patch both:

- the protocol/runtime boundary for blocked external tools
- the approval key contract for slot-set reuse

## Core Decisions

### 1. Approval unit is exact `tool + server + slot set`

Runtime approval applies only to:

- one `tool_name`
- one `server_id`
- one normalized sorted slot set

This avoids reusing approval across:

- a different tool on the same server
- the same tool with a broader slot set
- any implicit server-wide or slot-wide scope

### 2. Runtime approval is confirmation only, never temporary widening

Approval is available only when the exact requested slot set is already:

- granted by the effective MCP Hub policy
- configured with required secret material

Approval is never used to:

- add missing slot grants
- override assignment disables
- compensate for missing secrets

### 3. Missing bindings are hard deny

If the auth template requires slot names that are not granted by the effective
profile/assignment binding state, runtime must deny immediately.

Reason:

- `required_slot_not_granted`

No approval payload should be emitted for this case.

### 4. Missing secrets are hard deny

If the auth template requires slots whose secret material is missing, runtime
must deny immediately.

Reason:

- `required_slot_secret_missing`

No approval payload should be emitted for this case, because approval cannot
manufacture missing secret material.

### 5. Requested slot set is derived from the managed auth template

Do not infer requested slots from tool arguments or loose metadata.

The only correct source is the server's managed auth template, via the same
bridge logic already used by runtime auth hydration.

This keeps approval scope aligned with actual secret-bearing auth use.

### 6. Protocol must not collapse misconfigured external servers into `Tool not found`

This slice must ensure external-tool runtime failures for binding/secret issues
surface as explicit MCP policy denials, not missing-tool errors.

Practical implication:

- either the protocol must be able to recognize the external server tool and
  classify denial before adapter execution
- or the managed external runtime registry must preserve enough discoverability
  for protocol to return a policy denial when auth prerequisites are missing

The design should treat this as a required runtime behavior change, not a UI
polish item.

## Runtime Model

For an external tool call, runtime should compute:

- `server_id`
- `requested_slots`
- `bound_slots`
- `missing_bound_slots`
- `missing_secret_slots`
- `blocked_reason`

Decision rules:

- if `missing_secret_slots` is non-empty:
  - `deny`
  - reason `required_slot_secret_missing`
  - no approval payload
- else if `missing_bound_slots` is non-empty:
  - `deny`
  - reason `required_slot_not_granted`
  - no approval payload
- else if approval policy requires confirmation:
  - `approval_required`
- else:
  - `allow`

## Data And API Changes

### External Access Resolution

The current server aggregate is insufficient for slot-scoped runtime decisions.

Extend effective external-access data to include:

- `requested_slots`
- `bound_slots`
- `missing_bound_slots`
- `missing_secret_slots`

This may live:

- in the external-access resolver output directly
- or in a protocol-only derived structure that augments the existing resolver

For this slice, the important requirement is that protocol has access to the
exact requested slot bundle, not just `runtime_executable`.

### Approval Scope Payload

Extend `scope_payload` for external tools to include:

- `server_id`
- `requested_slots`
- `blocked_reason`

The approval fingerprint must include normalized sorted `requested_slots`.

## Protocol Changes

In `protocol.py`:

1. Evaluate the external tool's server and auth-template-required slot set.
2. Derive exact slot-state deltas.
3. Short-circuit hard-deny reasons before generic approval evaluation:
   - `required_slot_not_granted`
   - `required_slot_secret_missing`
4. Only call `_evaluate_runtime_approval(...)` for already-bound and
   configured slot sets.

Hard-deny responses should still include structured context so the persona UI
can render a specific message.

## Approval-Key Semantics

Approval scoping must include:

- tool name
- server id
- normalized sorted requested slot set
- existing context and conversation/session scope

That means:

- same tool + same server + same slot set can reuse approval within the chosen
  duration
- different tool on same server cannot reuse
- same tool with broader slot set cannot reuse

## UI Impact

### Runtime Approval Card

For external approval-required cases, show:

- tool name
- server id or display name
- requested slot set
- reason indicating confirmation is required for already-configured credentials

### Runtime Hard Deny

For missing binding:

- no approval buttons
- explicit message that required credential slots are not granted
- include missing slot names

For missing secret:

- no approval buttons
- explicit message that required credential secrets are not configured
- include missing slot names

The current generic approval card in
[sidepanel-persona.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/routes/sidepanel-persona.tsx)
will need a small contract extension so `scope_context` is rendered
meaningfully instead of appearing only inside generic summaries.

## Testing Strategy

### Backend Tests

Add or extend tests for:

- external access evaluation derives `requested_slots` from the auth template
- missing bound slot yields hard deny with no approval payload
- missing secret yields hard deny with no approval payload
- already-bound/configured slot set yields approval-required when approval mode
  requires it
- approval key changes when tool name changes
- approval key changes when slot set changes
- external-tool runtime denial surfaces a policy reason rather than `Tool not found`

### Frontend Tests

Add or extend tests for:

- external approval card renders server + slot set
- missing-binding hard deny renders explicit message with no approval controls
- missing-secret hard deny renders explicit message with no approval controls

## Risks

- Leaving the runtime registry/tool-discovery path unchanged and still producing
  generic missing-tool errors.
- Reusing approval across different slot bundles.
- Treating current server-level external access as sufficient for slot-aware
  decisions.
- Blurring confirmation semantics with access-grant semantics.

## Rollout

1. Extend external access evaluation with requested slot bundle state.
2. Update protocol to hard-deny missing binding/secret cases before approval.
3. Extend approval scope payload and hashing with requested slot sets.
4. Update persona runtime UI messaging for approval vs hard deny.
5. Verify with focused protocol, external access, persona UI, and Bandit runs.

## Recommendation

Implement this as one focused runtime PR.

Do not combine it with:

- temporary widening of external bindings
- secret-management changes
- broader external-service editor work
