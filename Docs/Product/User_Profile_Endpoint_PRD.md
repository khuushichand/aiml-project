# User Profile Endpoint PRD

## Overview
- Objective: Provide a single, authoritative endpoint for users and admins to view a full user profile plus all associated configuration, with clear editability rules and metadata to power a unified settings UI.
- Primary outcomes: reduce settings discovery time, enable self-service changes, and allow admins to audit or bulk-apply configuration across orgs/teams without digging through multiple endpoints.
- Scope: API-first profile read and update surfaces (self + admin), plus a config catalog to describe what can be edited and how.

## Background & Problem Statement
- Today, user data is spread across multiple endpoints (users, admin, keys, orgs/teams, quotas, providers).
- The WebUI needs a single control panel that can show "what is configurable", "current value", and "who can edit it."
- Admins need a consistent way to review and apply configuration across an org/team without bespoke scripts or manual API calls.

## Goals
- Deliver a unified profile response that aggregates identity, security, membership, quotas, usage, and user-specific configuration.
- Provide a config catalog with metadata for UI rendering (labels, types, defaults, constraints, editability).
- Support self-service updates for allowed fields and admin updates for scoped users.
- Provide a bulk update endpoint with dry-run and audit logging.

## Non-Goals
- Replacing or removing existing endpoints (users, admin, orgs, privileges, keys) in v1.
- Returning or storing secrets in clear text (API keys, BYOK, passwords).
- Building the WebUI itself.

## Personas & Use Cases
- End User: view account details, quotas, and personal preferences in one page; adjust safe preferences.
- Admin: audit a user profile, see effective config sources, and apply org/team standards.
- Support/Success: quickly inspect a user profile for troubleshooting.

## Functional Requirements

### Profile Sections (v1 required)
- Identity: id, uuid, username, email, role, created_at, last_login, status flags.
- Memberships: orgs, teams, roles, and org/team-level policy summaries.
- Security: MFA status, active sessions count, API key metadata (masked), BYOK key presence (no secrets).
- Quotas & Usage: storage quota/usage, relevant resource governors (audio minutes, evaluation quotas, etc).
- Preferences: user-editable settings (UI defaults, preferred models, prompt defaults).
- Effective Config: layered settings with source attribution (global -> org -> team -> user).

### Config Catalog
- Endpoint exposes a catalog of config keys with:
  - `key`, `label`, `description`, `type`, `enum`, `min/max`, `default`.
  - `editable_by`: user, admin, org_admin, team_admin.
  - `sensitivity`: public, internal, secret.
  - `ui`: input hint (text, toggle, select, number, json).
- Catalog is implemented as a code registry owned by the backend API team, versioned and cached; the profile response includes `catalog_version`.

### Editability Roles
- user: the subject user updating their own profile.
- org_admin: admin or owner for the user's organization membership.
- team_admin: lead/admin for the user's team membership.
- platform_admin: global admin role across the deployment.

### V1 Config Keys and Editability (initial catalog)

User-editable (self):
- `identity.email`
- `preferences.ui.theme`
- `preferences.ui.timezone`
- `preferences.ui.locale`
- `preferences.ui.date_format`
- `preferences.ui.density`
- `preferences.chat.default_model`
- `preferences.chat.temperature`
- `preferences.chat.max_output_tokens`
- `preferences.chat.system_prompt`
- `preferences.rag.default_top_k`
- `preferences.rag.rerank_enabled`
- `preferences.media.default_chunking_template_id`
- `preferences.audio.transcription_language`
- `preferences.audio.diarization_enabled`
- `preferences.audio.tts_voice`

Org/team admin editable (scoped):
- `memberships.orgs.role` (org_admin, platform_admin)
- `memberships.teams.role` (team_admin, org_admin, platform_admin)
- `memberships.teams.member` (add/remove; team_admin, org_admin, platform_admin)
- `limits.storage_quota_mb` (org_admin, platform_admin)
- `limits.audio_daily_minutes` (org_admin, platform_admin)
- `limits.audio_concurrent_jobs` (org_admin, platform_admin)
- `limits.evaluations_per_minute` (org_admin, platform_admin)
- `limits.evaluations_per_day` (org_admin, platform_admin)

Platform admin only:
- `identity.role`
- `identity.is_active`
- `identity.is_verified`
- `identity.is_locked`

Read-only in profile (managed via dedicated endpoints):
- `security.api_keys` (use `/users/api-keys` or admin equivalents)
- `security.sessions` (use `/users/sessions` or admin equivalents)
- `security.byok_keys` (use BYOK endpoints)
- `quotas.storage_used_mb` and derived usage metrics
- `effective_config.*` (computed view only)

### Read Endpoints
- `GET /api/v1/users/me/profile`
  - Returns the profile for the authenticated user.
- `GET /api/v1/admin/users/{user_id}/profile`
  - Returns profile for a user within admin scope (existing org/team guardrails apply).
- `GET /api/v1/admin/users/profile`
  - Batch profile summaries; supports `user_ids`, `org_id`, `team_id`, `role`, `is_active`, `search`, pagination.
