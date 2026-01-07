# PRD: Per-User Bring Your Own Keys (BYOK)

## Summary
Enable per-user provider API keys in multi-user mode so each user can bring their own credentials instead of using server defaults.

## Problem Statement
In multi-user environments, all provider calls currently rely on server-level keys. This couples usage and billing to the server operator and prevents users from supplying their own credentials.

## Goals
- Allow authenticated users to create, update, list, and delete provider keys.
- Support admin-managed team/org shared keys in v1.
- Resolve credentials per request with a clear precedence order.
- Store secrets securely and prevent exposure in logs or responses.
- Provide clear errors when a provider key is missing.

## Non-Goals
- Direct billing or payment handling.
- OAuth or provider-managed auth flows.
- Per-request key overrides (disabled for security).

## Personas
- Regular user who wants to use their own provider account.
- Admin/operator who wants safe defaults and visibility.

## User Stories
- As a user, I can add my provider key and use it for requests.
- As a user, I can delete my key and fall back to server defaults.
- As an admin, I can disable BYOK globally or restrict providers.
- As an admin, I can revoke a user's stored key or a shared key and force server defaults.
- As a user, I get a clear error if I request a provider without a key.

## Functional Requirements
- **Credential resolution order**
  - user BYOK -> team shared -> org shared -> server default (scope from token claims).
  - Per-request override keys are not supported.
  - If no credential exists for a provider that requires auth, return a 503 with a clear message (`error_code=missing_provider_credentials`).
- **Scope resolution**
  - Resolve `team_ids` and `org_ids` from token claims. If multiple are present, use `active_team_id`/`active_org_id`; if no active scope is set, skip shared-key lookup.
- **API endpoints**
  - `POST /api/v1/users/keys` create or update a key for a provider.
  - `GET /api/v1/users/keys` list providers and key status (masked).
  - `DELETE /api/v1/users/keys/{provider}` remove a key.
  - Optional: `POST /api/v1/users/keys/test` validate a key.
  - Admin endpoints for shared keys and user key revocation (see API and Schemas).
  - Team/org scoped shared-key endpoints for team/org managers (see API and Schemas).
- **Provider integration**
  - Provider call stack accepts resolved credentials at runtime.
  - Config-based keys remain supported as defaults.
- **Admin controls**
  - Config to allow or disable BYOK globally.
  - Allowlist of providers for BYOK storage and runtime BYOK usage (server defaults remain usable).
  - If a provider is removed from the allowlist, stored BYOK keys are ignored at runtime and UI marks them disabled until re-allowed.
  - Admin tooling to revoke (delete) user or shared keys and force server defaults.
- **Team/org shared keys**
  - Admin-managed shared keys scoped to team/org membership.
  - Stored and resolved using the same encryption and allowlist rules as user keys.

## Non-Functional Requirements
- **Security**
  - Encrypt secrets at rest using a master key from `.env`.
  - Never log secrets; redact in logs and exceptions.
- **Auditability**
  - Track `created_at`, `updated_at`, `last_used_at`, and actor fields for admin actions (`created_by`, `updated_by`, `revoked_by`, `revoked_at`).
  - Update `last_used_at` on successful provider calls or successful key tests; throttle updates to avoid hot writes.
- **Performance**
  - Minimal overhead per request; cache decrypted key in request scope.

## Data Model
New table in AuthNZ DB (name illustrative):
- `user_provider_secrets`
  - `id`, `user_id`, `provider`, `encrypted_blob`, `key_hint`, `created_at`, `updated_at`, `last_used_at`, `metadata`
  - `created_by`, `updated_by`, `revoked_by`, `revoked_at` (for admin actions when applicable)
  - Unique constraint on `(user_id, provider)`.
Additional table for shared keys (name illustrative):
- `org_provider_secrets` (or team-scoped equivalent)
  - `id`, `scope_type`, `scope_id`, `provider`, `encrypted_blob`, `key_hint`, `created_at`, `updated_at`, `last_used_at`, `metadata`
  - `created_by`, `updated_by`, `revoked_by`, `revoked_at`
  - Unique constraint on `(scope_type, scope_id, provider)`.

