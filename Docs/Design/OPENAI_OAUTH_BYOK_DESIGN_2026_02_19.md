# OpenAI OAuth BYOK Design (Opencode-Style Account Linking)

Status: Draft  
Last Updated: 2026-02-19  
Owner: AuthNZ + Chat + WebUI

## Summary
This design adds an OpenAI OAuth credential flow so a signed-in tldw user can link an OpenAI account without manually pasting an API key, while preserving the existing BYOK model and runtime resolution path.

The implementation reuses these existing foundations:
- BYOK secret storage and encryption in `tldw_Server_API/app/core/AuthNZ/user_provider_secrets.py`
- BYOK runtime resolution in `tldw_Server_API/app/core/AuthNZ/byok_runtime.py`
- BYOK user key endpoints in `tldw_Server_API/app/api/v1/endpoints/user_keys.py`
- Existing OAuth pattern and state handling from connectors in `tldw_Server_API/app/api/v1/endpoints/connectors.py` and `tldw_Server_API/app/core/External_Sources/connectors_service.py`

## Problem
Current BYOK assumes a user supplies a static API key (`/api/v1/users/keys`). For OpenAI account-linking UX (similar to opencode), users expect:
- Browser sign-in/consent flow
- No manual key entry
- Silent token refresh
- Existing chat/embeddings/audio flows to continue working with no API contract changes

## Goals
- Add OpenAI OAuth connect/disconnect/status endpoints under the existing `/api/v1/users/keys` surface.
- Store OAuth credentials using existing BYOK encryption, without exposing refresh/access tokens in API responses.
- Keep runtime call sites mostly unchanged by still resolving an `api_key`-like bearer value for provider calls.
- Support auto-refresh and one-time retry behavior for expired/revoked tokens.
- Preserve API-key BYOK as a first-class fallback.

## Non-Goals
- Replacing existing API-key BYOK flows.
- Generalizing to all providers in phase 1.
- Building org/team shared OAuth credentials in phase 1.
- Frontend redesign beyond minimal account-linking controls.

## Assumptions and Compatibility Constraints
- The deployment has a valid OpenAI OAuth client registration and token exchange contract.
- OpenAI OAuth support is feature-flagged; if not configured, the new endpoints fail closed (`403`/`501`).
- OAuth access token compatibility is verified during callback exchange with a lightweight provider probe before the credential is marked connected.

## Proposed API Contract
All endpoints live on the existing users router: `APIRouter(prefix="/users")`.

### 1) Start OAuth
`POST /api/v1/users/keys/openai/oauth/authorize`

Request body:
```json
{
  "credential_fields": {
    "org_id": "optional",
    "project_id": "optional"
  },
  "return_path": "/settings/model"
}
```

Response:
```json
{
  "provider": "openai",
  "auth_url": "https://...",
  "auth_session_id": "server-generated-session-id",
  "expires_at": "2026-02-19T18:30:00Z"
}
```

Behavior:
- Validates BYOK enabled and OpenAI allowlisted.
- Generates server-owned state (client cannot provide state).
- Resolves redirect URI from server configuration/allowlist only (client cannot provide arbitrary redirect URI).
- Persists short-lived OAuth state record with PKCE verifier (encrypted) and session metadata.
- Returns provider authorize URL.

### 2) OAuth Callback Exchange
`GET /api/v1/users/keys/openai/oauth/callback?code=...&state=...`

Response:
```json
{
  "provider": "openai",
  "status": "stored",
  "auth_source": "oauth",
  "key_hint": "oauth",
  "updated_at": "2026-02-19T18:21:09Z",
  "expires_at": "2026-02-19T19:21:09Z"
}
```

Behavior:
- Callback endpoint is intentionally unauthenticated and state-bound. It must not depend on `get_auth_principal`.
- Validates and consumes state (single-use, TTL-bound), deriving target user from state record ownership.
- Exchanges authorization code for token bundle.
- Executes compatibility probe using returned access token against OpenAI API before marking connected.
- Stores encrypted token payload in `user_provider_secrets` for provider `openai`.
- If an API-key credential already exists for provider `openai`, preserve it and add OAuth credential without implicit destructive replacement.
- Returns JSON for API clients; optional 303 redirect to configured frontend success path is supported.

