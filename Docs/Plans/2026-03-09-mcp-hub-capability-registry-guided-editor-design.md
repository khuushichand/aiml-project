# MCP Hub Capability Registry And Guided Editor Design

Date: 2026-03-09
Status: Approved for planning

## Summary

The next MCP Hub PR should add a derived tool capability registry and use it to drive two existing MCP Hub surfaces:

- the Catalog tab
- the profile and assignment editors in simple mode

This PR is the bridge between the policy engine that already exists and a policy authoring experience that ordinary users can actually use. The registry is derived from MCP tool definitions and normalization rules at startup. It is not user-authored in this phase.

## Why This Is The Next PR

The first MCP Hub tool-governance PR shipped:

- durable policy storage
- CRUD APIs for profiles, assignments, and approvals
- effective policy resolution
- runtime approvals
- persona-side approval prompts and policy summary

What is still missing is the machine-readable tool metadata and guided editor model that the original governance design depends on. The current UI is still document-first and hardcodes capabilities. The current catalog is still just a scope/list surface.

Without a registry-backed editor, MCP Hub still asks users to think in terms of raw allowlists and policy blobs instead of the capability-based controls the product goal calls for.

## Goals

- Add a canonical, derived registry of MCP tool governance metadata.
- Use the same registry DTO for the Catalog tab and the simple-mode policy editor.
- Replace hardcoded UI capability lists with registry-backed grouped controls.
- Ship structured preset generation for the core built-in profiles.
- Keep runtime behavior aligned with what the editor actually promises today.

## Non-Goals

- Adding a user-editable capability registry.
- Full path-bounded or resource-bounded enforcement for every tool.
- Override CRUD and explainability provenance UI.
- Credential binding management or external-server precedence cleanup.
- Reworking runtime temporary elevation semantics.

## Current Constraints

- Tool metadata exists today, but it is inconsistent and partial. Tool definitions can carry `metadata`, and runtime code already uses heuristic checks such as `metadata.category` and name-based write detection.
- Runtime enforcement is still centered on `allowed_tools` pattern matching and approval mode logic, not full capability family enforcement.
- The MCP Hub editors currently rely on hardcoded capability lists and freeform allow/deny text.
- The current Catalog tab does not expose the metadata needed to support a guided authoring flow.

These constraints mean the next PR must improve authoring and classification without pretending that every proposed future capability constraint is already enforceable.

## Core Decisions

### 1. The first registry is derived, not administered

The registry must be generated from MCP tool definitions plus server-side normalization rules.

Reasons:

- avoids a second source of truth
- keeps metadata close to tool definitions
- makes the catalog/editor reflect real server state
- prevents an admin UI from drifting away from runtime behavior

If a tool definition is missing metadata, the registry should classify it conservatively rather than invent confidence.

### 2. The registry must expose one canonical DTO

The registry output should be the single normalized shape consumed by:

- MCP Hub catalog enrichment
- simple-mode profile editing
- simple-mode assignment editing
- approval sensitivity decisions where applicable

This avoids having the catalog and editor each invent their own metadata interpretation layer.

### 3. The editor must support safe dual-mode authoring

The new simple mode should sit alongside the current advanced/document mode.

Rules:

- simple mode edits should generate policy documents from structured controls
- advanced mode should continue to expose raw allow/deny document editing
- if a stored policy contains fields that simple mode cannot faithfully round-trip, the UI should show an `advanced fields present` warning and avoid destructive rewrites

This is necessary to keep backward compatibility with the first PR and with power-user manual policy documents.

### 4. The PR must not over-promise enforcement

The simple editor should only expose controls that map cleanly to runtime behavior that exists today or can be added safely in the same PR.

That means this PR should support:

- tool group and tool-level allowlists
- broad capability toggles used for profile generation
- sensitivity-aware approval configuration
- read/write/process/network/credential classifications for UX and audit

It should not claim per-path or per-resource guarantees that the runtime cannot yet enforce.

## Registry Data Model

The registry is a derived read model, not a persistent policy object in this phase.

### Registry entry

Each tool registry entry should include:

- `tool_name`
- `display_name`
- `module`
- `category`
- `risk_class`
- `capabilities`
- `mutates_state`
- `uses_filesystem`
- `uses_processes`
- `uses_network`
- `uses_credentials`
- `supports_arguments_preview`
- `path_boundable`
- `metadata_source`
- `metadata_warnings`

### Field semantics

- `category`
  - coarse existing classification such as `read`, `search`, `management`, `ingestion`, `execution`
- `risk_class`
  - normalized class used by the UI and approval logic
  - recommended values: `low`, `medium`, `high`, `unclassified`
- `capabilities`
  - normalized capability family list, such as `filesystem.read`, `process.execute`, `network.external`
- `metadata_source`
  - shows whether the entry came from explicit tool metadata, heuristics, or fallback normalization
