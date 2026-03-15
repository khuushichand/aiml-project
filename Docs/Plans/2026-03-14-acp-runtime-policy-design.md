# ACP Runtime Policy Design

Date: 2026-03-14
Status: Approved
Scope: MCP Hub-authoritative ACP runtime policy snapshots with refresh, provenance, and backward-compatible ACP integration

## 1. Summary

Make `MCP Hub effective policy` the authoritative runtime policy source for ACP sessions. ACP profiles remain non-authoritative runtime configuration objects that carry execution settings and optional UI/policy hints, but they no longer decide live tool access.

At ACP session start, the runtime resolves an MCP Hub effective policy using the authenticated user plus persona, workspace, session, and ACP profile context. That resolved policy is normalized into an `ACPRuntimePolicySnapshot` that ACP runner clients use for prompt governance context, tool allow/ask/deny decisions, and permission-request UX.

The design is intentionally pragmatic:

- MCP Hub remains the single runtime authority for tool access
- ACP profiles stay useful as execution config plus hints
- ACP sessions cache policy snapshots for performance
- snapshot refresh happens on trigger, not every request
- legacy permission tiers remain only as UI grouping hints

## 2. User-Approved Decisions

Validated during brainstorming:

1. MCP Hub effective policy should be authoritative at runtime; ACP profiles should remain runtime configuration only.
2. ACP should use session snapshots plus versioned refresh rather than session-pinned policy or per-call full re-resolution.
3. ACP profiles in v1 should contain execution config plus optional non-authoritative hints.
4. Policy resolution should use the authenticated user plus persona/workspace/session context and ACP profile config.
5. Legacy ACP permission tiers should remain only as UI grouping hints, not as a second authority layer.
6. If MCP Hub policy changes while a session is running, the change should apply on the next refresh trigger.
7. v1 refresh should use a conservative trigger set:
   - session start
   - before permission checks for high-risk tools
   - when persona/workspace/session context changes
   - when policy fingerprint/version differs from the cached snapshot
8. ACP provenance should be exposed as summary plus expandable detail, not as raw full payload by default.

## 3. Review-Driven Revisions

Pressure-testing against ACP session persistence, MCP Hub effective-policy resolution, and existing ACP runner governance produced these corrections:

1. The repo does not currently have a persisted policy-snapshot seam in ACP sessions. V1 must explicitly add lightweight snapshot persistence rather than assuming an existing place to store fingerprints or refresh metadata.
2. The ACP-to-MCP-Hub context contract must be normalized. A single builder should construct the metadata passed into effective-policy resolution so different ACP entry points do not drift.
3. Tool authority must belong to the MCP Hub policy snapshot alone. Existing ACP governance hooks should remain for prompt/content/session checks, not become a second tool-permission engine.
4. Snapshot invalidation needs an exact source of truth. V1 should compare stable policy fingerprints, not ad hoc timestamps.
5. Refresh before high-risk tool checks must derive from resolved tool metadata or normalized risk semantics, not from a second ACP-only permission taxonomy.
6. ACP schema changes must be backward-compatible. Existing tier-centric clients should continue to work while newer clients gain policy summary and provenance fields.
7. Snapshot refresh should be singleflight per session so concurrent permission checks do not race and produce inconsistent decisions.
8. Permission decisions should record the policy snapshot fingerprint used so later debugging can tie outcomes to the exact runtime authority state.

## 4. Current State In The Repo

The current codebase already contains the right seams for this work:

- ACP runner clients in [tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py) and [tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py) already perform prompt-governance checks, permission checks, and permission-request flows.
- MCP Hub already resolves effective policy in [tldw_Server_API/app/services/mcp_hub_policy_resolver.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/mcp_hub_policy_resolver.py).
- ACP profile CRUD already exists under MCP Hub services and endpoints, with profiles stored as opaque `profile_json` configuration payloads.
- ACP session persistence already captures session metadata such as persona, workspace, group, scope snapshot, and MCP servers in [tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py) and [tldw_Server_API/app/services/admin_acp_sessions_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_acp_sessions_service.py).
- ACP request/response schemas already expose permission requests and session state in [tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py).

What is missing today:

- no ACP runtime policy snapshot model
- no persisted snapshot fingerprint/version metadata on ACP sessions
- no normalized ACP-to-MCP-Hub policy context builder
- no refresh coordination or singleflight logic for ACP sessions
- no MCP Hub-backed policy summary/provenance in ACP permission payloads
- no explicit separation between ACP tool authority and legacy tier UX

## 5. Goals And Non-Goals

### 5.1 Goals

- Make MCP Hub effective policy the single runtime authority for ACP tool allow/ask/deny decisions.
- Keep ACP profiles as execution config plus optional hints.
- Add an ACP runtime policy snapshot model with policy summary, provenance summary, fingerprint/version, and refresh metadata.
- Persist lightweight snapshot state with ACP sessions so current runtime authority can be inspected and audited.
- Refresh snapshots conservatively and fail closed when safe refresh cannot be completed for risky actions.
- Keep existing ACP APIs backward-compatible while adding richer governance payloads.
- Record the snapshot fingerprint used for permission decisions and denials.

