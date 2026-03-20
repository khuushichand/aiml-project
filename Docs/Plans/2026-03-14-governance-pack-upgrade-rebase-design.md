# Governance Pack Upgrade And Rebase Design

Date: 2026-03-14
Status: Approved
Scope: transactional in-place governance-pack upgrades with explicit dependency rebasing and active-install runtime filtering

## 1. Summary

Add a `Governance Pack Upgrade Planner` and `Governance Pack Upgrade Executor` to MCP Hub so an installed governance pack can be upgraded in place to a newer version of the same `pack_id` within the same owner scope.

Imported governance-pack base objects remain immutable. Upgrades do not mutate the old base objects. Instead, the system validates a new target pack version, computes an explicit upgrade plan keyed by stable source object ids, materializes the new immutable base set, rebinds direct dependents that point at imported object ids, atomically marks the new version as the active install, and retains lineage for the superseded version.

The design is intentionally conservative:

- upgrades are same-pack, same-scope only
- structural and behavioral conflicts block execution
- manual conflict resolution only in v1
- local overlays are preserved only when the system can prove their attachment remains valid
- runtime resolution must honor only the active installed pack version for a given `pack_id + scope`

## 2. User-Approved Decisions

Validated during brainstorming:

1. Upgrades should use a transactional in-place rebase model rather than parallel install or reinstall-only workflows.
2. If a local overlay or dependent object references a pack-managed object that no longer exists in the new version, the upgrade must block until resolved.
3. Conflict detection in v1 should include structural conflicts and behavioral conflicts, not only raw missing-object failures.
4. Upgrade history should be represented as explicit lineage records rather than only ordinary audit events.
5. Conflict resolution in v1 is manual only.
6. Upgrades may not cross scope boundaries for the same `pack_id`.

## 3. Review-Driven Revisions

Pressure-testing the proposal against the current governance-pack implementation produced these corrections:

1. Add explicit active-install state to governance packs. Today imported objects live directly in the same MCP Hub tables as any other runtime objects, so superseded pack objects must be filtered out of live resolution.
2. Recognize naming collisions in the current importer. Imported object names are currently derived from `pack_id:source_object_id`, so naive side-by-side staging would collide with uniqueness rules unless the staging strategy changes.
3. Split “overlay preservation” from “direct dependent rebinding.” Some local mutable objects merge with imported state conceptually, while others hold explicit foreign-key references to imported object ids and therefore must be rebound atomically during upgrade.
4. Narrow v1 conflict detection to explicit dependency edges and stable source-object ids rather than vague “effective-policy path” inference.
5. Treat adapter-registry state as a fingerprinted planning input, separate from pack identity. Pack diff conflicts and deployment mapping drift are related but distinct concerns.
6. Define pack-version ordering explicitly. The current `pack_version` field is a string, so upgrade ordering must follow a documented semantic-version comparison rule.
7. Restrict the runtime-object diff set in v1 to what governance-pack import actually installs today: approval policies, permission profiles, and policy assignments. Persona templates remain pack content but are not imported as first-class MCP Hub runtime objects in the current implementation.
8. Require a real transaction seam for execute-upgrade. The existing governance-pack import path uses best-effort rollback and is not sufficient for upgrade cutover.

## 4. Current State In The Repo

The current implementation already provides a useful base:

- Governance packs are stored in `mcp_governance_packs` with manifest and normalized IR.
- Imported object inventory is stored in `mcp_governance_pack_objects`, keyed by `governance_pack_id`, `object_type`, and `source_object_id`.
- Imported approval policies, permission profiles, and policy assignments are persisted as ordinary immutable MCP Hub rows.
- Imported objects include governance-pack metadata in their stored JSON payloads.
- Capability mappings and ACP runtime policy now flow through the shared MCP Hub effective-policy model.

Important current limitations:

