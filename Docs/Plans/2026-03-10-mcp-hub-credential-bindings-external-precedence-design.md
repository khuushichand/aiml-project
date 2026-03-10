# MCP Hub Credential Bindings And External-Server Precedence Design

Date: 2026-03-10
Status: Approved for planning

## Summary

The next MCP Hub PR should make MCP Hub the canonical control plane for external MCP
server definitions and server-level credential access.

This phase is intentionally narrow:

- DB-backed MCP Hub server definitions become the authoritative executable source
- file/env-defined external servers remain visible only as legacy migration inventory
- credential bindings are server-level only
- bindings can attach to permission profiles and policy assignments
- assignment bindings can add or disable inherited server access
- imported legacy auth config must be normalized for managed runtime use

The goal is to remove the current split-brain model where MCP Hub stores external
server rows and secrets while the live federation runtime still executes only the
file/env registry.

## Why This Is The Next PR

The MCP Hub avenue now has:

- durable policy storage
- profiles, assignments, approvals, overrides, and provenance
- registry-backed tool editing
- path-scoped local enforcement

The biggest remaining governance gap is external services.

Right now:

- MCP Hub already exposes external server CRUD and encrypted secret storage
- the UI only covers a small secret-rotation subset
- the live federation module still loads executable server definitions from YAML/env
- credential bindings exist in schema only, not as a real governance surface

That means external-service access is still governed by two partial systems instead
of one coherent MCP Hub policy domain.

## Goals

- Make DB-backed MCP Hub server definitions the canonical executable source.
- Surface file/env-defined servers as read-only legacy inventory during migration.
- Add server-level credential bindings for permission profiles and policy assignments.
- Resolve effective external access from profile bindings, assignment bindings, and
  tool policy.
- Prevent legacy inventory rows from remaining a second live execution authority.
- Expand MCP Hub UI to manage external servers, import legacy entries, and edit
  bindings.

## Non-Goals

- Per-secret-slot or per-header credential binding.
- Automatic extraction or copying of env secrets into MCP Hub.
- Permanent dual-source execution of both DB and file/env server registries.
- Broad redesign of upstream external transport protocols.
- Arbitrary secret-provider plugins beyond the current encrypted secret store.

## Current Constraints

- MCP Hub stores external servers in `mcp_external_servers` and one encrypted secret
  per server in `mcp_external_server_secrets`.
- The live external federation runtime still initializes exclusively from
  `MCP_EXTERNAL_SERVERS_CONFIG`.
- Runtime auth resolution currently depends on env-oriented config fields such as
  `token_env` and `api_key_env`.
- `mcp_credential_bindings` already exists, but it is generic and does not enforce
  the v1 binding invariants.
- Current external-server API responses do not expose `managed`, `legacy`, or
  `superseded` state.

These constraints mean the design must include both a runtime source-of-truth shift
and an auth-model bridge, not just new CRUD endpoints.

## Core Decisions

### 1. Managed MCP Hub servers are authoritative and executable

DB-backed MCP Hub server definitions are the only executable external servers in
this phase.

Legacy file/env servers remain visible in MCP Hub as migration inventory, but are
not a peer runtime authority.

This removes the current ambiguity where the UI suggests MCP Hub ownership while
the runtime still executes file/env config directly.

### 2. Legacy servers are inventory-only until imported

Legacy entries discovered from file/env config should appear in MCP Hub with:

- `server_source = legacy`
- read-only details
- no binding controls
- one primary action: `Import to MCP Hub`

Once imported:

- the managed copy becomes authoritative
- the legacy row becomes `superseded`
- the runtime must stop executing the legacy source for that `server_id`

### 3. Credential bindings are server-level and target profiles or assignments

Bindings are access grants, not secret containers.

V1 supports only server-level grants:

- no per-secret slot targeting
- no header-by-header binding

Bindings can target:

- permission profiles
- policy assignments

Assignment bindings may:

- add a managed server
- disable a managed server inherited from the linked profile

### 4. Cross-scope binding is narrower-to-broader only

Binding targets may reference servers owned by:

- the same owner scope, or
- a broader visible shared scope

Examples:

- a team assignment may bind team, org, or global servers
- a user assignment may bind user, team, org, or global servers it can already see
- an org profile may not bind a user-owned server

This prevents private lower-scope servers or secrets from being attached to broader
shared policy objects.

### 5. Imported managed servers preserve `server_id`

External virtual tool names are derived from `server_id`, so imported managed
servers should preserve the legacy `server_id`.

That keeps tool names stable and avoids introducing new virtual names during
migration.

Because of that choice, import must also immediately mark the legacy entry as
non-executable or superseded for runtime purposes. Managed and legacy copies of the
same `server_id` must not both remain executable.

### 6. Managed auth needs a runtime hydration bridge

The current runtime resolves auth from environment-variable references, while MCP
Hub stores a secret blob encrypted at rest.

This PR must define a managed auth bridge that can produce runtime auth material for
managed servers from:

- managed server config
- encrypted MCP Hub secret

The first version should stay narrow and support only auth shapes the server can
hydrate safely:

- no auth
- bearer token
- API key header

Imported legacy configs that currently use `*_ENV` auth modes must be normalized on
import rather than copied verbatim into managed runtime state.

## Data Model

### `mcp_external_servers`

Extend the managed server row model with:

- `server_source`
  - `managed`
  - `legacy`