### 5.2 Non-Goals

- Do not make ACP profiles authoritative for tool policy.
- Do not add push-based immediate revocation in v1.
- Do not persist the full raw effective-policy provenance blob in ACP session rows.
- Do not reintroduce ACP permission tiers as an authority layer.
- Do not make each tool executor query MCP Hub directly.
- Do not add a separate ACP-only policy language.

## 6. Proposed Architecture

### 6.1 Runtime Authority Model

ACP runtime policy authority is split into two distinct artifacts:

- `execution_config`
  - sourced from ACP profile plus session setup
  - contains sandbox/runtime mode, agent type, MCP server preferences, environment preset, and optional UI hints
- `policy_snapshot`
  - sourced from MCP Hub effective-policy resolution
  - contains resolved runtime policy, policy summary, provenance summary, fingerprint/version, and refresh metadata

Runner clients and permission checks consume both, but only the policy snapshot decides tool access.

### 6.2 ACPRuntimePolicyService

Add a new service, `ACPRuntimePolicyService`, that owns:

- building normalized MCP Hub resolution metadata from ACP session context
- resolving effective policy from MCP Hub
- normalizing that result into an ACP policy snapshot
- computing and comparing policy fingerprints
- refreshing snapshots on trigger
- coordinating one in-flight refresh per session

ACP runtime should talk to this service rather than duplicating policy resolution logic in endpoints or runner clients.

### 6.3 ACPRuntimePolicySnapshot

Introduce a normalized runtime object with fields such as:

- `session_id`
- `user_id`
- `policy_snapshot_version`
- `policy_snapshot_fingerprint`
- `policy_snapshot_refreshed_at`
- `policy_summary`
- `policy_provenance_summary`
- `resolved_policy_document`
- `approval_summary`
- `refresh_error`
- `context_summary`

V1 persistence should store only the lightweight fields that are needed for inspection, audit, and refresh logic:

- `policy_snapshot_version`
- `policy_snapshot_fingerprint`
- `policy_snapshot_refreshed_at`
- `policy_summary_json`
- `policy_provenance_summary_json`
- `policy_refresh_error`

The full raw resolved policy and full provenance can remain in memory or be recomputed on demand.

## 7. Context And Resolution Pipeline

### 7.1 Normalized Context Builder

ACP must use a single normalized builder to produce MCP Hub effective-policy metadata. Suggested keys:

- `persona_id`
- `workspace_id`
- `workspace_group_id`
- `scope_snapshot_id`
- `org_id`
- `team_id`
- `mcp_policy_context_enabled`
- `acp_profile_id`
- `acp_profile_hint_tags`
- `mcp_servers`

Rules:

- all ACP entry points use the same builder
- missing fields are omitted consistently rather than ad hoc set to `null`
- the builder owns any translation from ACP session fields to MCP Hub metadata contract

### 7.2 Resolution Flow

1. ACP session is created with user identity, optional persona/workspace context, and optional ACP profile.
2. ACP loads execution config from the ACP profile.
3. `ACPRuntimePolicyService` builds normalized effective-policy metadata.
4. MCP Hub effective policy is resolved using the user plus normalized metadata.
5. ACP normalizes the result into a policy snapshot and stores lightweight snapshot metadata with the session.
6. Prompt and permission checks consume the snapshot until a refresh trigger fires.
7. On refresh, ACP recomputes the snapshot and swaps it in for subsequent checks.

This keeps ACP coupled to MCP Hub through a single service boundary rather than through direct resolver calls scattered throughout the runtime.

## 8. Runtime Semantics

### 8.1 Prompt Governance

Prompt governance remains in ACP, but the runtime policy snapshot should provide contextual inputs such as policy summary and safety posture. ACP prompt/content governance stays responsible for prompt/session-shape validation rather than for tool allowlists.

### 8.2 Tool Execution Authority

When the agent requests a tool:

- if the tool is explicitly denied by the snapshot, ACP denies immediately
- if the tool is allowed without approval, ACP auto-approves
- if the tool is allowed but approval is required, ACP creates a permission request
- if the tool is unresolved or blocked by runtime constraints, ACP denies or requires approval according to normalized runtime posture

Runtime may narrow relative to snapshot intent when the environment cannot prove safety:

- missing workspace root proof
- missing external credential binding
- missing MCP server binding
- unsupported path constraint

Runtime may never broaden access beyond the resolved snapshot.

### 8.3 Legacy Permission Tiers

Legacy ACP permission tiers remain only as UI hints for batching or presentation. They should not decide tool authority.

V1 rule:

- MCP Hub snapshot decides `allow`, `approval_required`, or `deny`
- tier remains optional display metadata for grouping and UX

## 9. Snapshot Refresh Model

### 9.1 Refresh Triggers

