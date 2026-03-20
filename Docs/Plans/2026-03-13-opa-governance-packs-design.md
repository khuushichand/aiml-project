# OPA Governance Packs Design

Date: 2026-03-13
Status: Approved
Scope: schema-first, file-based governance packs for MCP Hub, personas, and ACP/agent runtimes

## 1. Summary

Add portable `Governance Packs` that define reusable capability profiles, approval templates, persona templates, and assignment templates in a deployment-agnostic format. Packs are authored as YAML/JSON, compiled into a normalized intermediate representation, and emitted as deterministic OPA bundle artifacts for portability and offline policy validation.

`tldw` remains the runtime authority. Imported packs become immutable MCP Hub base objects, while each deployment applies local overlays for concrete tool mappings, path/workspace enforcement, credential bindings, and other environment-specific constraints.

The first version is intentionally narrow:

- schema-first authoring only
- capability-first permissions, not concrete tool ids
- file-based Git-friendly distribution
- immutable imported base plus local overlays
- generated OPA artifacts, not hand-authored Rego
- dry-run import compatibility reporting before any mutable runtime changes

## 2. User-Approved Decisions

Validated during brainstorming:

1. OPA is the portable policy-packaging and validation boundary, not the live runtime authority for every tool decision.
2. The shared artifact should be a `Governance Pack`, not only a tool-profile export.
3. The first real consumers are `tldw` deployments plus the project's ACP/agent runtimes through adapters.
4. Pack authoring in v1 is schema-first. Most users should not write Rego directly.
5. Packs are capability-first and deployment-agnostic rather than concrete-tool-first.
6. Imported packs remain immutable base state and deployments customize them through local overlays.
7. Distribution in v1 is file-based and Git-friendly rather than registry-backed.

## 3. Review-Driven Revisions

The design was pressure-tested against the current MCP Hub and persona work already in the repository. These revisions close the largest risks:

1. Make schema files the only authored source of truth. Generated OPA artifacts and imported MCP Hub objects are derived outputs.
2. Do not trust arbitrary imported Rego in v1. The server regenerates the bundle artifact from the schema/IR and validates digests rather than executing user-supplied policy code directly.
3. Keep pack contents limited to persona templates, not live persona state. Packs must not contain mutable memory, session history, or deployment-local draft state.
4. Keep portable approval semantics intentionally small. Approval intent travels as `allow`, `ask`, `deny`, and optionally `ask_on_broaden`, while runtime-specific approval details remain local.
5. Add stable per-object ids and manifest versions so local overlays can survive pack updates.
6. Require a dry-run compatibility report on import so unresolved capabilities, unsupported fields, and stricter local runtime constraints are explicit.
7. Reuse the repo's existing assignment/override provenance model so imported base plus overlay behavior stays explainable.
8. Treat path/workspace guarantees as portable intent, not portable concrete configuration. Real path proof remains a local runtime concern.
9. Because the repo does not currently ship an OPA runtime dependency, v1 keeps OPA artifacts mandatory for packaging and parity checks, but does not make live server execution depend on an external `opa` binary.

## 4. Current State In The Repo

The existing codebase already has most of the runtime policy pieces needed around OPA packaging:

- `MCP Hub` is the canonical control plane for tool governance, with permission profiles, assignments, approvals, overrides, and external access rules.
- The current design work already prefers capability-based policy authoring over raw tool allowlists.
- Runtime approval, path scope, shared workspace trust, and external credential bindings are already modeled inside `tldw`.
- Persona surfaces consume effective policy summaries rather than owning tool policy directly.
- MCP protocol execution already enforces allowed tools and effective policy gates at runtime.

What does not exist today:

- no OPA/Rego integration
- no portable governance-pack artifact
- no capability-to-runtime adapter contract that is explicitly versioned for portability
- no import/export domain for immutable governance-pack bases and local overlays

This means the new work should layer onto MCP Hub rather than create a second runtime policy engine.

## 5. Goals And Non-Goals

### 5.1 Goals

- Create a portable, reviewable, file-based governance-pack format for sharing agent/persona tool-access policy across deployments.
- Let pack authors define capability profiles, persona templates, approval templates, and assignment defaults without naming concrete local tools.
- Generate deterministic OPA bundle artifacts from pack source for portability, validation, and offline parity checks.
- Import approved packs into immutable MCP Hub base objects.
- Keep deployment-specific tool mappings, workspace/path rules, and credentials local and auditable as overlays.
- Support both `tldw` server surfaces and ACP/agent runtimes through adapters instead of duplicated policy authoring.
- Provide clear dry-run compatibility output before import.

