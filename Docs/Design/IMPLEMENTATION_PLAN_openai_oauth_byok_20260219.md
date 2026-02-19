## Stage 1: AuthNZ OAuth State and Credential Data Foundations
**Goal**: Introduce durable backend primitives for OAuth flow state and multi-source OpenAI credentials without breaking legacy BYOK records.
**Success Criteria**: `byok_oauth_state` schema exists for SQLite/PostgreSQL; credential payload reader supports both legacy (`api_key`) and v2 multi-source payloads; no regressions in existing BYOK key read/write behavior.
**Tests**: Add/update AuthNZ unit tests for state create/consume/expiry/replay; add payload compatibility tests in BYOK runtime/unit suites.
**Status**: Complete

## Stage 2: OpenAI OAuth API Endpoints in User Keys Surface
**Goal**: Implement `/api/v1/users/keys/openai/oauth/*` endpoints (`authorize`, `callback`, `status`, `refresh`, `disconnect`) plus credential source switch endpoint.
**Success Criteria**: OAuth endpoints enforce BYOK/provider gating, use server-owned state and allowlisted redirect handling, and preserve API-key credentials when OAuth credentials are added/removed.
**Tests**: Extend `tldw_Server_API/tests/AuthNZ_SQLite/test_byok_endpoints_sqlite.py`; add new endpoint tests for source switching and callback invalid/expired state behavior.
**Status**: Complete

## Stage 3: BYOK Runtime Resolution, Refresh, and Failover
**Goal**: Extend `resolve_byok_credentials` to support active auth source selection, proactive refresh with skew, fallback to API key when OAuth refresh fails, and missing-credential fail-closed behavior.
**Success Criteria**: Runtime resolves active source deterministically; OAuth refresh updates encrypted payload and metadata; refresh failures yield fallback (if available) or auth-class failure semantics.
**Tests**: Extend `tldw_Server_API/tests/AuthNZ_Unit/test_byok_runtime.py`; add refresh success/failure/fallback cases and legacy-vs-v2 payload parsing tests.
**Status**: Complete

## Stage 4: OpenAI Call-Path Integration and Retry Semantics
**Goal**: Wire one-time OAuth refresh+retry on OpenAI `401` responses for chat, embeddings, and audio call paths.
**Success Criteria**: OpenAI call paths retry once after forced refresh; second failure propagates auth-class error with reconnect-required signal; non-OAuth providers remain unchanged.
**Tests**: Add/extend integration tests in chat and embeddings endpoint suites for expired token refresh path, revoked refresh token path, and no-regression provider behavior.
**Status**: Complete

## Stage 5: Observability, Frontend Controls, and Verification
**Goal**: Add metrics/audit events, minimal WebUI controls for connect/status/switch/disconnect, and verify SQLite+PostgreSQL coverage before rollout.
**Success Criteria**: OAuth lifecycle counters and audit events emitted; settings UI exposes OpenAI OAuth controls; targeted backend/frontend tests pass in project environments.
**Tests**: Add PostgreSQL parity tests (`AuthNZ` BYOK OAuth suites), run targeted pytest modules and frontend vitest/e2e subsets for provider settings flow.
**Status**: Complete