V1 refresh triggers:

- session start
- before permission checks for high-risk tools
- when persona/workspace/session context changes
- when the current policy fingerprint/version no longer matches the latest resolved policy

### 9.2 Fingerprint And Version

ACP should compare stable snapshot fingerprints derived from a canonical hash of:

- resolved effective policy
- relevant scope/context identity
- policy version metadata returned by MCP Hub, when available

ACP should prefer fingerprint comparison over ad hoc timestamps.

### 9.3 High-Risk Tool Checks

“High-risk” should come from normalized tool or policy metadata already available in the resolved policy path, not from an ACP-only side table. That keeps risk semantics aligned with MCP Hub runtime authority.

### 9.4 Refresh Failure Behavior

If refresh fails:

- existing completed tool calls are unaffected
- subsequent risky operations must fail closed
- ACP may deny or require approval, but must not silently keep a stale-broadened policy
- session detail should expose `policy_refresh_error`

### 9.5 Concurrency

Refresh should be singleflight per session:

- one refresh in flight per session id
- concurrent checks await or reuse the same refresh result
- ACP avoids duplicate resolver work and inconsistent mixed-snapshot decisions

## 10. API And UI Changes

### 10.1 ACP Session Shape

Add backward-compatible fields to ACP session responses:

- `policy_snapshot_version`
- `policy_snapshot_fingerprint`
- `policy_snapshot_refreshed_at`
- `policy_summary`
- `policy_provenance_summary`
- `policy_refresh_error`

These fields should be optional so older clients continue to parse session payloads.

### 10.2 Permission Request Shape

Add backward-compatible fields to permission request payloads:

- `approval_requirement`
- `governance_reason`
- `deny_reason`
- `provenance_summary`
- `runtime_narrowing_reason`
- `policy_snapshot_fingerprint`
- optional `tier`

Existing `tier` should remain available for UI batching hints.

### 10.3 UI Expectations

ACP UI should surface:

- compact policy summary on session detail
- last refresh time and refresh error state
- expandable provenance detail in permission modals and session detail
- clear copy that ACP profiles provide config/hints, not authority

## 11. Persistence And Audit

### 11.1 Session Persistence

Extend ACP session persistence to store lightweight snapshot state. This enables:

- operational inspection of current session policy
- refresh comparisons across requests
- troubleshooting without recomputing basic policy summary

### 11.2 Permission Decision Audit

Permission approvals, denials, and requests should record:

- `session_id`
- `tool_name`
- `decision`
- `policy_snapshot_fingerprint`
- `policy_snapshot_version`
- `governance_reason`

This creates an auditable link between runtime behavior and the policy snapshot in effect at the time.

## 12. Risks And Mitigations

1. `Dual authority confusion`
   - Mitigation: API/UI language should explicitly label ACP profiles as config/hints and MCP Hub snapshots as authority.
2. `Stale snapshot broadening`
   - Mitigation: fingerprint-based refresh and fail-closed behavior for risky actions.
3. `Resolver coupling`
   - Mitigation: ACP talks to a single `ACPRuntimePolicyService`, not to MCP Hub internals everywhere.
4. `Legacy tier drift`
   - Mitigation: tiers stay optional display metadata only.
5. `Provenance overload`
   - Mitigation: summary by default, expandable detail on demand.
6. `Refresh races`
   - Mitigation: singleflight refresh per session.

## 13. Testing Strategy

### 13.1 Snapshot Creation

Test that session start:

- resolves MCP Hub effective policy using normalized ACP context
- persists lightweight snapshot metadata
- keeps ACP profile config separate from authoritative policy

### 13.2 Permission Enforcement

Test that:

- allowed tools auto-approve
- denied tools fail immediately with governance reason
- approval-required tools create permission requests with provenance summary
- runtime narrowing converts would-be allow into ask or deny when required

### 13.3 Refresh Behavior

Test that:

- context changes trigger refresh
- fingerprint/version differences trigger refresh
- high-risk checks refresh before decision
- failed refresh does not silently broaden access
- concurrent refresh attempts reuse one in-flight operation

### 13.4 Backward Compatibility

Test that:

- ACP profile CRUD still works
- existing `tier` fields remain present
- older clients can parse session and permission payloads when new optional fields are present

### 13.5 Integration Parity

Test that:

- changes to MCP Hub profiles, adapter mappings, or governance-pack imports affect ACP behavior after refresh
- ACP decisions align with MCP Hub effective-policy outcomes for the same context

## 14. Recommended V1 Boundary

Include:

- ACP runtime policy snapshot service
- lightweight snapshot persistence
- normalized context builder
- fingerprint-based refresh
- singleflight refresh coordination
- MCP Hub-authoritative tool decision path
- backward-compatible schema expansion
- permission decision audit via snapshot fingerprint

Exclude:

- push-based live revocation
- full raw provenance persistence in session rows
- a second ACP-only policy language
- executor-by-executor direct MCP Hub integration