### 3) OAuth Status
`GET /api/v1/users/keys/openai/oauth/status`

Response:
```json
{
  "provider": "openai",
  "connected": true,
  "auth_source": "oauth",
  "updated_at": "2026-02-19T18:21:09Z",
  "last_used_at": "2026-02-19T18:25:00Z",
  "expires_at": "2026-02-19T19:21:09Z",
  "scope": "..."
}
```

Behavior:
- Returns OAuth-specific status from encrypted payload metadata.
- Never returns access token, refresh token, id token, or token hash.

### 4) Manual Refresh (User Recovery/Debug)
`POST /api/v1/users/keys/openai/oauth/refresh`

Response:
```json
{
  "provider": "openai",
  "status": "refreshed",
  "updated_at": "2026-02-19T18:40:00Z",
  "expires_at": "2026-02-19T19:40:00Z"
}
```

Behavior:
- Forces token refresh using stored refresh token.
- Updates encrypted payload in-place.
- Intended as authenticated user action (not anonymous callback flow).

### 5) Disconnect
`DELETE /api/v1/users/keys/openai/oauth`

Behavior:
- Revokes OAuth credential while preserving API-key credential for the same provider when present.
- Optional remote revocation call, best-effort and non-blocking.

### 6) Active Credential Source Switch
`POST /api/v1/users/keys/openai/source`

Request body:
```json
{
  "auth_source": "oauth"
}
```

Behavior:
- Switches active credential source between `api_key` and `oauth` when both exist.
- Returns `409` if requested source is unavailable.

## Schema Additions (`app/api/v1/schemas/user_keys.py`)
Add models:
- `OpenAIOAuthAuthorizeRequest`
- `OpenAIOAuthAuthorizeResponse`
- `OpenAIOAuthCallbackResponse`
- `OpenAIOAuthStatusResponse`
- `OpenAIOAuthRefreshResponse`
- `OpenAICredentialSourceSwitchRequest`
- `OpenAICredentialSourceSwitchResponse`

Extend existing list response model with optional source detail:
- `UserProviderKeyStatusItem.auth_source: Literal["api_key", "oauth"] | None`

Backward compatibility:
- Existing `UserProviderKeyResponse` and `/users/keys` endpoints remain unchanged.
- OAuth endpoint responses are additive and do not break current clients.

## Storage Model
### Reuse Existing BYOK Table
Keep using `user_provider_secrets` in `AuthnzUserProviderSecretsRepo` with encrypted payload.

New encrypted payload shape (OpenAI credential set):
```json
{
  "credential_version": 2,
  "active_auth_source": "oauth",
  "credentials": {
    "api_key": {
      "api_key": "sk-...",
      "stored_at": "2026-02-19T10:00:00Z"
    },
    "oauth": {
      "access_token": "<access_token>",
      "refresh_token": "<refresh_token>",
      "token_type": "Bearer",
      "scope": "...",
      "expires_at": "2026-02-19T19:21:09Z",
      "issued_at": "2026-02-19T18:21:09Z",
      "subject": "optional-sub"
    }
  },
  "credential_fields": {
    "org_id": "optional",
    "project_id": "optional"
  }
}
```

Notes:
- Do not duplicate OAuth access token into a top-level `api_key` field for v2 payloads.
- Resolver derives runtime bearer from active source.
- Maintain backward compatibility by supporting legacy payloads (`{"api_key": "...", ...}`) during read.
- `key_hint` remains non-sensitive and reflects active source (`oauth` or masked API key suffix).

### New OAuth State Table
Add a dedicated AuthNZ OAuth state table (do not reuse connector table to avoid cross-domain coupling):
- Table: `byok_oauth_state`
- Columns:
  - `state` (PK-part)
  - `user_id` (PK-part)
  - `provider`
  - `auth_session_id`
  - `redirect_uri`
  - `pkce_verifier_encrypted`
  - `created_at`
  - `expires_at`
  - `consumed_at` (nullable)
  - `return_path` (nullable)