- `legacy_source_ref`
  - stable identifier or path-derived ref for the file/env source record
- `superseded_by_server_id`
  - nullable managed server id for legacy rows that were imported

Managed rows remain the editable source.
Legacy rows are read-only inventory records.

### `mcp_external_server_secrets`

Keep the current one-secret-per-server model in this phase.

Secrets remain:

- encrypted at rest
- write-only in the UI
- never copied automatically from env on import

### `mcp_credential_bindings`

Keep the existing table but tighten it for v1:

- `binding_target_type`
  - constrained to `profile` or `assignment`
- `binding_target_id`
  - required
- `external_server_id`
  - managed server only
- `credential_ref`
  - reserved constant for this phase, e.g. `server`
- `binding_mode`
  - `grant`
  - `disable`
- `usage_rules_json`
  - remains reserved for future, keep empty or narrowly scoped

Required invariants:

- unique `(binding_target_type, binding_target_id, external_server_id)`
- no binding may reference a legacy or superseded server
- `disable` is only valid for assignment-target bindings

## Runtime Architecture

### 1. Legacy inventory reader

Add a focused discovery path that reads file/env server definitions and exposes them
to MCP Hub as inventory rows.

It should not be the executable runtime registry.

### 2. Managed external server registry

Add a managed runtime source that reads:

- managed external server definitions from MCP Hub DB
- encrypted secrets from MCP Hub secret storage

This registry should build the executable external server config objects used by the
runtime.

### 3. Auth hydration adapter

Introduce a small bridge that converts managed server config plus stored secret into
runtime auth material.

For v1:

- websocket/header auth should be supported
- stdio env injection should be supported only for explicitly modeled safe cases
- anything outside the supported managed auth shapes should be rejected as
  unsupported rather than silently falling back to env coupling

### 4. External federation module source split

`ExternalFederationModule` should stop treating file/env config as the only runtime
source.

Instead it should:

- use managed DB-backed servers for executable discovery and tool routing
- use legacy inventory only for MCP Hub UI visibility and import workflows

That is the key change that removes the dual live authority problem.

## Effective External Access Resolution

External access should be computed as the intersection of:

- effective tool/capability policy permitting external usage
- active approval policy
- effective server bindings from profile and assignment
- server managed/executable state
- server enabled state
- usable secret/auth availability

Resolution order:

1. collect profile `grant` bindings
2. apply assignment `grant` bindings
3. apply assignment `disable` bindings
4. filter out non-managed, superseded, disabled, or secret-missing servers

Effective access output per server should include:

- `server_id`
- `server_name`
- `granted_by`
- `disabled_by_assignment`
- `server_source`
- `superseded_by_server_id`
- `secret_available`
- `runtime_executable`
- `blocked_reason`

## API And UI Changes

### MCP Hub external server responses

Expand the external server DTO with:

- `server_source`
- `legacy_source_ref`
- `superseded_by_server_id`
- `binding_count`
- `runtime_executable`

### External Servers UI

The existing `External Servers` tab should become a full management surface:

- managed rows support create, edit, enable/disable, delete, set/rotate/clear secret
- legacy rows are read-only
- legacy rows expose `Import to MCP Hub`
- superseded legacy rows show the linked managed server

### Credential Bindings UI

Add binding controls in:

- permission profile editor
- policy assignment editor

V1 behavior:

- profiles can grant managed servers
- assignments can grant managed servers
- assignments can disable inherited managed servers
- legacy or superseded rows are visible but not selectable

### Effective summaries

Summaries should explain why a visible server is not usable:

- legacy inventory only
- superseded
- disabled by assignment
- external capability not granted
- secret missing
- runtime auth unsupported

## Migration Rules

Import flow:

1. discover legacy inventory from file/env config
2. user chooses `Import to MCP Hub`
3. create managed row with preserved `server_id`
4. normalize managed auth config away from `*_ENV` coupling
5. require user to set or rotate the secret in MCP Hub
6. mark the legacy row as superseded
7. runtime executes only the managed row

Do not automatically copy env secret values.

The import path should be explicit and auditable.

## Testing Strategy

Backend unit tests:

- binding invariants and uniqueness
- cross-scope binding validation
- import normalization and supersede behavior
- effective external-access resolution
- managed auth hydration

Backend integration tests:

- managed server executes
- legacy inventory is visible but non-executable
- imported server with same `server_id` takes precedence
- missing secret or unsupported auth blocks runtime execution

Frontend tests:

- managed vs legacy rendering in the External Servers tab
- import action availability
- binding editors exclude legacy servers
- summaries explain non-usable servers

Migration tests:

- file/env inventory discovery
- import creates managed canonical row
- superseded legacy row no longer drives executable tools

## Main Risks

- leaving file/env runtime execution paths active after adding managed CRUD
- shipping managed secret storage without a working runtime auth bridge
- allowing lower-scope private servers to leak into broader shared bindings
- allowing duplicate or ambiguous binding rows
- preserving imported env-auth config in a way that keeps hidden env coupling alive

## Recommended Scope Boundary

Include in this PR:

- managed-vs-legacy server states
- runtime source-of-truth split
- managed auth hydration for a narrow supported set
- server-level credential bindings
- binding-aware summaries and UI

Do not include in this PR:

- per-secret slot bindings
- automatic env secret import
- arbitrary secret provider plugins
- multi-secret server definitions
- broad external transport redesign
