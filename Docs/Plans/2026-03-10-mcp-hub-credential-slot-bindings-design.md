# MCP Hub Credential Slot Bindings Design

Date: 2026-03-10
Status: Approved for planning

## Summary

The next MCP Hub PR should refine external-service governance from server-level
credential access to explicit named credential slots on managed external servers.

This phase is intentionally narrow:

- slots exist only on managed MCP Hub external servers
- slots cover secret-bearing values only
- each managed server exposes one explicit managed auth template
- profiles grant selected slots
- assignments can add or disable individual slots
- runtime hydrates only the granted slot set
- legacy inventory remains read-only and unslotted

The goal is to let MCP Hub express controlled access such as "GitHub readonly token"
versus "GitHub write token" instead of treating a whole external server as one
undifferentiated secret bucket.

## Why This Is The Next PR

The MCP Hub avenue now has:

- durable policy storage
- profiles, assignments, approvals, overrides, and provenance
- registry-backed tool editing
- path-scoped local enforcement
- managed-versus-legacy external-server precedence
- server-level external bindings for profiles and assignments

The biggest remaining governance gap is credential granularity inside managed
external servers.

Right now:

- managed runtime hydration understands one secret-bearing value per server
- effective external access is resolved only at the server level
- bindings are unique per target plus server, not per target plus server plus secret
- the UI can grant or disable only whole servers

That is enough for "can use server X", but not for "can use readonly token on server X
but not write/admin token on server X."

## Goals

- Add explicit named credential slots to managed external servers.
- Keep non-secret companion values on the managed server definition itself.
- Let permission profiles grant selected slots per server.
- Let policy assignments add or disable individual slots.
- Make runtime auth hydration slot-aware and fail closed when required slots are
  missing or not granted.
- Keep migration safe for existing one-secret managed servers.

## Non-Goals

- Secret slots on legacy inventory records.
- Per-header, per-body-field, or arbitrary inferred slot extraction from config.
- Multiple alternative auth strategies per server in the same phase.
- Automatic multi-slot inference from ambiguous legacy or managed configs.
- Exposing raw secret values anywhere in MCP Hub UI.

## Current Constraints

- Managed auth hydration currently resolves one secret-bearing value and supports
  only simple managed auth modes.
- The managed runtime loader builds one runtime payload per server and does not yet
  understand partial slot access.
- Effective external access summaries are server-level only.
- The current binding table is unique on `(target_type, target_id, external_server_id)`.
- The current server-level `/external-servers/{id}/secret` API and UI still exist.

These constraints mean the next design must explicitly reshape runtime, storage,
and summaries around `server + slot set`, not just add more rows in the database.

## Core Decisions

### 1. Slots are explicit first-class objects on managed servers

Each managed external server may define zero or more explicit credential slots.

Examples:

- `api_key`
- `bearer_token`
- `client_secret`
- `token_readonly`
- `token_write`

Slots are not inferred from arbitrary config keys at runtime. They are explicit MCP
Hub metadata attached to the managed server definition.

### 2. Slots cover secret-bearing values only

V1 slots are for secret-bearing values only.

Non-secret companions remain in server config, for example:

- `tenant_id`
- `account_id`
- `region`
- `api_key_header`

This keeps slot semantics clean and avoids treating plain configuration as if it were
secret governance.

### 3. Each managed server has one explicit managed auth template

The current runtime cannot safely support multiple alternative auth strategies per
server in this phase, so each managed server gets one managed auth template.

That template must declare:

- `auth_mode`
- required slot names
- how each slot is injected into runtime auth material

V1 should support only narrow managed auth templates such as:

- bearer token header
- API key header
- client id plus client secret header/body shape only if the mapping is explicit

If the template cannot be expressed safely, the server remains non-executable until
it is normalized.

### 4. `slot_name` is the stable binding key

Each slot has:

- `slot_name`
- `display_name`
- `secret_kind`
- `is_required`
- `privilege_class`

`slot_name` is immutable after creation and is the stable key used in bindings and
runtime hydration.

`display_name` is editable and user-facing.

### 5. Effective external access becomes slot-aware

The current server-level effective-access shape is not sufficient once assignments can
disable only some slots.

The next response model should be:

- one server record containing `slots[]`, or
- a flattened `server + slot` list

The recommended shape is:

- `server_id`
- `server_name`
- `server_state`
- `slots[]`

Where each slot entry exposes:

- `slot_name`
- `display_name`
- `granted_by`
- `disabled_by_assignment`
- `secret_available`
- `runtime_usable`
- `blocked_reason`
- `privilege_class`

### 6. Assignment bindings operate at the slot level

Profiles grant selected slots for a server.

Assignments may:

- add slot grants
- disable inherited slot grants

Assignments must not replace the entire slot set wholesale. Resolution is additive
then subtractive:

1. profile slot grants
2. assignment slot grants
3. assignment slot disables

### 7. Existing server-level secret APIs become a transitional alias only

The current `/external-servers/{id}/secret` API should not remain the long-term model,
but removing it immediately would create unnecessary churn.

For this phase:

- keep the server-level secret API as a temporary alias only for migrated default-slot
  servers
- introduce slot-secret APIs as the canonical interface
- mark the server-level secret path as deprecated in docs and UI copy

If a managed server has multiple slots, the server-level secret API should reject the
write rather than guess which slot it meant.

## Data Model

### `mcp_external_server_credential_slots`

Add a new table for slot metadata:

- `id`
- `server_id`
- `slot_name`
- `display_name`
- `secret_kind`
- `is_required`
- `privilege_class`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`

Required invariant:

- unique `(server_id, slot_name)`

### `mcp_external_server_slot_secrets`

Add a new table for encrypted slot secret values:

- `slot_id`
- encrypted payload
- `key_hint`
- `updated_by`
- `updated_at`

Required invariant:

- one live secret row per slot

### `mcp_credential_bindings`

Evolve bindings from server-level to slot-level:

- keep `binding_target_type`
- keep `binding_target_id`
- keep `external_server_id`
- add `slot_name`
- keep `binding_mode`
- keep `usage_rules_json` reserved

New uniqueness:

- `(binding_target_type, binding_target_id, external_server_id, slot_name)`

Rules:

- `disable` remains valid only for assignment targets
- bindings may reference managed servers only
- bindings may reference defined slots only

### Transitional compatibility

Keep `mcp_external_server_secrets` temporarily as a migration input and alias path for
default-slot servers.

Runtime and new APIs should prefer slot-secret storage once slots exist.

## Managed Auth Template Contract

Each managed server definition should expose one explicit auth template in config.

Recommended contract:

- `auth.mode`
- `auth.required_slots`
- `auth.slot_bindings`

Example:

```json
{
  "auth": {
    "mode": "bearer_token",
    "required_slots": ["token_readonly"],
    "slot_bindings": {
      "token_readonly": {
        "inject": "header",
        "header_name": "Authorization",
        "prefix": "Bearer "
      }
    }
  }
}
```

Or:

```json
{
  "auth": {
    "mode": "api_key_header",
    "required_slots": ["api_key"],
    "slot_bindings": {
      "api_key": {
        "inject": "header",
        "header_name": "X-API-KEY"
      }
    }
  }
}
```

This is intentionally explicit. The runtime should not infer header names, prefixes,
or field placement from slot names alone.

## Runtime Architecture

### 1. Slot-aware managed auth hydration

The managed auth bridge should hydrate runtime auth only from:

- managed server auth template
- granted slot metadata
- encrypted slot secrets

It should fail closed when:

- a required slot is not granted
- a required slot secret is missing
- the auth template references an unknown slot
- the template shape is unsupported

### 2. Slot-aware managed runtime registry

The managed registry should continue to produce executable runtime server configs,
but now only if the auth template can be satisfied by the final granted slot set.

The runtime still produces one executable server entry per server, not one per slot,
but auth hydration for that server depends on the slot set granted to the current
context.

### 3. Slot-aware effective external access

The external-access resolver should return per-slot status and then derive a server
aggregate from that slot set.

A server may be:

- partially usable
- fully blocked
- fully usable

The UI should not collapse that distinction back into one boolean.

## Binding Semantics

### Profile bindings

Profiles grant selected slots per server.

Example:

- `github` -> `token_readonly`
- `stripe` -> `publishable_key`

### Assignment bindings

Assignments may:

- grant additional slots
- disable inherited slots

Example:

- profile grants `github: token_readonly`
- assignment grants `github: token_write`
- assignment disables `github: token_readonly`
- effective result is `github: token_write`

### Grant-authority implications

Slot grants can materially broaden external access, especially once slots encode
different privilege levels.

The design should therefore require broadened-access checks against `privilege_class`
or equivalent slot metadata, not just server identity.

## Migration Strategy

The migration order matters.

### Step 1: Add slot tables and slot-aware binding columns

Do not drop current server-level secret storage first.

### Step 2: Backfill default slots for obvious single-secret managed servers

For managed servers whose auth template clearly maps to one secret slot:

- create one default slot such as `bearer_token` or `api_key`
- copy the existing encrypted server secret into the new slot secret row
- backfill existing server-level bindings to that slot

### Step 3: Replace binding uniqueness

Only after slot identity exists should the unique index move from:

- `target + server`

to:

- `target + server + slot`

### Step 4: Prefer slot-secret runtime hydration

Once slots exist for a server, runtime should prefer slot-secret storage.

### Step 5: Keep alias compatibility temporarily

For migrated single-slot servers only, the old server-level secret API can delegate
to the default slot.

Ambiguous multi-slot servers must not use the old path.

## UI Changes

### External Servers

Managed server editor gains a `Credential Slots` section with:

- add slot
- edit slot metadata
- set/rotate slot secret
- remove slot

Each slot shows:

- display name
- stable slot name
- secret kind
- required/optional
- privilege class
- secret configured state

### Permission Profiles

Profile bindings become grouped slot selection per server.

Only managed servers with defined slots are selectable.

Servers with no slots should be shown as incomplete, not selectable.

### Policy Assignments

Assignment bindings become per-slot controls:

- inherit
- grant
- disable

Effective summary must show slot-specific blocked reasons.

### Persona Summary

Stay compact:

- `GitHub: token_readonly granted`
- `GitHub: token_write disabled`
- `Stripe: client_secret missing`

No secret values are ever exposed.

## Testing

### Backend

- slot table migration coverage
- default-slot backfill coverage
- slot-secret CRUD coverage
- slot-level binding uniqueness and validation
- slot-level effective external access resolution
- auth hydration from explicit slot bindings
- missing required slot failures

### Frontend

- slot CRUD in managed server editor
- slot-secret configured indicators
- profile slot binding selection
- assignment slot inherit/grant/disable controls
- slot-aware persona and assignment summaries

### Runtime

- managed registry builds runtime payloads from slot-based auth templates
- ambiguous or unsupported templates fail closed
- deprecated server-level secret alias works only for single-slot migrated servers

## Main Risks

- ambiguous migration from server-level secret blobs to slots
- auth template drift between UI and runtime
- assignment slot grants broadening access without privilege metadata
- UI complexity if too many slot types appear at once

## Recommendation

Proceed with a slot-based design, but keep the first version constrained:

- one auth template per server
- secret-bearing slots only
- explicit slot metadata only
- default-slot migration only for obvious single-secret managed servers
- slot-aware runtime and summaries from day one

That is the smallest version that actually delivers meaningful per-secret governance
without creating another temporary half-model.