Add ensure/migration support for both SQLite and PostgreSQL in AuthNZ migration paths.
Add indexes:
- `(provider, expires_at)`
- `(user_id, provider, consumed_at)`

State cleanup:
- Scheduled purge of expired/consumed rows.
- Hard cap per-user/provider outstanding states to prevent table growth abuse.

## Runtime Resolution and Refresh
### Core principle
All call sites continue asking BYOK runtime for provider credentials; runtime decides whether credential source is API key or OAuth.

### Changes in `byok_runtime.resolve_byok_credentials`
- Detect v2 credential-set payload (`credential_version == 2`) and legacy payload variants.
- Resolve active source from `active_auth_source`.
- If token near expiry (configurable skew, default 120s), refresh before returning.
- On refresh success:
  - update encrypted payload
  - update `updated_at`
  - return fresh runtime bearer from OAuth credential
- On refresh failure:
  - mark OAuth source unavailable and, when API key source exists, fall back to API key source
  - if neither source is usable, return missing credential result (`api_key=None`) and emit metrics.

### One-time 401 refresh+retry
For OpenAI provider call paths (`chat`, `embeddings`, `audio`):
- If call fails with `401` and current credential source is OAuth:
  - force-refresh credentials once (`force_refresh=True`)
  - retry provider call once
- If second attempt fails, propagate original auth error.

### Locking
Use per-user+provider async lock to prevent refresh stampedes:
- lock key: `byok_oauth_refresh:{user_id}:{provider}`
- require distributed lock backend (DB advisory lock or Redis) before production multi-worker enablement
- in-process lock only allowed for single-worker/dev environments

## Security Requirements
- OAuth state is single-use and TTL-bound (default 10 minutes).
- PKCE verifier stored encrypted at rest and deleted/marked consumed after callback.
- Do not log bearer tokens, refresh tokens, codes, verifier, or id token.
- Callback validates:
  - state ownership (`user_id`, `provider`)
  - state freshness
  - expected redirect URI (exact match against server allowlist/config)
- CSRF protections from existing auth stack remain enabled.
- `base_url` override policy remains unchanged and only from trusted callers.
- Callback route must not rely on ambient browser session auth; authorization is entirely state-bound.
- `return_path` is sanitized to local application-relative paths only (no open redirect).

## Configuration and Feature Flags
Add settings/env:
- `OPENAI_OAUTH_ENABLED` (default `false`)
- `OPENAI_OAUTH_CLIENT_ID`
- `OPENAI_OAUTH_CLIENT_SECRET`
- `OPENAI_OAUTH_AUTH_URL`
- `OPENAI_OAUTH_TOKEN_URL`
- `OPENAI_OAUTH_SCOPES`
- `OPENAI_OAUTH_STATE_TTL_MINUTES` (default `10`)
- `OPENAI_OAUTH_REFRESH_SKEW_SECONDS` (default `120`)
- `OPENAI_OAUTH_REDIRECT_URI`
- `OPENAI_OAUTH_ALLOWED_RETURN_PATH_PREFIXES`
- `OPENAI_OAUTH_REFRESH_LOCK_BACKEND` (`memory|redis|db`)

BYOK gating remains:
- multi-user mode
- `BYOK_ENABLED=1`
- provider allowlisted (`openai`)

## Observability
Add counters/histograms:
- `byok_oauth_authorize_started_total{provider}`
- `byok_oauth_callback_success_total{provider}`
- `byok_oauth_callback_failure_total{provider,reason}`
- `byok_oauth_refresh_total{provider,outcome}`
- `byok_oauth_refresh_latency_ms{provider}`
- `byok_oauth_401_retry_total{provider,outcome}`

Audit events:
- `provider_oauth_authorize_started`
- `provider_oauth_connected`
- `provider_oauth_refreshed`
- `provider_oauth_disconnected`
- `provider_oauth_refresh_failed`

## Frontend Integration (Phase 1)
Current frontend has no dedicated `/api/v1/users/keys` BYOK panel usage. Add a minimal provider card in settings (model/provider settings area):
- Button: `Connect OpenAI`
- Status chip: `Connected (OAuth)` / `API Key` / `Not connected`
- Actions: `Refresh`, `Disconnect`, `Use API Key Instead`