- `GET /api/v1/users/profile/catalog`
  - Returns config catalog and schema metadata for the UI.

### Query Parameters
- `sections`: comma-separated list to include only specific sections (identity, security, quotas, preferences, memberships, effective_config).
- `include_sources`: include per-field source attribution (default false for size).
- `include_raw`: admin-only, includes raw stored values where safe.
- `mask_secrets`: default true; when false (admin-only), still returns only hints, never raw secrets.

### Update Endpoints
- `PATCH /api/v1/users/me/profile`
  - User updates allowed keys (preferences and user-level overrides only).
- `PATCH /api/v1/admin/users/{user_id}/profile`
  - Admin or org/team admin updates any editable fields per catalog and scope.
- Request payload (patch list with validation):
  ```json
  {
    "updates": [
      {"key": "preferences.ui.timezone", "value": "America/Denver"},
      {"key": "limits.storage_quota_mb", "value": 10240}
    ],
    "dry_run": false
  }
  ```
- Response includes applied changes, skipped keys with reasons, and updated `profile_version`.

### Bulk Update (Admin)
- `POST /api/v1/admin/users/profile/bulk`
  - Filters: `org_id`, `team_id`, `user_ids`, `role`, `is_active`, `search`.
  - Supports `dry_run` to preview counts and diff summaries.
  - Requires explicit `confirm=true` when more than N users (configurable guardrail).
  - Emits audit events with actor, target set, keys changed, and source IP.

## Response Shape (Example)
```json
{
  "profile_version": "2025-01-15T12:00:00Z",
  "catalog_version": "v1.0",
  "user": {
    "id": 42,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "username": "jdoe",
    "email": "jdoe@example.com",
    "role": "user",
    "is_active": true,
    "is_verified": true,
    "created_at": "2024-07-01T10:00:00Z",
    "last_login": "2025-01-12T09:30:00Z"
  },
  "memberships": {
    "orgs": [{"org_id": 1, "role": "member"}],
    "teams": [{"team_id": 5, "role": "lead"}]
  },
  "security": {
    "mfa_enabled": false,
    "api_keys": [{"id": 10, "name": "cli", "last_used_at": "2025-01-10T13:00:00Z"}],
    "byok_keys": [{"provider": "openai", "has_key": true}]
  },
  "quotas": {
    "storage_quota_mb": 5120,
    "storage_used_mb": 822.4,
    "audio_minutes_remaining": 120,
    "evals_per_minute": 60
  },
  "preferences": {
    "ui.theme": {"value": "paper", "source": "user"},
    "chat.default_model": {"value": "gpt-4.1-mini", "source": "org"}
  }
}
```

## Permissions & RBAC
- Self profile access requires normal auth (JWT or API key) and returns only self data.
- Admin profile access reuses existing admin org/team scope checks; org/team admins can update fields scoped to their memberships; no cross-org leakage.
- Sensitive fields are always masked; secrets are never returned.
- Bulk updates require admin role; org/team admins can bulk-update within their scope.

## Non-Functional Requirements
- Performance: single user profile response under 300 ms for typical loads; batch reads paginated.
- Reliability: partial section failures return `section_errors` while preserving overall 200 response when feasible.
- Security: strict masking, audit logging for admin reads and any write operations.
- Observability: metrics for profile fetch latency, section build time, bulk update count, and error rates.

## Technical Approach
- Implement `UserProfileService` in `tldw_Server_API/app/core/` to compose:
  - AuthNZ user record, org/team memberships, MFA status, sessions, API keys, BYOK presence.
  - Quota/usage services (storage, audio, evaluations).
  - User preferences and per-user overrides (new table described below).
- Add a config catalog as a code registry to define keys, types, editability, and UI metadata.
- Store user-specific overrides in a new table (e.g., `user_config_overrides`) with:
  - `user_id`, `key`, `value_json`, `updated_at`, `updated_by`.
  - Optional `scope` for org/team overrides in the future.
- Merge config layers into an "effective" view with source annotations.

## Implementation Phases
1. Profile Read (MVP)
   - `GET /users/me/profile`, `GET /admin/users/{user_id}/profile`.
   - Identity, memberships, quotas, and security metadata.
2. Config Catalog + Preferences
   - Config catalog endpoint and user preference reads.
   - User-level overrides stored in `user_config_overrides`.
3. Updates + Bulk
   - PATCH endpoints for self/admin.
   - Bulk update with dry-run and audit events.

## Testing Strategy
- Unit tests for config catalog validation and config merge logic.
- Integration tests for self/admin profile retrieval and permissions.
- Bulk update tests for filters, dry-run, and audit emission.
- Security tests to ensure secrets are never returned and admin scope is enforced.

## Risks & Mitigations
- Response bloat: require `sections` filtering and pagination for batch profile reads.
- Inconsistent sources: use a single service layer to compute effective config with source tags.
- Security leaks: centralized redaction utilities and schema-driven masking.
- Backward compatibility: keep existing endpoints intact; profile endpoint is additive.

## Open Questions
- None for v1. Revisit after frontend discovery to expand the catalog.
