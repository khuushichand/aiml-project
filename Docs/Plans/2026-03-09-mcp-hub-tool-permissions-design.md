# MCP Hub Tool Permissions Design

Date: 2026-03-09
Status: Approved for planning

## Summary

`MCP Hub` becomes the canonical control plane for tool governance. It owns reusable permission profiles, context assignments, overrides, runtime approval rules, credential bindings, and the effective policy resolver used by MCP tool execution.

`Persona/Agents` UI remains responsible for non-tool configuration. For tool access, it becomes a consumer of MCP Hub state and shows an effective summary plus links back to MCP Hub for editing.

This design avoids coupling the new system to the current ACP-specific policy scaffolding, which is being re-architected elsewhere. ACP integration is treated as a compatibility boundary, not the source of truth.

## Goals

- Make `MCP Hub` the main editor for tool permissions, tool approvals, and tool-related credentials.
- Support reusable named permission profiles.
- Allow `default`, `group`, and `persona` contexts to reference a profile or use manual configuration.
- Allow per-context overrides that may either restrict or broaden access when the editor has authority to grant the broader capability.
- Support runtime approval policies such as `ask every time`, `ask outside profile`, and temporary elevation.
- Keep secret material out of persona records.
- Provide a model that can survive ACP re-architecture without rework.

## Non-Goals

- Moving non-tool persona attributes into MCP Hub.
- Making ACP-specific runtime stores the canonical policy backend.
- Implementing full policy enforcement for every possible tool without first establishing a capability registry and metadata contract.

## Current Constraints

The existing codebase has partial MCP Hub support, but the current model is not enough for the target system:

- `MCP Hub` currently exposes `ACP Profiles`, `Tool Catalogs`, and `External Servers` in the UI.
- MCP Hub storage is currently ACP-profile-shaped and uses ownership scopes of `global`, `org`, `team`, and `user`.
- MCP runtime enforcement currently understands RBAC tool permissions and generic `mcp:*` scopes, but not the full capability model proposed here.
- External server federation still reads YAML or env-backed configuration at startup.
- Persona policy rules already exist and must not remain a peer source of truth for tool policy after this design lands.

## Core Decisions

### 1. MCP Hub is the canonical tool policy domain

All tool-related governance is edited in MCP Hub:

- permission profiles
- assignment of profiles to contexts
- inline overrides
- runtime approval behavior
- external-service credential bindings

Persona and agent UIs keep non-tool settings and consume effective tool policy summaries from MCP Hub.

### 2. Reusable profiles are optional accelerators, not mandatory

Users may:

- assign an existing reusable profile
- create a new custom profile
- configure a target context manually without first creating a reusable profile

This supports both curated presets and direct editing.

### 3. Overrides may broaden access, but only with grant authority

A user editing a persona or group assignment may broaden access beyond inherited policy only if the acting user has authority to grant the broader capability. The UI must reject or disable broadening changes the acting user is not authorized to grant.

### 4. Runtime approval is part of policy, not an afterthought

Static permissions and runtime approvals are part of one system. A policy can allow an action silently, allow it only after confirmation, or allow temporary elevation with explicit scope and expiry.

## Domain Model

### Distinguish ownership from applicability

This is a required correction to avoid overloading the current `owner_scope_type` model.

#### Config owner scope

Defines who owns and can administer a stored object:

- `global`
- `org`
- `team`
- `user`

This is used for visibility, administration, and storage boundaries.

#### Assignment target

Defines where a policy applies at runtime:

- `default`
- `group`
- `persona`

Each assignment target also carries a target identifier when needed:

- `default` has no target id
- `group` uses a group id
- `persona` uses a persona id

These are separate concepts and must be stored separately.

### Proposed objects

#### PermissionProfile

Reusable named tool policy bundle.

Fields:

- `id`
- `name`
- `description`
- `owner_scope_type`
- `owner_scope_id`
- `mode` (`preset` or `custom`)
- `policy_document`
- `is_active`
- timestamps and actor metadata

#### PolicyAssignment

Connects policy to a runtime target.

Fields:

- `id`
- `target_type` (`default`, `group`, `persona`)
- `target_id`
- `owner_scope_type`
- `owner_scope_id`
- `profile_id` nullable
- `inline_policy_document` nullable
- `approval_policy_id` nullable
- `is_active`
- timestamps and actor metadata

Rule:

- a target may use a reusable profile, manual config, or a reusable profile plus overrides

#### PolicyOverride

Delta applied on top of the base assignment.

Fields:

- `id`
- `assignment_id`
- `override_document`
- `broadens_access` boolean
- `grant_authority_snapshot`
- timestamps and actor metadata

#### ApprovalPolicy

Defines runtime approval behavior.

Fields:

- `id`
- `name`
- `mode`
- `rules`
- `owner_scope_type`
- `owner_scope_id`
- timestamps and actor metadata

#### CredentialBinding

Associates profiles or assignments with external service credentials and server definitions without embedding raw secrets into persona config.

Fields:

- `id`
- `binding_target_type`
- `binding_target_id`
- `external_server_id`
- `credential_ref`
- `usage_rules`
- timestamps and actor metadata

#### EffectivePolicy

Computed runtime result returned by the resolver, not necessarily persisted as the source record.

Contents:

- resolved capabilities
- resolved resource constraints
- required approval mode
- credential availability state
- provenance metadata
- deny reasons or missing prerequisites

## Capability Model

Tool permissions must be capability-based rather than only tool-name-based. Tool names remain enforceable units, but they are not expressive enough for the target UX.

### Capability families

- `filesystem.read`
- `filesystem.write`
- `filesystem.delete`
- `process.execute`
- `network.external`
- `credentials.use`
- `mcp.server.connect`
- `tool.invoke`

### Constraint dimensions

- path scope
- tool scope
- module scope
- external service scope
- credential scope

Examples:

- current folder only
- current folder and descendants
- explicit path allowlist
- all tools in a module
- selected individual tools
- approved external services only

### Sensitivity classes

The editor and approval system should understand tool risk classes such as:

- destructive
- external side effects
- secret-bearing
- executes processes
- broad filesystem reach

## Tool Capability Registry

This is a required addition because current MCP runtime checks do not understand the full proposed capability model.

Each tool should have machine-readable metadata or a registry entry describing:

- tool name
- module
- capability families used
- whether it is read-only or mutating
- whether it can affect filesystem, processes, network, or credentials
- risk class
- optional resource-specific constraints

The UI reads this registry to present grouped controls. The runtime resolver uses it to determine whether a requested tool call fits within policy.

Without this registry, the system would only be able to approximate the promised permission model.

## Preset Profiles

Presets should be implemented as normal profiles shipped by the system:

- `No Additional MCP Restrictions`
- `Read Only`
- `Read In Current Folder`
- `RW Current Folder`
- `External Services`

Presets are editable by duplication, not by mutating the built-in definition directly. They act as starting points, not a separate policy mechanism.

## Grant Authority Model

The current coarse MCP Hub mutation gate is not sufficient for safe broadening behavior. Editing and granting must be distinct.

### Needed grant classes

- `grant.tool.invoke`
- `grant.filesystem.read`
- `grant.filesystem.write`
- `grant.filesystem.delete`
- `grant.process.execute`
- `grant.network.external`
- `grant.credentials.use`
- `grant.mcp.server.connect`

These grant permissions define which capabilities a user may add when editing another context's policy.

### Grant evaluation rules

When a proposed change is more permissive than the inherited effective policy:

1. detect the broadened capabilities
2. compare them against the acting user's grant authority
3. allow save only when all broadened capabilities are grantable
4. record in audit history that access was broadened

If the acting user lacks authority, the UI should explain which capability could not be granted.

## Policy Resolution Rules

Resolution order:

1. start with the applicable `default` assignment
2. merge in any applicable `group` assignment
3. merge in the `persona` assignment if present
4. apply explicit overrides
5. apply approval policy rules
6. apply hard upper bounds from platform authorization

### Merge semantics

These rules must be explicit in implementation:

- capability grants are additive unless explicitly denied
- explicit denies take precedence over inherited allows
- tighter resource constraints win when two grants overlap
- broader overrides are allowed only with grant authority
- approval policies can require confirmation even for otherwise allowed actions

### Hard upper bounds

The resolved MCP Hub policy is not the only gate. The runtime must still honor:

- AuthNZ identity and session validity
- RBAC permissions
- API key scope ceilings
- missing credential material
- unavailable external service definitions

This is why the system must distinguish `configured policy` from `effective policy`.

## Runtime Approval Model

Approval policy is attached to assignments or profiles and evaluated at tool-call time.

### Supported modes

- `allow_silently`
- `ask_every_time`
- `ask_outside_profile`
- `ask_on_sensitive_actions`
- `temporary_elevation_allowed`

### Approval request contents

Every approval request should include:

- acting user
- persona id if any
- group id if any
- conversation or session id if applicable
- tool name
- summarized arguments
- trigger reason
- requested elevation scope
- available duration options

### Approval token scope

To avoid accidental over-broad approvals, approval decisions should be keyed by:

- user
- target context
- conversation or session id when relevant
- tool or tool risk class
- resource scope if applicable
- approval reason

### Expiry

Temporary elevation must always include TTL. Examples:

- once
- until end of current conversation
- until end of current session
- fixed expiration timestamp