## Rollout Plan
1. Dark launch backend behind `OPENAI_OAUTH_ENABLED=false`.
2. Enable in test/staging with selected users.
3. Enable WebUI controls behind frontend feature flag.
4. Gradually enable in production.
5. Keep API-key fallback documented and available.

## Implementation Phases
### Phase A: Backend Contracts + State Repo
- Add schemas and endpoints in `user_keys.py`.
- Add `byok_oauth_state` repo/service + migrations.
- Add OAuth client helper for OpenAI authorize/token exchange.

### Phase B: Runtime Refresh Integration
- Extend BYOK payload parsing in `byok_runtime.py`.
- Add refresh path and lock.
- Add forced refresh helper.

### Phase C: Call-Site Retry Wiring
- Chat endpoint (`endpoints/chat.py`) openai 401 refresh+retry once.
- Embeddings endpoint (`endpoints/embeddings_v5_production_enhanced.py`) same behavior.
- Audio paths for OpenAI-based calls.

### Phase D: UI + Docs + Metrics
- Add settings/provider connect flow.
- Update docs and quickstart.
- Add dashboards/alerts for OAuth failures and refresh churn.

## Test Matrix
### Unit Tests
- OAuth state create/consume/expiry/replay protection.
- OAuth payload encrypt/decrypt round trip.
- Refresh path success/failure and lock contention.
- Credential parser: legacy single-key payload vs v2 multi-source payload variants.

### Integration Tests
- `POST authorize` returns URL/auth-session metadata.
- Callback rejects invalid/expired state.
- Callback stores BYOK secret with `auth_source=oauth`.
- Status endpoint redacts secrets.
- Refresh endpoint rotates token and updates expiry.
- Disconnect removes OAuth credential.
- Existing API key remains available after OAuth connect/disconnect.
- Source switch endpoint enforces availability and returns `409` on invalid switch.

### Endpoint Runtime Tests
- Chat with expired OAuth token triggers refresh and succeeds.
- Chat with revoked refresh token returns auth-class failure (`401/403 reconnect_required`) when no API key fallback exists.
- Embeddings path refresh+retry behavior.
- No regression for API-key BYOK and server default key fallback.

### Existing Test Suites to Extend
- `tldw_Server_API/tests/AuthNZ_SQLite/test_byok_endpoints_sqlite.py`
- `tldw_Server_API/tests/AuthNZ_Unit/test_byok_runtime.py`
- `tldw_Server_API/tests/AuthNZ/test_byok_endpoints_postgres.py` (new)
- `tldw_Server_API/tests/AuthNZ/test_byok_runtime_postgres.py` (new)
- `tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py` (pattern reference)
- Chat/embeddings integration suites where BYOK key resolution is already covered

## Risks and Mitigations
- OAuth provider contract drift: isolate HTTP contract in one adapter module and add contract tests.
- Refresh token invalidation loops: cap retries and emit explicit refresh-failure metrics.
- Multi-worker race on refresh: enforce distributed lock backend before production multi-worker rollout.
- Confusion between API-key and OAuth credentials: expose `auth_source` in status and UI.
- OAuth callback auth ambiguity: resolve via explicit unauthenticated-but-state-bound callback contract.

## Open Questions
- Should callback default to JSON-only for API clients, with optional redirect mode gated by `return_path`?
- Should manual refresh remain user-only, with separate admin scoped tooling outside user route?
- For phase 2, do we support org/team shared OAuth credentials (`/orgs/{id}/keys/shared`) or keep OAuth user-only?
- Do we need remote token revocation on disconnect, or local revoke is sufficient?

## Definition of Done
- OAuth connect/disconnect/status/refresh endpoints implemented and documented.
- BYOK runtime can resolve and refresh OpenAI OAuth credentials.
- Chat + embeddings + audio pass refresh/retry integration tests.
- API-key BYOK behavior unchanged.
- Metrics and audit events emitted for all OAuth lifecycle actions.