- there is no active/superseded install state on governance packs
- runtime resolution does not currently filter governance-pack-owned objects by active install
- imported object names are unique per scope and derived from `pack_id:source_object_id`, which prevents naive side-by-side installs of another version
- there is no first-class upgrade lineage table
- there is no transaction-backed upgrade executor
- persona templates are not imported as standalone MCP Hub runtime objects

This means the upgrade design must extend the existing governance-pack model rather than assume a separate shadow install system already exists.

## 5. Goals And Non-Goals

### 5.1 Goals

- Support safe upgrades from one governance-pack version to a newer version of the same `pack_id` in the same scope.
- Preserve immutable imported base objects while still allowing in-place administrative upgrade semantics.
- Detect structural and behavioral upgrade conflicts before execution.
- Preserve local overlays and dependent mutable objects only when their attachment can be validated and, when required, deterministically rebound.
- Add explicit lineage and auditability for pack upgrades.
- Ensure runtime policy resolution only considers the active installed version of a governance pack per scope.

### 5.2 Non-Goals

- Do not support cross-scope upgrades in v1.
- Do not support heuristic or fuzzy remapping.
- Do not provide automatic conflict repair in v1.
- Do not implement one-click rollback UX in v1.
- Do not expand v1 upgrade diffing to persona-template runtime objects that do not yet exist.
- Do not retain multiple active pack versions for the same `pack_id + scope`.

## 6. Proposed Architecture

### 6.1 Upgrade Identity Rules

An upgrade is only valid when all of the following are true:

- same `pack_id`
- same `owner_scope_type`
- same `owner_scope_id`
- target `pack_version` is newer than the currently active installed version
- target `pack_schema_version`, `capability_taxonomy_version`, and `adapter_contract_version` are compatible with the current runtime

Version ordering should use semantic-version parsing in v1. If the version cannot be parsed under the supported rules, dry-run upgrade should reject it explicitly.

### 6.2 Canonical Upgrade Pipeline

The canonical lifecycle becomes:

1. locate the currently active installed governance pack for `pack_id + scope`
2. normalize and validate the target pack
3. compare installed normalized IR to target normalized IR using stable `source_object_id` keys
4. compute dependency and rebinding impact for local mutable objects that point at imported object ids
5. snapshot planner inputs, including current adapter-registry fingerprint
6. return an upgrade plan with conflicts, warnings, and an upgradeable verdict
7. if clean, execute upgrade inside a transaction-backed cutover path
8. mark the target version active and mark the prior version superseded
9. persist lineage and audit metadata

### 6.3 Active Install Model

Governance packs need explicit install-state fields:

- `is_active_install`
- `superseded_by_governance_pack_id`
- optional `installed_from_upgrade_id`

Only one active installed row may exist for a given `(pack_id, owner_scope_type, owner_scope_id)`.

Runtime consumers must ignore imported objects associated with superseded governance-pack installs. This requires resolver/repo filtering so that inactive versions remain auditable but not live.

### 6.4 Immutable Base, Mutable Dependents

Imported governance-pack base objects remain immutable. Upgrades do not mutate those rows.

However, local mutable objects fall into two categories:

1. `merge-only overlays`
   - local state that combines with imported base through resolver precedence
   - no direct foreign-key reference to a specific imported object id

2. `direct dependents`
   - local mutable objects that explicitly reference imported object ids
   - examples include assignments or other stored objects holding `profile_id` or `approval_policy_id`

Direct dependents must be rebound during a successful upgrade if their referenced imported object survives under the same stable source id in the new pack version. If rebinding cannot be proven safe, the upgrade blocks.

## 7. Upgrade Planner

### 7.1 Planner Inputs

The upgrade planner should take:

- active installed governance-pack row
- active installed imported-object inventory
- target pack manifest and normalized IR
- current local mutable dependents and overlays in the same scope
- current adapter-registry fingerprint and relevant mapping summaries

### 7.2 Upgrade Plan Output