## UX Requirements
- Settings page lists providers and key status:
  - "Using server default", "Using your key", or "BYOK disabled" with last used date.
- Add/edit key form with validation feedback.
- Delete confirmation with fallback messaging.

## Security and Compliance
- Encrypt secrets before storage.
- Mask key display (show last 4 chars only).
- Validate provider names against allowlist on key write and runtime BYOK resolution.

## Telemetry and Metrics
- Count key create/update/delete events.
- Track provider calls resolved by BYOK vs server default.
- Error rate for missing keys.
- Metrics are local-only by default (no external export without explicit opt-in).

## Rollout Plan
- Phase 1: API + storage + backend resolution.
- Phase 2: Web UI settings and key test flow.
- Phase 3: Admin allowlist, shared keys, and usage metrics.

## Risks and Mitigations
- **Leakage of secrets**: strict logging redaction and encryption at rest.
- **Provider-specific auth quirks**: centralize credential injection and validation.
- **Config drift**: default to server keys when user keys removed.

## Open Questions
- Which providers require additional credential fields beyond `api_key`, and how should they be validated?

## Decisions
- Eligible providers at launch: all commercial providers.
- Team/org key sharing is in scope for v1.
- Scope resolution uses token claims with Personal -> Team -> Org -> Server default precedence.
- BYOK credential fields never inherit server defaults; users must supply required account-scoped fields.

# Design

## Architecture Overview
- Store BYOK secrets (user and team/org shared) in the AuthNZ database alongside user records.
- Add a credential resolver used by chat, embeddings, audio, and any provider-backed endpoint.
- Encrypt secrets at rest with AES-GCM using existing crypto helpers.
- Gate BYOK behavior with AuthNZ settings and a provider allowlist.

## Components and Placement
- `tldw_Server_API/app/core/AuthNZ/repos/user_provider_secrets_repo.py` for DB access.
- `tldw_Server_API/app/core/AuthNZ/user_provider_secrets.py` for encrypt/decrypt, validation, masking.
- Extend repos/services above to support shared key scopes (`scope_type`, `scope_id`).
- `tldw_Server_API/app/api/v1/endpoints/user_keys.py` for CRUD endpoints.
- `tldw_Server_API/app/api/v1/schemas/user_keys.py` for request/response models.
- `tldw_Server_API/app/core/AuthNZ/migrations.py` new migration for the table.

## Data Model Details
- `user_provider_secrets` columns:
  - `id` (PK), `user_id` (FK), `provider`
  - `encrypted_blob` (AES-GCM JSON envelope with `api_key` and optional `credential_fields`)
  - `key_hint` (last 4 chars), `metadata` (JSON for non-sensitive tags)
  - `created_at`, `updated_at`, `last_used_at`
  - `created_by`, `updated_by`, `revoked_by`, `revoked_at`
- Unique index on `(user_id, provider)` and normalized lower-case provider names.
- Shared keys store the same envelope, audit fields, and metadata with scope fields (`scope_type`, `scope_id`).
- `credential_fields` validation strategy:
  - Use provider capability metadata to define allowed fields per provider.
  - Default allowed keys for unknown providers: `org_id`, `project_id`. `base_url` requires explicit provider allowlist config to avoid SSRF.
  - Reject unknown keys unless explicitly allowlisted via config override.
  - For providers that require auth, user/shared keys must include `api_key`; do not merge server-default `api_key` into BYOK entries with custom `credential_fields`.

## Encryption and Storage
- Add BYOK-specific helpers that encrypt with `BYOK_ENCRYPTION_KEY` and decrypt with primary + secondary keys.
- `BYOK_ENCRYPTION_KEY` for primary encryption; optional `BYOK_SECONDARY_ENCRYPTION_KEY` for dual-read during rotations.
- Rotation flow: admin triggers rotation via CLI/maintenance script, set secondary, dual-read, re-encrypt all rows in batches, then retire secondary.
- Store only the encrypted envelope; derive `key_hint` before encryption.
- Never log plaintext or decrypted keys.

