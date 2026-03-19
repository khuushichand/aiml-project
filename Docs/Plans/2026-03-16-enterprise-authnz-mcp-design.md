# Enterprise AuthNZ and MCP Integration Design

## Goal

Add an enterprise-grade identity and credential layer to the existing `AuthNZ -> MCP Hub -> MCP Unified` architecture without introducing a separate control plane service.

The primary product outcome is:

- OIDC-based enterprise login and JIT provisioning into the existing local user/org/team model
- Generic MCP credential-slot authorization and brokered runtime credential use
- A pluggable secret-backend interface, starting with the existing local encrypted storage model

## Why This Shape

The current codebase already assumes:

- a local `AuthPrincipal` is resolved in-process
- local org/team membership drives authorization and visibility
- MCP policy and approval decisions are stored locally and resolved during request handling

This makes an `AuthNZ-first` enterprise layer the lowest-risk extension. It keeps:

- identity, provisioning, key ownership, and secret resolution in `AuthNZ`
- execution policy, approval profiles, path/workspace scope, and slot bindings in `MCP Hub`
- transport/runtime execution in `MCP Unified`

## Non-Goals

For v1, this design does not attempt to deliver:

- a new standalone enterprise control plane service
- SAML in phase 1
- SCIM in phase 1
- team-scoped or user-scoped identity providers
- remote secret backends in phase 1
- external-only principals that bypass local `users` rows

## Core Invariants

1. Every authenticated human user must map to a local `users` row.
2. Every federated login must end in the existing `AuthPrincipal` model.
3. `MCP Hub` remains the source of truth for execution policy, approvals, and slot-binding rules.
4. `AuthNZ` remains the source of truth for identity, provisioning, secret references, and runtime credential resolution.
5. `MCP Unified` must not become a durable owner of secret material.
6. Runtime adapters may receive ephemeral execution material, never durable stored secrets.

## Scope and Support Matrix

### Phase 1 support

- `AUTH_MODE=multi_user` only
- PostgreSQL-backed deployments only, or PostgreSQL strongly preferred and treated as required for enterprise mode
- OIDC only
- browser-based login flows only
- global-scoped and org-scoped identity providers only
- local encrypted secret backend only

### Explicitly deferred

- SAML
- SCIM-style provisioning and sync
- remote secret backends
- federation support for single-user mode
- SQLite enterprise mode

## Recommended Architecture

### AuthNZ responsibilities

- OIDC provider configuration
- issuer trust and callback verification
- claim mapping preview and activation
- local-account linking and JIT provisioning
- secret backend registry and runtime secret resolution
- short-lived brokered execution credentials
- audit records for federation and credential-use control paths

### MCP Hub responsibilities

- external server metadata
- credential slot definitions and eligibility rules
- profile/assignment binding to logical secret references
- path/workspace scope evaluation
- approval-policy enforcement and approval-decision persistence

### MCP Unified responsibilities

- accept request context and resolved principal
- ask upstream layers whether a slot may be used
- execute calls with short-lived injected credentials only
- avoid storing durable secret material in adapter config or runtime state

## Revised Phases

### Phase 1: OIDC Foundation

Deliver:

- OIDC provider config
- issuer trust validation
- claim-mapping preview
- JIT provisioning controls
- local-account linking policy
- feature flags for enterprise federation

Do not deliver:

- SAML
- SCIM
- remote secret backends

### Phase 2: Generic MCP Credential Brokering

Deliver:

- generic credential-slot state model
- logical secret references bound to MCP slots
- brokered runtime credential resolution
- UI/API remediation states such as `missing`, `expired`, `reauth_required`, `approval_required`

### Phase 3: Secret Backend Plugins

Deliver:

- backend abstraction with local encrypted backend as the first implementation
- optional remote backends later behind the same capability-oriented interface

### Phase 4: SAML

Deliver SAML only after OIDC, claim mapping, linking, and provisioning behavior are stable.

### Phase 5: SCIM-style Sync

Deliver lifecycle sync only after federation and secret brokering are stable.

SCIM is operationally later, not logically dependent on SAML.

## Data Model

### New tables for phase 1

#### `identity_providers`

Stores trusted OIDC provider configuration.

