# Capability Adapter Registry Design

Date: 2026-03-14
Status: Approved
Scope: scope-aware capability adapter mappings for MCP Hub with full runtime integration at the effective-policy resolver boundary

## 1. Summary

Add a scope-aware `Capability Adapter Registry` to MCP Hub so portable capabilities can resolve into concrete runtime policy for `global`, `org`, and `team` scopes. The registry becomes the canonical capability-resolution layer for all MCP Hub policy documents, including governance-pack imports and hand-authored MCP Hub policies. Concrete tool fields remain fully editable peers to capabilities.

Runtime integration happens at the existing `McpHubPolicyResolver` boundary. The resolver will merge authored MCP Hub policy inputs, resolve portable capabilities through the adapter registry, merge the resolved concrete effects with directly-authored concrete tool rules, and then hand that resolved policy to the existing approval, path-scope, and external-access services.

The design is intentionally pragmatic:

- capabilities become first-class everywhere
- direct concrete tool fields continue to work unchanged
- governance-pack dry-run/import stops relying on hardcoded capability support
- runtime consumers reuse the existing effective-policy flow instead of each executor learning adapter lookups independently

## 2. User-Approved Decisions

Validated during brainstorming:

1. The next slice should cover dry-run/import mapping plus effective-policy visibility, not only dry-run/import.
2. Adapter mappings should be scope-aware for `global`, `org`, and `team`.
3. Full runtime integration is in scope, but should integrate at the canonical policy-resolver boundary.
4. The long-term pragmatic direction is to make the adapter registry the canonical capability-resolution layer for all MCP Hub policy documents, not governance-pack imports only.
5. Concrete tool fields should remain fully editable peers to capabilities rather than being demoted to a legacy-only path.

## 3. Review-Driven Revisions

Pressure-testing against the current MCP Hub resolver and governance-pack implementation produced these corrections:

1. Split authored and computed state. The current resolver returns a merged `policy_document` that downstream services already consume. Adapter-resolved effects must not be written back as if they were authored inputs.
2. Direct authored scalar runtime knobs remain authoritative. Mapping outputs may fill missing values but should not override explicit direct values for approval or path-scope semantics.
3. Mapping CRUD needs grant-authority checks based on resolved concrete effects, or mappings become a privilege-escalation side door relative to existing policy-document checks.
4. Support exactly one `adapter_contract_version` in v1 and reject anything else explicitly.
5. User-scoped policy resolution can still use the adapter registry, but only through `team -> org -> global` mappings. User-scoped mappings are excluded from this release.
6. Mapping writes need preview/audit output, not just governance-pack dry-run diagnostics, because mapping edits are retroactive by design.
7. Mapping validation should use the MCP tool registry so free-form tool names do not silently drift away from actual runtime inventory.
8. Effective-policy provenance should include mapping summary and expandable detail rather than dumping raw per-effect provenance everywhere by default.

## 4. Current State In The Repo

The current codebase already contains the right runtime seam for this work:

- `McpHubPolicyResolver` in [tldw_Server_API/app/services/mcp_hub_policy_resolver.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/mcp_hub_policy_resolver.py) merges profiles, assignments, path-scope objects, and overrides into a single effective policy.
- List-based fields such as `allowed_tools`, `denied_tools`, `tool_names`, `tool_patterns`, and `capabilities` already use union merge semantics.
- Effective-policy responses already carry `sources` and `provenance`.
- Downstream services such as approval, path-scope, path enforcement, and external access already consume effective-policy output.
- Governance-pack import and dry-run already exist, but [tldw_Server_API/app/services/mcp_hub_governance_pack_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/mcp_hub_governance_pack_service.py) still uses hardcoded supported-capability and approval maps.

What is missing today:

- no persisted capability adapter registry
- no scope-aware capability-to-runtime mapping service
- no authored-versus-resolved policy split
- no runtime provenance for capability-mapping expansion
- no governance-pack dry-run integration with live adapter mappings

## 5. Goals And Non-Goals

### 5.1 Goals

- Add a persisted MCP Hub configuration domain for scope-aware capability adapter mappings.
- Make portable capabilities first-class in all MCP Hub policy documents.
- Keep direct concrete tool fields fully supported as peer inputs.
- Resolve capabilities at effective-policy read time rather than materializing permanent expanded copies into every policy object.
- Reuse the same capability-resolution engine for governance-pack dry-run/import, effective-policy responses, and runtime enforcement.
- Validate mapping outputs against the MCP tool registry and current grant-authority rules.
- Surface mapping provenance, unresolved capabilities, and stricter-local constraints in effective-policy and governance-pack UX.

