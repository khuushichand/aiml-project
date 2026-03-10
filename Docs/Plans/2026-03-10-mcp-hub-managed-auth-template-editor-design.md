# MCP Hub Managed Auth Template Editor Design

Date: 2026-03-10
Status: Approved for planning

## Summary

The next MCP Hub PR should add a first-class managed auth template editor for
external servers.

This phase is intentionally narrow:

- one auth template per managed external server
- template mappings reference credential slots only
- supported runtime targets are `header` and `env`
- simple fixed `prefix` and `suffix` formatting is allowed
- runtime receives compiled parser-compatible transport config, not a second
  parallel auth channel
- legacy alias-based secret fallback remains transitional only

The goal is to make slot-based credential governance actually executable and
auditable for both websocket and stdio transports.

## Why This Is The Next PR

The MCP Hub avenue now has:

- policy storage, profiles, assignments, overrides, and runtime approvals
- registry-backed tool editing and path-scoped enforcement
- managed-versus-legacy external-server precedence
- server-level and slot-level credential bindings
- explicit named credential slots on managed servers

The next remaining gap is auth template authoring.

Right now:

- managed runtime hydration already reads a template-like shape from
  `config.auth`
- websocket header injection works
- stdio env injection does not yet exist
- MCP Hub UI can manage slots and slot secrets, but not how they become runtime
  auth
- server status still mostly reflects `secret_configured` and `runtime_executable`,
  which is no longer enough once slots and bindings exist

Without an explicit template editor, slot-based governance remains incomplete.

## Goals

- Add one explicit managed auth template per managed external server.
- Support both websocket/header and stdio/env auth injection.
- Keep auth-template references limited to credential slots only.
- Allow simple prefix/suffix formatting for common patterns like
  `Authorization: Bearer <token>`.
- Compile MCP Hub-managed auth templates into parser-compatible transport config
  before runtime adapters are constructed.
- Surface auth-template validity and blocked reasons in MCP Hub API and UI.

## Non-Goals

- Multiple alternative auth strategies per server.
- Query-string, body-field, or scriptable auth injection.
- Non-secret config interpolation in templates.
- Arbitrary raw JSON editing as the primary authoring path.
- Keeping legacy alias-based auth as a peer long-term runtime source.

## Current Constraints

- The current auth bridge already reads `config.auth.mode`,
  `config.auth.required_slots`, and `config.auth.slot_bindings`.
- The runtime registry service already compiles managed server rows into
  `ExternalMCPServerConfig` payloads before parsing.
- Websocket adapters consume headers from parsed config.
- Stdio adapters consume env from parsed config.
- The current UI and API do not expose auth-template presence, validity, or
  blocked reasons.

These constraints mean the next design should extend the existing managed config
overlay, not invent a second persisted runtime auth model.

## Core Decisions

### 1. The auth template is persisted as managed MCP Hub overlay config

MCP Hub should continue to own managed external server config. The auth template
should be stored as a structured managed config section that compiles into the
existing parser/runtime flow.

Recommended persisted shape inside managed server config:

- `auth.mode`
- `auth.mappings`

Where each mapping contains:

- `slot_name`
- `target_type`: `header | env`
- `target_name`
- `prefix`
- `suffix`
- `required`

This avoids a second source of truth while still giving the UI a clean authored
object to manage.

### 2. One auth template per managed server

Each managed server gets exactly one template/mode in v1.

This keeps:

- validation simple
- runtime precedence unambiguous
- UI authoring narrow and understandable

Future auth-strategy alternatives can be added later if needed, but not in this
phase.

### 3. Required slots are derived from mappings

Do not store separately editable `required_slots` and `mappings`.

Instead:

- each mapping may be marked `required`
- the effective required-slot set is derived from mappings

This removes drift between two editable lists and keeps the model boring.

### 4. Transport targets are compiled into normal parsed config

The runtime bridge must compile auth-template mappings into the transport config
that adapters already understand.

Compilation rules:

- `header` mappings compile into `websocket.headers`
- `env` mappings compile into `stdio.env`

This means:

- websocket/header auth stays in the existing parsed config path
- stdio/env auth uses the existing `stdio.env` path consumed by the stdio adapter

There should be no side-channel auth injection mechanism parallel to parsed
transport config.

### 5. Template precedence is strict once a template exists

If a managed server has an auth template:

- template-driven auth hydration is authoritative
- old server-level secret alias fallback is ignored