## Credential Resolution Flow
1. Resolve provider name from request or default config.
2. If `AUTH_MODE=single_user` or BYOK is disabled, skip BYOK lookup.
3. Determine scope context from token claims (`team_ids`/`org_ids` and optional `active_team_id`/`active_org_id` when multiple). No request-supplied scope overrides.
4. If BYOK is enabled and provider is allowlisted, load and decrypt user key (if present).
5. If allowlisted and no user key, load and decrypt team shared key using the token scope context (if present).
6. If allowlisted and no team key, load and decrypt org shared key using the token scope context (if present).
7. If a user/team/org key exists, use its `api_key` and its `credential_fields` as-is. Do not inherit server-default `credential_fields` for BYOK entries to avoid cross-account coupling; missing required fields must fail validation. Empty strings are invalid.
8. Otherwise, use server default provider key.
9. If no key is available and the provider requires auth, return a 400 with a clear message.

## API and Schemas
- `POST /api/v1/users/keys`
  - Request: `{ "provider": "openai", "api_key": "sk-...", "credential_fields": { "org_id": "...", "base_url": "..." }, "metadata": {...} }`
  - Response: `{ "provider": "openai", "status": "stored", "key_hint": "....1234", "updated_at": "..." }`
- `GET /api/v1/users/keys`
  - Response includes allowlisted providers and any stored-but-disallowed providers with status: `{ "items": [ { "provider": "openai", "has_key": true, "source": "user|team|org|server_default|none|disabled", "key_hint": "....1234", "last_used_at": "..." } ] }`
  - `key_hint` is only included when `source=user`; otherwise it is omitted.
- `DELETE /api/v1/users/keys/{provider}` -> 204
- Optional `POST /api/v1/users/keys/test` validates the stored key for the provider with a lightweight provider call (no `api_key` in the request body).
  - Request: `{ "provider": "openai", "model": "gpt-4o-mini" }`
  - Response: `{ "provider": "openai", "status": "valid", "model": "gpt-4o-mini" }`
- `POST /api/v1/admin/keys/shared`
  - Request: `{ "scope_type": "org|team", "scope_id": "org_123", "provider": "openai", "api_key": "sk-...", "credential_fields": { "org_id": "...", "base_url": "..." }, "metadata": {...} }`
  - Response: `{ "scope_type": "org", "scope_id": "org_123", "provider": "openai", "status": "stored", "key_hint": "....1234", "updated_at": "..." }`
- `GET /api/v1/admin/keys/shared`
  - Query params: `scope_type`, `scope_id`, `provider` (optional filters).
  - Response: `{ "items": [ { "scope_type": "org", "scope_id": "org_123", "provider": "openai", "key_hint": "....1234", "last_used_at": "..." } ] }`
- Optional `POST /api/v1/admin/keys/shared/test` validates a stored shared key with a lightweight provider call (no `api_key` in the request body).
  - Request: `{ "scope_type": "org|team", "scope_id": "org_123", "provider": "openai", "model": "gpt-4o-mini" }`
  - Response: `{ "scope_type": "org", "scope_id": "org_123", "provider": "openai", "status": "valid", "model": "gpt-4o-mini" }`
- `DELETE /api/v1/admin/keys/shared/{scope_type}/{scope_id}/{provider}` -> 204
- `GET /api/v1/admin/keys/users/{user_id}`
  - Response: `{ "user_id": 123, "items": [ { "provider": "openai", "key_hint": "....1234", "last_used_at": "...", "allowed": true } ] }`
- `DELETE /api/v1/admin/keys/users/{user_id}/{provider}` -> 204 (admin revoke user key)
- Team/org scoped shared-key endpoints (same payloads/responses as admin shared endpoints):
  - `/api/v1/orgs/{org_id}/keys/shared` (POST/GET)
  - `/api/v1/orgs/{org_id}/keys/shared/{provider}` (DELETE)
  - Optional `/api/v1/orgs/{org_id}/keys/shared/test`
  - `/api/v1/teams/{team_id}/keys/shared` (POST/GET)
  - `/api/v1/teams/{team_id}/keys/shared/{provider}` (DELETE)
  - Optional `/api/v1/teams/{team_id}/keys/shared/test`