### 5.2 Non-Goals

- Do not add user-scope mappings in v1.
- Do not add multiple adapter-contract versions in v1.
- Do not force-migrate all existing direct concrete policies into capability form.
- Do not redesign every downstream tool executor to query mappings directly.
- Do not introduce registry publishing, hand-authored Rego, or external OPA runtime dependencies.

## 6. Proposed Architecture

### 6.1 Canonical Resolution Pipeline

The canonical runtime path becomes:

1. collect authored MCP Hub policy inputs from profiles, assignments, path-scope objects, and overrides
2. build an `authored_policy_document`
3. extract declared capabilities from the authored policy
4. resolve capabilities through the highest-precedence active adapter mapping in scope
5. merge the resolved concrete effects with directly-authored concrete policy fields
6. produce a `resolved_policy_document`
7. apply existing runtime-only constraints such as path proof, workspace trust, credential availability, and approval checks
8. return the final effective policy plus provenance and diagnostics

This means governance packs and hand-authored MCP Hub policies share one runtime model.

### 6.2 Authored Versus Resolved Policy

The resolver should return both:

- `authored_policy_document`
- `resolved_policy_document`

And keep convenience fields derived from the resolved form:

- `allowed_tools`
- `denied_tools`
- `capabilities`
- `approval_policy_id`
- `approval_mode`

Rules:

- authored policy remains the merged user-configured intent
- resolved policy includes capability-mapping expansion
- runtime consumers use the resolved policy
- UI can explain the difference between declared intent and executable outcome

### 6.3 New MCP Hub Domain Objects

Add a new table and repo surface for capability mappings. Suggested fields:

- `id`
- `mapping_id`
- `owner_scope_type`
- `owner_scope_id`
- `capability_name`
- `adapter_contract_version`
- `title`
- `description`
- `resolved_policy_document_json`
- `supported_environment_requirements_json`
- `is_active`
- `created_by`
- `updated_by`
- timestamps

Design constraints:

- only one active mapping for the same `capability_name` in the same scope
- mappings are scope-owned like other MCP Hub objects
- `global`, `org`, and `team` only in v1

### 6.4 Services

#### McpHubCapabilityAdapterService

Owns:

- CRUD for capability mappings
- scope validation
- tool-registry-backed validation of resolved concrete effects
- grant-authority checks against mapping outputs
- preview/audit summaries for create and update

#### McpHubCapabilityResolutionService

Owns:

- capability lookup by effective scope context
- precedence handling: `team -> org -> global`
- unresolved-capability reporting
- resolved-effect provenance generation
- environment-requirement compatibility output

#### McpHubPolicyResolver

Extended responsibilities:

- produce authored and resolved policy documents
- call capability resolution after authored merge, before final effective-policy output
- preserve current assignment/profile/override precedence behavior
- expose mapping provenance and diagnostics in effective-policy responses

#### McpHubGovernancePackService

Dry-run and import should stop using `_SUPPORTED_PORTABLE_CAPABILITIES` and `_RUNTIME_APPROVAL_MODE_MAP` as the source of truth. Instead they should ask the resolution service for:

- resolved capabilities
- unresolved capabilities
- unsupported environment requirements
- stricter-local warnings
- final importability verdict

## 7. Resolution Semantics

### 7.1 Existing Precedence Stays In Place

Existing effective-policy precedence remains:

1. assignment/profile/path-scope/override resolution
2. authored merged policy document

Capability resolution happens after that authored merge, not before it.

### 7.2 Mapping Precedence

Mapping lookup precedence for a runtime context:

1. `team`
2. `org`
3. `global`

User-scoped policy resolution may still use the registry, but it only looks upward through the applicable team/org/global scopes.

### 7.3 Merge Rules

List-based concrete fields from mappings are union-merged with direct concrete fields:

- `allowed_tools`
- `denied_tools`
- `tool_names`
- `tool_patterns`

Scalar hints follow direct-authoritative semantics:

- direct authored scalar fields win
- mapping outputs may supply missing scalar values
- mappings must not silently replace explicit authored approval/path-scope choices

Unresolved capabilities grant nothing.

### 7.4 Runtime Narrowing

After mapping resolution, existing runtime services may narrow or block:

- path enforcement
- workspace trust checks
- external credential availability
- approval gates