Recommended fields:

- `id`
- `slug`
- `provider_type` (`oidc`)
- `owner_scope_type` (`global` or `org`)
- `owner_scope_id`
- `enabled`
- `display_name`
- `issuer`
- `discovery_url`
- `authorization_url`
- `token_url`
- `jwks_url`
- `client_id`
- encrypted client secret reference if needed
- `claim_mapping_json`
- `provisioning_policy_json`
- timestamps

#### `federated_identities`

Links a trusted external identity to a local user.

Recommended fields:

- `id`
- `identity_provider_id`
- `external_subject`
- `user_id`
- `external_username`
- `external_email`
- `last_claims_hash`
- `last_seen_at`
- `status`
- timestamps

### Optional later table

#### `identity_provisioning_events`

Useful for high-volume operational analysis, but not required in phase 1 if the existing audit system is sufficient.

Use the audit pipeline first unless product or support needs prove otherwise.

### Secret and credential storage model

#### `secret_backends`

Stores configured secret backend definitions.

For v1, only one backend type is required:

- `local_encrypted_v1`

Later backend types may include:

- `hashicorp_vault`
- `aws_secrets_manager`
- `gcp_secret_manager`
- `azure_key_vault`

#### `managed_secret_refs`

Stores logical references to secret material plus status metadata.

Recommended fields:

- `id`
- `owner_scope_type`
- `owner_scope_id`
- `provider_key`
- `backend_id`
- `secret_locator`
- `status`
- `expires_at`
- `refresh_metadata_json`
- `metadata_json`
- timestamps

### Deliberate omission

Do not add a generic `managed_credentials` table in phase 1.

Reason:

- it overlaps with existing BYOK storage
- it overlaps with MCP Hub binding metadata
- it creates a third source of truth for credential ownership and use

Instead:

- `AuthNZ` stores secret references and backend status
- `MCP Hub` stores which assignments/profiles/slots may use them

## API Surfaces

### Auth federation admin

Add routes under `/api/v1/admin/identity`.

Suggested endpoints:

- `POST /providers`
- `GET /providers`
- `GET /providers/{id}`
- `PUT /providers/{id}`
- `POST /providers/{id}/test`
- `POST /providers/{id}/mappings/preview`
- `POST /providers/{id}/enable`
- `POST /providers/{id}/disable`

### Auth federation runtime

Add routes under `/api/v1/auth/federation`.

Suggested endpoints:

- `GET /login/{provider_slug}`
- `GET /callback/{provider_slug}`
- `POST /link/{provider_slug}`
- `POST /unlink/{provider_slug}`

### Secret backend admin

Add routes under `/api/v1/admin/secrets`.

Suggested endpoints:

- `POST /backends`
- `GET /backends`
- `GET /backends/{id}`
- `POST /secret-refs`
- `GET /secret-refs/{id}`
- `POST /secret-refs/{id}/rotate`
- `POST /secret-refs/{id}/refresh`
- `GET /secret-refs/{id}/status`

### MCP credential orchestration

Extend `/api/v1/mcp/hub`.

Suggested endpoints:

- `POST /external-servers/{server_id}/credential-slots/{slot_name}/authorize`
- `GET /external-servers/{server_id}/credential-slots/{slot_name}/status`
- `POST /external-servers/{server_id}/credential-slots/{slot_name}/bind`
- `POST /policy-assignments/{id}/credential-bindings`
- `DELETE /policy-assignments/{id}/credential-bindings/{binding_id}`

## Federation Rules

### Local account requirement

Federated identities must always resolve to local users.

This keeps the rest of the stack compatible with:

- local numeric user ids
- local org/team membership
- existing `AuthPrincipal`
- existing audit and session assumptions

### Linking rules

- external subject is authoritative
- email is advisory only
- automatic linking to an existing local account is disabled by default
- linking an external identity to an existing account requires explicit authenticated confirmation
- one provider subject may map to one local user

### Provisioning modes

Support explicit policy modes:

- `jit_grant_only`
- `jit_grant_and_revoke`
- `sync_managed_only`

Default recommendation:

- start with `jit_grant_only`

### Revocation and deprovisioning

The design must support claim removal, not only claim addition.