The old server-level secret path remains transitional only for managed servers
that do not yet have a template and still rely on migrated default-slot
compatibility.

### 6. Template mappings must be unique per runtime target

Per managed server template, require uniqueness on:

- `(target_type, target_name)`

This prevents ambiguous collisions like:

- two slots both targeting `Authorization`
- two slots both targeting the same env var

Fail closed on duplicate targets.

### 7. Slot deletion invalidates any referencing template

If a slot referenced by a template is deleted:

- the template becomes invalid
- runtime execution must fail closed
- MCP Hub should surface this clearly in server status

The UI should warn before deleting a referenced slot, but template invalidation
must still be enforced server-side.

## Data Model

## Managed Server Config Additions

Persist the template inside managed external server config:

```json
{
  "auth": {
    "mode": "template",
    "mappings": [
      {
        "slot_name": "token_readonly",
        "target_type": "header",
        "target_name": "Authorization",
        "prefix": "Bearer ",
        "suffix": "",
        "required": true
      }
    ]
  }
}
```

Rules:

- `slot_name` must reference an existing server slot
- `target_type` must be `header` or `env`
- `target_name` must be non-empty
- duplicate `(target_type, target_name)` is invalid
- templates may contain both `header` and `env` mappings, but runtime only
  materializes mappings valid for the current transport

## API Response Additions

External server responses should add:

- `auth_template_present`
- `auth_template_valid`
- `auth_template_blocked_reason`

Allowed blocked reasons:

- `no_auth_template`
- `auth_template_invalid`
- `required_slot_not_granted`
- `required_slot_secret_missing`
- `unsupported_template_transport_target`

These fields are needed for the MCP Hub UI to show actual readiness state rather
than just generic secret presence.

## Runtime Semantics

Execution model:

1. Load managed external server row.
2. Read slot definitions and slot secrets.
3. Read managed auth template from server config.
4. Resolve effective granted slot set from profile plus assignment bindings.
5. Validate template mappings against defined slots.
6. For each required mapping:
   - ensure slot is granted
   - ensure slot secret exists
7. Compile runtime auth:
   - websocket: merge mapped headers into `websocket.headers`
   - stdio: merge mapped env vars into `stdio.env`
8. Force parsed `auth.mode` to `none` after compilation so external runtime does
   not also try env-based auth indirection.

Blocked reasons:

- `no_auth_template`
- `auth_template_invalid`
- `required_slot_not_granted`
- `required_slot_secret_missing`
- `unsupported_template_transport_target`

## MCP Hub UI

The auth-template editor lives inside the managed server editor, alongside:

- `Server config`
- `Credential slots`
- `Auth template`

Recommended UI flow:

1. User chooses a managed server.
2. User defines slots first.
3. User opens `Auth template`.
4. User adds mappings with:
   - slot
   - target type
   - target name
   - prefix
   - suffix
   - required

Guardrails:

- disable template editor when no slots exist
- highlight transport-specific targets first:
  - websocket -> headers
  - stdio -> env vars
- warn when deleting a slot referenced by the template
- show template readiness state in both the editor and server list

Do not make raw JSON the primary authoring path in v1.

## Migration

For existing managed servers:

- if no auth template exists, keep them visible and editable
- migrated default-slot compatibility may continue temporarily
- once a template is added, runtime must prefer template compilation
  unconditionally

This allows incremental adoption without keeping ambiguous long-term fallback
behavior.

## Testing

### Backend Unit Tests

- template validation against defined slot set
- uniqueness of `(target_type, target_name)`
- prefix/suffix formatting
- transport-target validation
- slot deletion causing invalid template status

### Backend Integration Tests

- websocket/header compilation from slot grants
- stdio/env compilation from slot grants
- missing required slot blocks runtime
- invalid template blocks runtime
- template precedence over old alias-based fallback

### Frontend Tests

- auth-template editor renders available slots
- adding/removing mappings updates readiness state
- invalid template state appears in server UI
- server list shows template presence/validity

## Risks

- creating two sources of truth between config JSON and MCP Hub state
- ambiguous fallback behavior if template precedence is not strict
- transport-target mismatches silently passing through
- duplicate mapping targets causing last-write-wins behavior

## Recommendation

Implement the next PR as a focused managed auth-template slice:

- extend the existing managed config overlay
- compile template mappings into parser-compatible transport config
- add transport-aware validation and status fields
- build a guided auth-template editor in MCP Hub

That closes the biggest remaining external-auth usability gap without widening
scope into multi-strategy auth or arbitrary template logic.