The planner should produce:

- `identity_check`
- `compatibility_check`
- `pack_version_ordering`
- `object_diff`
- `dependency_impact`
- `adapter_state_fingerprint`
- `conflicts`
- `warnings`
- `upgradeable`

### 7.3 Diff Model

Diffs key off stable `source_object_id`, not local MCP Hub row ids.

V1 runtime-object types:

- `approval_policy`
- `permission_profile`
- `policy_assignment`

For each source object id:

- `unchanged`
- `added`
- `removed`
- `modified`

Persona templates may still appear in manifest-level informational diff output, but they are not treated as installed runtime-object diff entities in v1 unless persona-template import becomes real first.

## 8. Conflict Model

### 8.1 Structural Conflicts

These always block:

- different `pack_id`
- different scope
- older or equal target version
- incompatible schema/taxonomy/adapter contract
- missing or duplicate stable source ids
- removed imported runtime object that still has direct dependents
- source object changes kind in a way that breaks rebinding

### 8.2 Behavioral Conflicts

These block when they affect a locally dependent runtime path:

- approval template change from one portable posture to another for an imported approval policy that still has local dependents
- permission profile capability grants/denies change for an imported profile referenced by local dependents
- imported assignment changes target semantics or referenced source ids in a way that invalidates dependent local assumptions

Behavioral conflict detection should use explicit dependency edges and known semantic fields, not generic full-policy diff heuristics.

### 8.3 Adapter Drift

Adapter-registry drift is not pack identity, but it matters operationally.

The planner should snapshot an adapter-state fingerprint and classify these separately:

- newly unresolved capabilities under current mappings
- materially changed mapping summaries for modified imported profiles
- stricter runtime implications due to current adapter state

In v1:

- unresolved capabilities affecting an active imported runtime path are blocking
- stricter runtime implications that do not orphan dependencies may be warnings

### 8.4 Warning-Only Diffs

Warnings include:

- added imported objects with no dependents
- removed imported objects with no dependents
- manifest metadata changes with no runtime impact
- target pack adds capabilities that are currently resolved but stricter than before

## 9. Execution Model

### 9.1 Transaction-Backed Cutover

Execute-upgrade should use a real repo/database transaction, not best-effort rollback.

Execution flow:

1. acquire a scope-local upgrade lock for `(pack_id, owner_scope_type, owner_scope_id)`
2. regenerate and validate the plan against current state
3. reject execution if planner inputs changed, including adapter fingerprint drift or dependent-object changes
4. materialize the target governance-pack row and imported immutable base objects
5. build a deterministic old-id -> new-id rebinding map from stable source ids
6. atomically rebind direct dependents where allowed by the approved plan
7. mark the old install superseded
8. mark the new install active
9. persist lineage record and audit metadata
10. commit transaction

If any step fails, the transaction must roll back and the old active install must remain live.

### 9.2 Naming And Uniqueness

Because imported object names are unique by scope and currently omit pack version, staging a new imported base beside the current one would collide.

V1 must solve this explicitly. Two pragmatic options were considered:

- add version-aware imported names during upgrade materialization
- introduce a dedicated staging mechanism that does not rely on live unique names

Recommendation for v1: include pack version in imported object names during materialization for governance-pack-owned rows. The display layer can still present cleaner titles while the persisted unique name remains collision-safe and traceable.

### 9.3 Runtime Filtering

Resolver and listing logic that considers governance-pack-owned rows must ignore objects belonging to superseded packs unless the API explicitly asks for history.

This is required so lineage retention does not accidentally broaden or duplicate live effective policy.

## 10. Data Model And API

### 10.1 Persistence Additions

Suggested additions to `mcp_governance_packs`:

- `is_active_install`
- `superseded_by_governance_pack_id`
- `installed_from_upgrade_id`

Add `mcp_governance_pack_upgrades`:

- `id`
- `pack_id`
- `owner_scope_type`
- `owner_scope_id`
- `from_governance_pack_id`
- `to_governance_pack_id`
- `from_pack_version`
- `to_pack_version`
- `status`
- `planned_at`
- `executed_at`
- `planned_by`
- `executed_by`
- `planner_inputs_fingerprint`
- `adapter_state_fingerprint`
- `plan_summary_json`
- `accepted_resolutions_json`
- `failure_summary`

### 10.2 API Surfaces

Add:

- `POST /governance-packs/dry-run-upgrade`
- `POST /governance-packs/execute-upgrade`
- `GET /governance-packs/{id}/upgrade-history`

Dry-run response should include:

- source install summary
- target manifest summary
- object diff summary
- direct dependent impact summary
- blocking conflicts
- warnings
- planner-input fingerprint
- adapter-state fingerprint
- upgradeable verdict

### 10.3 UI Surfaces

In MCP Hub governance-pack UI:

- installed pack detail shows active/inactive state and upgrade history
- dry-run upgrade modal shows added/removed/modified imported objects
- modal calls out blocked dependents and required manual actions
- execute button is disabled when blocking conflicts exist

Because v1 is manual-resolution only, the UI should point admins at the blocking dependent objects rather than trying to mutate them directly inside the upgrade modal.

## 11. Failure Modes And Rollback

Failure modes:

- identity mismatch
- incompatible runtime versions
- stale planner inputs
- unresolved capability drift under current adapter state
- dependent rebinding failure
- uniqueness collision during target materialization
- transaction failure during cutover

Required behavior:

- dry-run rejects before execution when possible
- execute-upgrade revalidates current state
- transaction rollback preserves old active install on any failure
- lineage and audit log retain failure context for diagnosis

Rollback in v1 is not a dedicated destructive action. Instead, because superseded versions remain in lineage, admins can perform a normal validated upgrade back to a prior compatible version if needed.

## 12. Testing Strategy

### 12.1 Planner Tests

- same-pack newer-version accepted
- cross-scope rejected
- invalid semantic-version ordering rejected
- removed imported object with dependent blocks
- modified imported object with dependent semantic conflict blocks
- warnings-only plan when no dependent exists
- adapter-fingerprint drift classified correctly

### 12.2 Executor Tests

- successful transactional cutover
- stale plan rejected
- lock prevents concurrent upgrades
- direct dependents rebound to new imported object ids
- transaction failure preserves old active install

### 12.3 Runtime Tests

- effective policy uses only active installed pack objects
- superseded pack objects do not contribute to live effective policy
- unchanged local overlays/dependents still resolve correctly after upgrade

### 12.4 API/UI Tests

- dry-run upgrade report rendering
- execute disabled on conflicts
- upgrade history visible
- lineage metadata exposed correctly

## 13. Recommended V1 Boundary

Include:

- active/superseded install state
- semantic-version ordering for upgrades
- planner keyed by installed normalized IR and stable source ids
- explicit dependency-graph conflict detection
- adapter-state fingerprinting in plans
- transaction-backed execute-upgrade
- deterministic rebinding of direct dependents
- runtime filtering to active installed versions only
- upgrade lineage records and MCP Hub UI visibility

Exclude:

- heuristic remapping
- automatic conflict repair
- cross-scope upgrades
- one-click rollback UX
- persona-template runtime-object upgrades unless persona-template import becomes real first

## 14. Recommendation

Implement governance-pack upgrades as a transactional in-place rebase of immutable base objects, with explicit active-install tracking, explicit dependent-object rebinding, and runtime filtering to the active version only.

This is the most pragmatic long-term shape because it preserves the design guarantees already established for governance packs:

- imported base remains immutable
- local mutable state remains separate and auditable
- upgrades are explainable and safe
- runtime policy stays authoritative and deterministic

Anything looser than this would either break immutability, orphan local state, or make policy provenance too ambiguous to trust.