### 5.2 Non-Goals

- Do not make OPA the live runtime authority for MCP tool execution in v1.
- Do not support hand-authored Rego modules in v1.
- Do not put secrets, credential material, file paths, workspace ids, or host-local server ids into shared packs.
- Do not export or import live persona memory, session history, or mutable companion state.
- Do not build OCI/registry publishing in the first release.
- Do not claim simulator parity for runtime-only facts such as credential presence, real path proof, or session-local context that the pack cannot know.

## 6. Proposed Architecture

### 6.1 Source-Of-Truth Pipeline

The pack lifecycle is:

1. Human-authored schema files
2. normalized intermediate representation (IR)
3. generated OPA bundle artifact
4. dry-run simulation and compatibility report
5. immutable MCP Hub base-object import
6. local overlays for deployment-specific runtime details

Rules:

- schema is canonical
- IR is deterministic and internal
- OPA bundle is generated output
- MCP Hub import is derived runtime state
- live execution continues to use local `tldw` enforcement

### 6.2 Governance Pack Shape

Suggested pack layout:

- `manifest.yaml`
- `profiles/*.yaml`
- `personas/*.yaml`
- `approvals/*.yaml`
- `assignments/*.yaml`
- `tests/*.yaml`
- `dist/opa/` generated only

Suggested manifest fields:

- `pack_id`
- `pack_version`
- `pack_schema_version`
- `capability_taxonomy_version`
- `adapter_contract_version`
- `title`
- `description`
- `authors`
- `compatible_tldw_versions`
- `compatible_runtime_targets`
- `content_digest`

### 6.3 Portable Objects

#### CapabilityProfile

Defines portable permissions and portable intent:

- stable `profile_id`
- title/description
- capability grants
- capability denies
- approval intent
- environment requirements
- optional semantic tags for adapter hints

#### ApprovalTemplate

Defines portable runtime posture:

- stable `approval_template_id`
- `allow | ask | deny | ask_on_broaden`
- optional duration classes or reuse hints that can be mapped locally if supported

#### PersonaTemplate

Defines a persona seed, not a live persona:

- stable `persona_template_id`
- display metadata
- base instructions/state overlays
- referenced capability profile
- referenced approval template
- persona traits or tags

Explicitly excluded:

- memory snapshots
- live sessions
- mutable workspace history
- deployment-local voice or secret material

#### AssignmentTemplate

Defines where templates want to attach in abstract terms:

- `default | group | persona`
- referenced profile/template ids
- default overlay posture
- optional adapter hints

### 6.4 OPA Role

OPA is used for:

- portable artifact packaging
- deterministic normalization output
- offline policy-parity checks
- pack-distributed compliance evidence

OPA is not used for:

- live MCP `tools/call` authority
- path canonicalization
- workspace trust proof
- credential-secret availability checks

Because the repo does not currently include an OPA runtime dependency, v1 should:

- generate deterministic bundle artifacts under `dist/opa/`
- support offline/CI parity checks where OPA tooling is available
- keep server dry-run import decisions grounded in the normalized IR and local adapter contracts

This preserves the portability benefit without introducing a brittle hard dependency for every runtime path on day one.

### 6.5 Capability Taxonomy

Packs must use a small, versioned, semantic capability taxonomy. Examples:

- `filesystem.read`
- `filesystem.write`
- `process.execute.safe`
- `network.external.search`
- `network.external.fetch`
- `mcp.server.connect`
- `tool.invoke.research`
- `tool.invoke.notes`
- `tool.invoke.code_edit`

Portable environment requirements travel separately:

- `workspace_bounded_read`
- `workspace_bounded_write`
- `no_external_secrets`
- `local_mapping_required`

These are intent signals. They do not directly configure a concrete path scope or tool allowlist by themselves.

### 6.6 Adapter Contract

Each deployment needs a local adapter that maps portable capability intent onto concrete runtime constructs:

- MCP tool names
- modules
- catalogs
- external server bindings
- path/workspace enforcement modes
- approval-policy ids

The adapter contract should be explicit and versioned. Required outputs:

- `resolved_capabilities`
- `unresolved_capabilities`
- `approval_mappings`
- `dropped_fields`
- `warnings`
- `confidence`

If a required capability cannot be mapped, import must fail closed or mark that object non-importable. The system must never silently broaden access to compensate.

## 7. Import, Overlay, And Upgrade Model

### 7.1 Import Flow

The server should support this sequence:

1. validate pack schema
2. normalize to IR
3. regenerate the OPA artifact locally
4. run portable decision tests against the IR and artifact parity contract
5. evaluate the local adapter mapping
6. produce a dry-run report
7. import immutable base objects only after explicit confirmation

### 7.2 Dry-Run Compatibility Report

A dry-run report is required before import. Minimum contents:

- manifest summary
- pack digest
- resolved capabilities
- unresolved capabilities
- approval mappings
- unsupported fields
- local runtime constraints that are stricter than the pack
- importable vs blocked objects
- final import verdict

### 7.3 Immutable Base Plus Local Overlays

Imported pack content remains immutable base state.

Deployments customize behavior through local overlays:

- concrete tool mappings
- assignment overrides
- external credential bindings
- workspace/path scoping
- environment-specific exceptions

The overlay system should reuse the repo's current MCP Hub precedence rules:

1. default assignment
2. group assignment
3. persona assignment
4. assignment override

Within one assignment:

1. imported profile/template base
2. assignment inline content
3. assignment override

### 7.4 Provenance

Effective policy responses should expose enough provenance to answer:

- which values came from the imported pack
- which values came from a local overlay
- which values were unresolved or dropped during import

This should be additive to the existing provenance model rather than a replacement.

### 7.5 Upgrade Semantics

Pack-managed objects need stable ids so upgrades can rebase without destroying local overlays.

Minimum upgrade rules:

- same pack id + newer version may update immutable base objects
- local overlays remain separate
- deleted upstream objects are reported, not silently removed
- incompatible schema/taxonomy versions block upgrade

## 8. Error Handling And Trust Boundaries

Core rules:

- unresolved capability -> deny or block import, never silent allow
- unsupported approval template -> block import
- missing referenced profile/template -> block import
- runtime cannot prove portable environment requirement -> local runtime may escalate to approval or deny
- imported bundle digest mismatch -> block import
- local adapter ambiguity -> fail closed with explicit diagnostics

Trust rules:

- imported packs are untrusted until locally validated
- generated OPA artifacts are derived from validated schema
- pack authors cannot inject runtime secrets or local path grants
- live server execution always prefers stricter local runtime truth over portable intent

## 9. Testing Strategy

Testing should happen at four layers.

### 9.1 Schema And IR Validation

Verify:

- manifest validation
- object reference integrity
- stable id requirements
- taxonomy version checks

### 9.2 Artifact Generation

Verify:

- deterministic IR output
- deterministic OPA bundle output
- digest stability for the same source pack
- clear diffs for changed source input

### 9.3 Dry-Run Import And Adapter Validation

Verify:

- required capabilities resolve or fail explicitly
- unsupported approval fields are surfaced
- unresolved pack objects are blocked
- imported objects are tagged with source pack provenance

### 9.4 Runtime Parity Boundaries

Verify:

- imported base + overlay yields expected effective policy for the portable subset
- runtime remains allowed to be stricter for path, workspace, credential, and session constraints
- persona and ACP-facing policy summaries show pack provenance without claiming live persona state came from the pack

## 10. V1 Scope

### 10.1 Include

- governance-pack schema definitions
- normalized IR generation
- deterministic OPA artifact generation
- dry-run import report
- immutable base import into MCP Hub
- pack metadata/provenance storage
- local overlay compatibility
- persona-template import
- capability mapping failure reporting
- file-based examples and fixtures

### 10.2 Exclude

- hand-authored Rego
- OPA as the live tool-execution authority
- registry publishing/OCI
- secrets and credential export/import
- concrete workspace/path declarations in packs
- live persona/session export
- third-party runtime adapters beyond `tldw` and ACP-facing surfaces

## 11. Recommended Next Slice

The first implementation slice should focus on:

1. schema and IR definition
2. deterministic artifact generation
3. dry-run import and provenance storage
4. immutable base import into MCP Hub
5. minimal MCP Hub UI for preview/import and pack inventory

This sequence delivers the portability contract without destabilizing the current runtime enforcement model.