## MCP Hub UI Structure

The UI should be reorganized around governance tasks rather than current backend categories.

### Top-level tabs

- `Profiles`
- `Assignments`
- `Approvals`
- `Credentials`
- `Catalog`

### Profiles

Create and edit reusable profiles.

Modes:

- simple editor for common controls
- advanced editor for capability and constraint detail

### Assignments

Attach policy to:

- `default`
- `group`
- `persona`

Each assignment may:

- reference a reusable profile
- use inline manual configuration
- add overrides

This view should also display an effective policy preview.

### Approvals

Configure runtime approval modes and approval rules.

### Credentials

Manage external server definitions, secret presence, bindings, rotation state, and which policies may use each credential class.

### Catalog

Show tool and module catalog enriched with policy metadata from the capability registry.

## Effective Policy Explainability

The effective-policy view must show provenance, not only the final result.

For each major capability or denial, the UI should show:

- granted by
- denied by
- overridden by
- approval required because
- missing prerequisite because

This is necessary to make inherited policy debuggable.

## External Servers And Credential Source Of Truth

This area needs an explicit migration rule because current federation still reads file or env-backed configuration.

### Recommended precedence

Phase 1:

- support both DB-backed MCP Hub state and file-backed external config
- DB-backed state is authoritative for UI-managed servers
- file-backed state remains readable for migration and compatibility

Phase 2:

- runtime federation reads merged registry through a single abstraction, not directly from YAML
- MCP Hub-managed definitions override file definitions when ids collide

Phase 3:

- deprecate direct file-backed configuration for interactive management

Secrets should continue to be stored through secure server-side secret storage and referenced indirectly. Persona records should never hold raw secrets.

## Persona Policy Compatibility

Existing persona policy rules must not remain a second peer authority for tool governance.

Recommended transition:

- MCP Hub becomes canonical for tool policy
- persona policy rule endpoints remain for compatibility only
- tool-related persona rules become derived or adapter-backed views
- persona UI shows effective MCP Hub policy summary rather than owning separate tool policy logic

This preserves backward compatibility while removing split-brain governance.

## Persistence

Add MCP Hub-owned durable tables for:

- permission profiles
- profile preset metadata
- policy assignments
- policy overrides
- approval policies
- approval decisions and temporary elevations
- credential bindings
- policy audit history
- optional capability registry metadata if not generated elsewhere

Do not rely on the current in-memory ACP admin session service for durable permission configuration.

## Audit Requirements

Every mutation should log:

- actor
- target context
- previous state
- new state
- whether the change broadened access
- which grant authority justified the broadened access

Every runtime approval should log:

- requester
- context
- tool
- summarized args or arg hash
- approval reason
- approval scope
- expiry
- decision

## Rollout Plan

### Phase 1: Storage and read path

- add new MCP Hub domain objects
- add read APIs
- expose capability registry metadata

### Phase 2: UI foundation

- replace current ACP-tab framing with governance tabs
- build profile editor and assignments UI
- add effective-policy preview and provenance

### Phase 3: Resolver integration

- add policy resolver service
- make MCP protocol ask the resolver before execution
- keep behind a feature flag until validated

### Phase 4: Approval flow

- add runtime approval service
- add temporary elevation handling
- add audit integration

### Phase 5: Compatibility cleanup

- adapt persona policy endpoints to MCP Hub-backed views
- reduce reliance on ACP-specific tool policy mechanisms
- deprecate file-first external server management

## Testing Strategy

### Backend unit tests

- profile resolution
- assignment precedence
- override broadening detection
- grant authority checks
- approval trigger logic
- credential availability effects

### Backend integration tests

- MCP execution allowed or denied based on resolved policy
- approval flow lifecycle
- temporary elevation expiry
- external server precedence behavior
- persona summary consuming MCP Hub state

### Frontend tests

- profile editor simple and advanced modes
- assignment flows
- effective-policy explainability
- approval policy configuration
- credential binding flows

### Migration tests

- old MCP Hub data remains readable
- compatibility adapters behave predictably
- file-backed external config and DB-backed config coexist during migration

## Open Implementation Questions

- Whether group assignment should initially map to existing team or org structures, or support a separate MCP-specific group concept later.
- Whether capability registry data should be stored centrally or derived from tool definitions at startup.
- Whether approval dialogs should support user-defined reason templates or only system-generated explanations in the first version.

## Recommended First Implementation Slice

The first implementation should not attempt the whole system at once.

Recommended slice:

1. introduce new MCP Hub domain model and read APIs
2. build `Profiles` and `Assignments`
3. expose effective-policy preview
4. add resolver and feature-flagged enforcement
5. add `Approvals`
6. expand `Credentials`

This yields visible product value early while keeping runtime migration risk contained.