- `metadata_warnings`
  - non-fatal notes used to highlight tools that require review because their metadata is incomplete or inferred

### Conservative fallback

If metadata is incomplete:

- default `risk_class` to `unclassified`
- mark `metadata_source` as `heuristic` or `fallback`
- attach warnings
- avoid placing the tool in low-risk presets unless explicitly allowed by normalization rules

## Registry Derivation Rules

Registry derivation should follow this order:

1. Read explicit tool metadata from the MCP tool definition.
2. Normalize known metadata keys to the canonical registry fields.
3. Apply module-specific normalization rules for built-in tools where metadata is known to be incomplete.
4. Apply conservative heuristics as a final fallback.
5. Emit warnings when heuristics were required.

### Example normalization

- `metadata.category = "ingestion"` implies:
  - `mutates_state = true`
  - `risk_class` at least `medium`
- shell/command execution tools imply:
  - `capabilities` includes `process.execute`
  - `uses_processes = true`
  - `risk_class = high`
- external service tools imply:
  - `uses_network = true`
  - `capabilities` includes `network.external`
- secret-bearing tools imply:
  - `uses_credentials = true`
  - `capabilities` includes `credentials.use`

## Backend Changes

### New registry service

Add a dedicated service that:

- enumerates the effective MCP tool definitions
- normalizes them into registry entries
- groups them by module
- exposes filtering helpers for presets and editor surfaces

This should be implemented as a read service, not a persistence layer.

### New MCP Hub API surface

Expose registry-backed read endpoints through MCP Hub:

- list registry entries
- list modules/groups
- return registry metadata for a specific tool
- optionally return derived preset templates built from the registry

### Catalog enrichment

The existing catalog read path should include registry metadata so the Catalog tab can show:

- module/group
- risk badge
- capability tags
- metadata warnings

## Guided Editor Design

### Simple mode

Simple mode should present grouped controls such as:

- file reading
- file writing
- destructive file actions
- command execution
- external service access
- credential usage
- tool groups/modules

The controls generate a policy document from registry-backed mappings. This replaces the current hardcoded capability set as the default authoring path.

### Advanced mode

Advanced mode remains available for:

- raw capability list editing
- raw allow/deny pattern editing
- unsupported legacy fields

### Round-trip safety

If the stored policy document includes fields or patterns that the simple editor cannot preserve exactly:

- show a warning
- keep advanced mode as the source of truth
- do not silently flatten or discard advanced data

## Presets

Presets should remain normal profiles, but their generation should be registry-backed.

Recommended built-ins:

- `No Additional MCP Restrictions`
- `Read Only`
- `Read Current Folder`
- `RW Current Folder`
- `External Services`

Important note:

`No Security` is a misleading label because platform ceilings, RBAC, and auth scopes still apply. The preset should be renamed to avoid implying that all restrictions are gone.

## Runtime Alignment

This PR should align the editor and runtime where feasible, but it should not attempt to solve full capability enforcement.

Scope for runtime alignment in this PR:

- use registry risk class to support `ask_on_sensitive_actions`
- keep `allowed_tools` pattern enforcement as the actual execution gate
- ensure preset generation produces patterns and capabilities consistent with the current enforcement model

Out of scope:

- universal per-path enforcement
- universal per-credential binding enforcement
- per-argument sandboxing for every tool type

## Testing Requirements

### Backend

- registry normalization tests for built-in tools
- fallback classification tests for incomplete metadata
- API tests for enriched registry/catalog responses
- resolver/protocol parity tests for registry-backed preset output

### Frontend

- simple-mode profile generation tests
- simple-mode assignment generation tests
- advanced-fields-present guard tests
- catalog rendering tests for risk badges and warnings

## Risks And Mitigations

### Risk: metadata drift between tools and registry

Mitigation:

- derive the registry at runtime from tool definitions
- keep normalization rules server-side and tested

### Risk: simple mode corrupts advanced policies

Mitigation:

- add explicit non-round-trippable detection
- keep advanced mode as fallback

### Risk: external tool metadata is weak or malformed

Mitigation:

- conservative classification
- `unclassified` risk class
- warning badges in the catalog and editor

### Risk: the UI exposes controls the runtime cannot enforce

Mitigation:

- limit simple-mode controls to what maps cleanly to current runtime behavior
- defer path-bounded and credential-bounded controls to later PRs

## Recommended Rollout

### Phase 1

- add derived registry service
- add registry read APIs
- enrich Catalog tab

### Phase 2

- add guided simple mode for profiles
- add guided simple mode for assignments
- keep advanced mode available

### Phase 3

- switch presets to registry-backed generation
- align approval sensitivity decisions with registry risk classes

## Follow-Up PRs After This One

- Policy overrides and effective-policy provenance
- Credential bindings and external-server precedence
- Path-bounded capability enforcement
- More explicit grant-authority visualization in the UI