## Validation Rules (BYOK)
- BYOK requests must supply all account-scoped fields required by the provider (e.g., `org_id`, `project_id`, or `base_url` when allowed). No fallback to server defaults for these fields.
- `api_key` is required for providers that require auth.
- Unknown providers only allow `org_id` and `project_id` by default; `base_url` requires an explicit provider allowlist entry.

## Integration Points
- Chat: inject resolved credentials into adapter request (`api_key` + allowed `credential_fields`).
- Embeddings: inject `api_key` and allowed `credential_fields` in embeddings requests.
- Audio/TTS: resolve credentials in the service layer for providers that use API keys or custom base URLs.
- RAG and evaluations reuse embeddings resolution so they inherit BYOK.

## RBAC and Auth
- Endpoints require authenticated users (`get_current_active_user` or `get_auth_principal`).
- Users can only manage their own keys in v1.
- Admins can revoke user keys and manage shared team/org keys.
- Global admin endpoints (`/api/v1/admin/keys/...`) require admin role.
- Team/org scoped endpoints (`/api/v1/orgs/{org_id}/keys/shared`, `/api/v1/teams/{team_id}/keys/shared`) require team/org manager roles (owner/admin/lead) or global admin.
- Token claims must include `team_ids`/`org_ids` and optional `active_team_id`/`active_org_id` when multiple scopes exist, to select shared keys deterministically.

## Configuration
- `BYOK_ENABLED` (default false; ignored in single-user mode).
- `BYOK_ALLOWED_PROVIDERS` (comma-separated allowlist).
- `BYOK_ALLOWED_BASE_URL_PROVIDERS` (comma-separated allowlist for providers that accept BYOK `base_url`).
- Default allowlist: all commercial providers (can be overridden).
- `BYOK_ENCRYPTION_KEY` and optional `BYOK_SECONDARY_ENCRYPTION_KEY`.

## Provider Auth Requirements
- Define `requires_auth` per provider using capability metadata in adapter registries.
- For unknown/custom providers, default to requiring auth unless explicitly marked otherwise in config.

## Error Handling
- 400 for invalid providers or malformed payloads.
- 503 for missing required provider credentials at runtime (`error_code=missing_provider_credentials`).
- 403 when BYOK is disabled, provider is disallowed, or in single-user mode for key management endpoints.
- 404 for delete requests when a user key does not exist, and for `/keys/test` when no stored key exists for the provider.
- 401/403 for `/keys/test` when provider rejects credentials; 502 for provider outage/timeouts.

## UI Design Notes
- Settings page lists providers with status and last-used time.
- Add/edit key modal with masked display and validation feedback.
- Delete confirmation clarifies fallback to server default keys.

---

# Implementation Plan

## Stage 1: Data Model and Crypto
**Goal**: Store per-user provider keys securely.
**Success Criteria**: Encrypted key storage with unique per-user per-provider enforcement; migration added.
**Tests**: Unit tests for encrypt/decrypt, dual-read rotation, and CRUD paths.
**Status**: Complete

## Stage 2: Backend Resolution and API Surface
**Goal**: Resolve credentials per request and expose CRUD endpoints.
**Success Criteria**: Provider calls use resolved credentials; endpoints return masked status and proper errors.
**Tests**: Integration tests for endpoints, resolution precedence, redaction, and request override rejection.
**Status**: Complete

## Stage 3: Web UI Settings
**Goal**: Allow users to manage keys from the UI.
**Success Criteria**: Add/edit/delete flows with validation and status display.
**Tests**: Frontend tests for key management flows.
**Status**: In Progress

## Stage 4: Admin Controls and Metrics
**Goal**: Allow BYOK gating and monitor adoption.
**Success Criteria**: Config-based allow/deny list; shared team/org keys and admin revoke flow; metrics emitted for usage and errors.
**Tests**: Config-driven behavior tests; metrics emission checks.
**Status**: In Progress

## Remaining Work (Summary)
- Implement full BYOK key management UI (list, add/edit/delete, test) with API wiring and validation feedback.
- Add BYOK-specific admin dashboards and wire to metrics endpoints (adoption, resolution sources, missing credentials, key activity).
- Capture audit actor fields (`created_by`, `updated_by`, `revoked_by`) in BYOK tables and expose in admin views.
- Formalize provider-specific required credential fields and validation metadata.