Without that, local memberships drift from IdP truth and MCP visibility remains over-permissive.

## Secret Backend Interface

Use a capability-oriented interface rather than generic CRUD.

Required methods:

- `store_ref`
- `resolve_for_use`
- `rotate_if_supported`
- `describe_status`
- `delete_ref`

Important constraint:

- backend bootstrap credentials must come from deployment-level config or environment variables, not tenant-managed database rows

## Brokered Runtime Credential Model

### Required runtime rule

`MCP Unified` and its adapters may receive only ephemeral execution material.

They may not:

- persist durable secret values into adapter config
- write them into telemetry
- surface them in approval payloads
- store them in long-lived connection state unless explicitly short-lived and scoped

### Preferred model

- `AuthNZ` resolves a short-lived credential or broker handle
- `MCP Hub` confirms policy eligibility and approval status
- adapter injects execution material for one call or a tightly bounded short session

## Reauthentication

The current admin reauth flow is local-password-based.

That is insufficient for federated-only administrators.

The enterprise design must support two reauth strategies:

- local-password reauth for local-password accounts
- federated reauth or signed step-up token flow for IdP-backed accounts

This is required before enterprise federation is considered complete.

## End-to-End Flows

### OIDC login

1. User starts login at `/api/v1/auth/federation/login/{provider}`.
2. `AuthNZ` validates provider enablement and issuer trust configuration.
3. User authenticates with the IdP.
4. Callback validates nonce, issuer, audience, and signature.
5. `AuthNZ` resolves or creates a local user, applies provisioning policy, updates memberships, and emits a standard local session and `AuthPrincipal`.

### MCP slot authorization

1. Admin or user binds a logical secret reference to an MCP server slot.
2. `MCP Hub` stores the authorization relationship.
3. `AuthNZ` stores and validates the secret reference and backend state.
4. Slot status is exposed to the UI without exposing secret material.

### MCP execution

1. `MCP Unified` receives a tool call.
2. `MCP Hub` resolves effective policy, path scope, workspace scope, and slot eligibility.
3. Approval logic runs if required.
4. `AuthNZ` resolves short-lived execution material.
5. Adapter executes the outbound request using ephemeral credentials only.

## Failure Modes

Fail closed by default for:

- invalid issuer trust
- invalid claim mapping
- ambiguous account linking
- backend-unavailable secret resolution
- expired or revoked credentials
- approval-required actions without approval

Operational statuses should distinguish:

- `missing`
- `expired`
- `reauth_required`
- `approval_required`
- `backend_unavailable`

## Security Requirements

- dry-run and preview before provider activation
- explicit issuer allowlist
- explicit activation and privileged admin confirmation
- no implicit email-based linking
- secret redaction in logs, approval prompts, and telemetry
- strict TTL and scope for brokered execution credentials

## Testing Strategy

### Unit

- claim mapping evaluator
- linking policy
- provisioning policy modes
- secret backend interface behavior
- slot status transitions
- brokered credential resolution

### Integration

- OIDC callback success and failure
- JIT provisioning into local org/team membership
- MCP binding plus approval plus execution resolution
- backend unavailable and refresh failure paths

### Security

- issuer mismatch
- audience mismatch
- replayed state/nonce
- email collision takeover prevention
- redaction checks
- fail-closed behavior

### End-to-end

- federated login to MCP tool execution
- missing credential to authorize to retry flow
- approval-required tool call with scoped approval reuse
- backend outage and remediation UX

## Rollout and Feature Flags

Recommended flags:

- `AUTH_FEDERATION_ENABLED`
- `MCP_CREDENTIAL_BROKER_ENABLED`
- `SECRET_BACKENDS_ENABLED`

Recommended rollout order:

1. OIDC provider config and preview
2. JIT provisioning in dry-run and limited enablement
3. generic MCP slot-status model
4. brokered runtime credential flow
5. remote backends later

## Summary

The revised design intentionally narrows the enterprise scope to:

- OIDC federation
- safe local-user provisioning
- generic MCP credential-slot brokering
- local encrypted secret backend first

This keeps the architecture aligned with the current codebase, avoids introducing a separate control plane, and minimizes duplication between AuthNZ storage and MCP Hub policy state.