Runtime may narrow or block. Runtime may never broaden beyond the authored-plus-resolved policy.

## 8. Provenance Model

Effective-policy responses should extend provenance beyond the current field-level authored sources.

Recommended provenance kinds:

- `profile`
- `profile_path_scope_object`
- `assignment_path_scope_object`
- `assignment_inline`
- `assignment_override`
- `capability_mapping`
- `runtime_constraint`

For mapping provenance, include:

- `capability_name`
- `mapping_id`
- `mapping_scope_type`
- `mapping_scope_id`
- `resolved_effects`
- `effect`: `merged | narrowed | blocked`

Recommended response split:

- top-level mapping summary for common UI display
- detailed provenance entries for drill-down

This avoids excessive payload noise while keeping the system explainable.

## 9. API And UI Surfaces

### 9.1 Backend API

Add MCP Hub management endpoints for:

- list capability mappings
- create capability mapping
- update capability mapping
- delete capability mapping
- preview/validate mapping before write

Effective-policy responses should add:

- `authored_policy_document`
- `resolved_policy_document`
- mapping summaries
- unresolved capabilities
- stricter-local warnings

Governance-pack dry-run responses should add:

- live mapping resolution diagnostics
- unresolved capability detail by scope
- stricter-local warnings sourced from the resolver

### 9.2 Frontend UI

Add a new MCP Hub tab:

- `Capability Mappings`

That tab should support:

- scope selection
- list/detail/edit for mappings
- preview of resolved concrete effects
- validation errors and warnings

Update effective-policy views such as persona policy summary to show:

- mapping-provided tool access
- scope source of the mapping
- unresolved capability warnings
- runtime narrowing notes

## 10. Failure Modes

Fail-closed behavior is required:

- no mapping found for a capability -> grant nothing
- duplicate active mappings in same scope -> reject on write
- invalid tool names/patterns relative to tool registry -> reject on write
- unsupported adapter contract version -> reject on write and on read if encountered
- missing grant authority for resolved concrete effects -> reject on write
- runtime cannot safely honor a resolved effect -> narrow or block with provenance

## 11. Migration Strategy

Migration is additive:

- existing direct concrete MCP Hub policies continue to work unchanged
- capability mappings are introduced as a new governance layer
- policy authors can begin using capabilities immediately
- governance-pack dry-run/import switches from hardcoded capability checks to the registry-backed resolver
- no forced rewrite of existing policy documents

Because mapping changes are retroactive, create/update actions should emit audit events and return preview summaries describing the concrete effects they will influence.

## 12. Testing Strategy

Coverage should include four levels.

### 12.1 Registry Storage And Validation

- migration coverage for the new table
- repo CRUD coverage
- scope validation
- uniqueness of active mappings per capability per scope
- tool-registry-backed validation
- grant-authority enforcement for mapping writes

### 12.2 Capability Resolution

- precedence `team -> org -> global`
- unresolved capability behavior
- authored-direct plus mapped-concrete merge behavior
- direct scalar override behavior
- environment-requirement compatibility warnings

### 12.3 Effective Policy And Runtime Integration

- policy resolver returns authored and resolved policy documents
- provenance includes mapping and runtime-constraint entries
- approval/path/external-access consumers still behave correctly with resolved policy
- runtime narrowing is visible and never broadens access

### 12.4 Governance Pack Parity

- dry-run/import uses the same resolution service
- import verdict matches live mapping availability
- changing mappings updates dry-run/runtime results without reimporting the pack

## 13. V1 Boundary

Include:

- capability mapping storage and validation
- scope-aware resolution service
- tool-registry-backed mapping validation
- authored versus resolved policy output
- effective-policy provenance and diagnostics for mappings
- governance-pack dry-run/import integration
- MCP Hub UI for capability mappings and visibility

Exclude:

- user-scope mappings
- multiple adapter contract versions
- executor-by-executor direct mapping lookups outside the canonical resolver
- automatic conversion of existing concrete policies into capabilities
- registry publishing and hand-authored Rego

## 14. Main Risks To Watch

- provenance payloads becoming too large or noisy
- mapping updates silently broadening runtime effects without adequate preview/audit
- direct-versus-mapped scalar precedence becoming ambiguous
- tool-registry validation being too weak and allowing stale mappings
- governance-pack dry-run diverging from the canonical runtime resolver

The right mitigation is to treat the resolver as the single runtime truth and keep all previews, dry-runs, and UI diagnostics aligned to that one path.
