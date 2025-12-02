# User Auth Dependencies PRD (v0.1)

## Summary

AuthNZ currently has overlapping mechanisms for:

- Attaching the current user to a request (via `User_DB_Handling` and `auth_deps`).
- Authorizing access via permissions and roles (`permissions.py`, `rbac.py`).
- Exposing current user and auth context to other modules (LLM, RAG, MCP, UI).

While the underlying RBAC model is consistent, there is duplication and ambiguity in how “current user”, “current principal”, and authorization checks are wired into the request lifecycle. This PRD proposes:

1. Making authorization checks purely claim-based (no additional RBAC DB lookups on hot paths).
2. Unifying “current user/auth” dependencies around a single `AuthPrincipal` / `AuthContext` dependency (see Principal-Governance PRD).

The goal is to make authentication/authorization dependencies predictable, efficient, and easy to use across the project.

## Related Documents

- `Docs/Design/Principal-Governance-PRD.md` – defines `AuthPrincipal` / `AuthContext` and AuthNZ guardrails.
- `Docs/Design/User-Unification-PRD.md` – defines deployment profiles (`local-single-user`, `multi-user-postgres`) and bootstrap semantics.
- `Docs/Design/Resource_Governor_PRD.md` – describes global resource governance integrated with AuthNZ via `AuthGovernor`.
  - Admin and diagnostics surfaces under `/api/v1/resource-governor/*` are now guarded via claim-first dependencies (`get_auth_principal` + `require_roles("admin")`), with existing integration tests preserved.

---

## Problems & Symptoms

### 1. Mixed Claim-Based and DB-Based Authorization

- `User_DB_Handling.verify_jwt_and_fetch_user`:
  - Decodes JWT / API key.
  - Fetches user data from AuthNZ DB.
  - Enriches with roles and effective permissions by querying RBAC tables.
- `permissions.py`:
  - Checks `user.permissions` / `user.roles` when available.
  - Falls back to DB (`get_user_database().has_permission`) for some checks.
- `rbac.py`:
  - Uses `get_configured_user_database()` to compute effective permissions and check them per user.

This leads to:

- Inconsistent behavior if roles/permissions change during a session.
- Extra DB round-trips on hot paths, even though claims were already computed at authentication time.

### 2. Multiple “Current User” Entry Points

- `User_DB_Handling.get_request_user` + mode-specific helpers.
- `auth_deps.get_current_user` and related dependencies.
- Various endpoints use slightly different dependency stacks for auth, sessions, and scopes.

Symptoms:

- Test code and services need to know which dependency to call to get “the real user”.
- Bugs where one dependency stack attaches `request.state.user_id` but another does not, leading to missing context in downstream code (usage logging, budgets, etc.).

### 3. Context Leaks and Tight Coupling

- Some modules (usage logging, LLM budget guard, resource governance) reach into `request.state` to read `user_id`, `api_key_id`, `org_ids`, `team_ids` directly.
- There is no single structured object that represents “this is the authenticated principal and their claims”.

---

## Goals

### Primary Goals

- **G1: Claim-First Authorization**
  - Make `User.permissions`, `User.roles`, and `AuthPrincipal` claims the canonical source of truth for runtime access decisions.
  - Eliminate extra DB-dependent permission checks on hot paths (except where explicitly needed, e.g., admin tooling).

- **G2: Unified Auth Dependencies**
  - Provide a small set of well-documented FastAPI dependencies:
    - `get_auth_principal` → returns `AuthPrincipal`.
    - `get_current_user` → returns `User` (wrapped principal).
    - `require_permissions`, `require_roles`, etc. built on top of claims.
  - Make all endpoints and middlewares rely on these instead of ad-hoc auth handling.
  - Resource-Governor admin/config endpoints and diagnostics routes are explicit adopters of this stack: they use `require_roles("admin")` (admin role or `principal.is_admin`) as the gate, and reuse the same 401/403 semantics as other claim-first admin surfaces (connectors admin policy, tools admin, embeddings model-management, workflows DLQ).

### Secondary Goals

- Improve test ergonomics:
  - Provide simple ways to stub `AuthPrincipal` / `User` in tests.
- Make it easy to reason about what a route needs: reading dependencies tells you exactly what auth/claims are required.

### Non-Goals (Initial Version)

- Changing external auth APIs (login, token issuance, etc.).
- Replacing non-FastAPI call sites that use decorators (those will be adapted gradually).

---

## Proposed Solution

### 0. Transitional Compatibility Layer

- Existing public dependencies are widely used and form the current compatibility surface:
  - `tldw_Server_API.app.api.v1.API_Deps.auth_deps.get_current_user`, `get_current_active_user`, `require_admin`, `require_role`, `get_optional_current_user`.
  - `tldw_Server_API.app.core.AuthNZ.User_DB_Handling.get_request_user`, `verify_jwt_and_fetch_user`, `verify_single_user_api_key`.
- Today, these:
  - Perform their own JWT/API-key validation and RBAC enrichment (including per-request DB lookups).
  - Write `request.state.user_id/api_key_id/org_ids/team_ids` directly, with no `AuthContext`.
  - Contain single-user-specific behavior (synthetic admin user, direct `SINGLE_USER_API_KEY` comparisons, mode-based bypasses).
- In v1, we will:
  - Keep these functions as *facades* for compatibility, but refactor their internals to delegate to `get_auth_principal` / `AuthContext`.
  - Preserve their external signatures and core HTTP semantics (401/403 behavior, key accepted headers, basic user fields) unless explicitly versioned.
  - Gradually migrate endpoints and tests toward using the new dependencies directly (`get_auth_principal`, `require_permissions`, `require_roles`), then deprecate legacy entry points once usage drops.

### 1. Claim-First Permission Checks

#### Concept

- All runtime authorization checks should be pure functions of claims already attached to the principal.
- DB access for authorization is reserved for:
  - Issuing/refreshing tokens and keys (authentication and session management).
  - Guardrail/accounting operations (rate limits, budgets) as defined in the Principal-Governance and Resource_Governor PRDs.
  - Admin operations (managing roles/permissions).

#### Implementation Sketch

- Strengthen the invariant that `User_DB_Handling` (or `get_auth_principal`) always:
  - Fetches roles and base permissions from RBAC tables.
  - Applies user-specific overrides (allow/deny).
  - Sets `user.roles`, `user.permissions`, and `user.is_admin` on the principal.

- Update `permissions.py`:
  - `check_permission(user, permission)`:
    - First consults `user.permissions` (and possibly `user.is_admin` for implicit permissions).
    - Does not hit the DB in the common case.
  - `check_role(user, role)`:
    - Consults `user.roles` claim.
  - Remove or gate the DB fallback behind a debug or admin-only flag, then phase it out.

- Update/limit usage of `rbac.py` on hot paths:
  - Keep `rbac` for admin APIs (e.g., listing effective permissions, debugging).
  - Avoid calling it from per-request permission checks.

### 2. Unified Auth Dependencies

#### Concept

- Define a single “front door” dependency for auth:
  - `get_auth_principal(request: Request) -> AuthPrincipal`.
- Build all other auth-related dependencies on top of it.

#### Implementation Sketch

- Introduce `get_auth_principal` in AuthNZ (implementation aligned with Principal-Governance PRD).
  - It:
    - Handles credential detection (Bearer, API key, single-user key).
    - Validates via JWT/Session/API-key managers.
    - Hydrates user data and RBAC claims.
    - Attaches to `request.state.auth`.
    - Behaves consistently across deployment profiles:
      - In `local-single-user`, the bootstrapped admin user (`SINGLE_USER_FIXED_ID`) is represented as a normal user principal with admin role and full claims.
      - In `multi-user-postgres`, principals are derived from the authenticated user or service identity using the same code paths.
      - Dependencies do not special-case `AUTH_MODE` or profiles for authorization; claims on `AuthPrincipal` determine access.

- Provide derivative dependencies:
  - `get_current_user(principal: AuthPrincipal = Depends(get_auth_principal)) -> User`.
  - `require_permissions(perms: list[str])`:
    - A dependency factory that asserts the principal/user has required permissions.
  - `require_roles(roles: list[str])`.

- Migrate existing dependencies:
  - `User_DB_Handling.get_request_user`, `auth_deps.get_current_user`, and any per-endpoint auth dependencies to call `get_auth_principal` or its wrappers.

### Profiles & endpoint gating

- Endpoint availability (e.g., user registration/creation) is governed by deployment profile and configuration as defined in `User-Unification-PRD.md`:
  - In `local-single-user`, additional user creation is forbidden as a hard constraint; routes that create users MUST be disabled or return errors regardless of the caller’s admin status.
  - In `multi-user-postgres`, user-management routes may be enabled and guarded by `require_permissions` / `require_roles`.
- Auth dependencies themselves remain profile-agnostic:
  - They always return an `AuthPrincipal` derived from the current credentials.
  - Profile checks are applied at routing/service level when deciding whether a route should exist or succeed.

### 3. Principal Kinds & Service Tokens

- `AuthPrincipal` includes a `kind` (or `subject_type`) field that describes the principal type, such as:
  - `user` – end-users authenticated via JWT/session.
  - `api_key` – API-key-based access mapped to a user.
  - `service` – internal service tokens or automation identities.
  - `anonymous` – unauthenticated/public access where allowed.
- Dependencies behave as follows:
  - `get_auth_principal` always returns an `AuthPrincipal` with a populated `kind`, and user-centric fields (`user_id`) are only present when applicable (e.g., `user`, `api_key`).
  - `get_current_user` and any user-centric dependencies REQUIRE a principal with user context; if invoked when `kind` is `service` or `anonymous` (or when `user_id` is missing), they MUST block the call with an appropriate 403 error rather than fabricating a user.
  - Future service-specific dependencies (e.g., `require_service_principal`) MAY be introduced for internal endpoints that expect `kind=service`.

### 4. Clean Request-State Usage

- Standardize on:
  - `request.state.auth` as the canonical `AuthContext` (principal + request metadata).
  - `request.state.auth.principal` as the canonical `AuthPrincipal`.
  - `request.state.user_id`, `api_key_id`, `org_ids`, `team_ids` preserved for backwards compatibility but always derived from `request.state.auth.principal`.
- Update middlewares that currently access `request.state` directly:
  - `UsageLoggingMiddleware` uses `request.state.auth` to derive `user_id`, `key_id`, org/team context.
  - `llm_budget_guard` uses `AuthPrincipal` to discover the key and quotas.

- PII and logging:
  - `AuthPrincipal` / `AuthContext` MUST NOT store raw secrets (JWTs, API keys) or other high-sensitivity fields.
  - When logging or emitting metrics from dependencies, use stable, non-PII identifiers (e.g., principal_id, hashed IDs), aligning with `PII_REDACT_LOGS` and `USAGE_LOG_DISABLE_META`.

### 5. Error Semantics (401 vs 403)

- `get_auth_principal`:
  - When credentials are missing or invalid, raises an unauthenticated error that maps to HTTP 401 with appropriate `WWW-Authenticate` headers where applicable.
  - The error payload (status, error code, message) is treated as part of the public API surface and SHOULD remain stable or be explicitly versioned.
- `require_permissions` / `require_roles`:
  - Assume a principal is already present (they depend on `get_auth_principal`); they do not perform their own authn.
  - When the principal lacks required permissions/roles, raise a forbidden error that maps to HTTP 403.
  - The 403 payload SHOULD include which permission(s) or role(s) failed, and that detail structure is considered part of the API surface once shipped.

---

## Scope

### In-Scope (v1)

- Define `AuthPrincipal` and `get_auth_principal` (may share implementation and file with Principal-Governance PRD).
- Update:
  - `permissions.py` to be claim-first and reduce DB lookups.
  - `User_DB_Handling` / `auth_deps` to rely on `get_auth_principal`.
- Introduce `require_permissions` / `require_roles` dependencies and use them in a selection of high-value endpoints (e.g., admin, media management).
- Ensure both deployment profiles (`local-single-user`, `multi-user-postgres`) use the same dependencies and claim semantics:
  - `local-single-user` maps the bootstrapped admin user to an `AuthPrincipal` with admin claims.
  - No dependency re-introduces `is_single_user_mode()` branching for authorization.

### Out of Scope (v1)

- Rewriting all endpoints to use the new dependencies immediately; focus on AuthNZ + a few representative routes.
- Removing all decorators in favor of dependencies; we may continue to support both.

---

## Risks & Mitigations

- **Risk: Stale claims after role/permission changes.**
  - Mitigation:
    - Keep claim TTL aligned with access-token lifetime.
    - For critical operations, optionally re-validate certain claims server-side (e.g., check “still admin”).

- **Risk: Hidden reliance on DB-based checks in existing code.**
  - Mitigation:
    - Instrument or temporarily log when DB fallbacks are used.
    - Add tests to cover key permission/role scenarios.

- **Risk: Test breakage where tests assume direct DB changes immediately affect permissions.**
  - Mitigation:
    - Document that changes take effect on next login/token issue/refresh.
    - Provide test helpers that issue new tokens after RBAC changes.

---

## Milestones & Phasing

### Phase 1: AuthPrincipal + Claim Invariants

- Implement `AuthPrincipal` and `get_auth_principal`.
- Ensure `User_DB_Handling` sets roles/permissions consistently.
- Add tests verifying:
  - A user’s permissions match DB configuration at login time.
  - `user.permissions` and `user.roles` are present and correct for JWT and API-key paths.
  - In the `local-single-user` profile, the bootstrapped admin user (`SINGLE_USER_FIXED_ID`) is represented as an `AuthPrincipal` with admin role and full claims, and no special-case `AUTH_MODE` logic is required in dependencies.
  - `AuthPrincipal.kind` is correctly set for different credential types (`user`, `api_key`, `service`, `anonymous`), and user-centric fields are only present when appropriate.

- **Status (v0.1)**: Done — validated by `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_state_consistency.py` and `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_jwt_happy_path.py`.

### Phase 2: Claim-First Permissions

- Update `permissions.py` to rely on claims first.
- Ensure `is_single_user_mode()` is not used as an “allow-all” shortcut:
  - When `user.permissions` / `user.roles` are present, they are authoritative in both single-user and multi-user profiles (no DB lookup, no mode-based bypass).
  - When claims are absent, `check_permission` / `check_role` fall back to the configured `UserDatabase` for both profiles instead of auto-allowing in single-user mode.
- Add tests covering:
  - Multiple roles and overlapping permissions.
  - User-specific allow/deny overrides.
  - Admin implied permissions.
  - Single-user principals with insufficient claims receiving 403 from `require_permissions` / `require_roles`, matching multi-user semantics.

- **Status (v0.1)**: Done — covered by `tldw_Server_API/tests/AuthNZ_Unit/test_permissions_claim_first.py` and `tldw_Server_API/tests/AuthNZ/integration/test_rbac_admin_endpoints.py`.

### Phase 3: Unified Dependencies & Adoption

- Implement `require_permissions` / `require_roles` dependencies.
- Migrate a set of key endpoints (auth admin, media admin, RAG admin) to use them.
- Update `UsageLoggingMiddleware` and `llm_budget_guard` to use `AuthPrincipal`.
  - Metrics/admin, Resource-Governor admin, and selected chat/Prompt Studio surfaces are part of this adoption and are now **claim-first, tested**:
    - `POST /api/v1/metrics/reset` is gated via `require_roles("admin")` + `require_admin` and covered by HTTP-level permissions tests in `tldw_Server_API/tests/AuthNZ_Unit/test_metrics_permissions_claims.py`.
    - Resource-Governor admin and diagnostics endpoints (`/api/v1/resource-governor/policy*`, `/api/v1/resource-governor/diag/*`) are gated via `get_auth_principal` + `require_roles("admin")`, with behavior validated by `tldw_Server_API/tests/AuthNZ_Unit/test_resource_governor_permissions_claims.py` and the `Resource_Governance` integration suite.
    - Chat slash-command discovery (`GET /api/v1/chat/commands`) now performs RBAC filtering purely via `AuthNZ.rbac.user_has_permission` when `CHAT_COMMANDS_REQUIRE_PERMISSIONS` is enabled, and the async command router enforces per-command permissions without any `is_single_user_mode()` bypass; this is locked in by `tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py` and `tldw_Server_API/tests/Chat_NEW/integration/test_chat_commands_endpoint.py`.
    - Prompt Studio dependencies (`get_prompt_studio_user`) build `user_context.is_admin` and `user_context.permissions` strictly from `User` claims (`roles`, `permissions`, `is_admin`) instead of `AUTH_MODE`; HTTP-level tests in `tldw_Server_API/tests/AuthNZ_Unit/test_prompt_studio_user_claims.py` and `tldw_Server_API/tests/prompt_studio/unit/test_prompt_studio_deps_headers.py` cover claim propagation and 401 behavior.
- Add route-level tests covering:
  - Endpoints that require a user principal, ensuring `get_current_user` / `require_permissions` fail with 403 when invoked with a `service` or `anonymous` principal lacking `user_id`.
  - Service-only endpoints (if any) that rely on `AuthPrincipal.kind=service` without requiring user-centric fields.

- **Status (v0.1)**: In Progress — core admin/chat/Prompt Studio flows are claim-first and tested (see tests cited above), with long-tail endpoint adoption deferred to future iterations.

### Phase 4: Cleanup & Documentation

- Remove or deprecate DB-based permission checks on hot paths.
- Update AuthNZ README and API integration guide to:
  - Document how to use the new dependencies.
  - Provide examples for custom routes.

- **Status (v0.1)**: In Progress — primary guides are updated (see `Docs/Code_Documentation/Guides/AuthNZ_Code_Guide.md` and route-level claim tests in `tldw_Server_API/tests/AuthNZ_Unit/test_auth_claim_route_level.py`); additional documentation and legacy shim cleanup are deferred to future iterations.

---

## Open Questions

- How should we handle cross-service calls where another service presents an internal token—should those produce a “service principal” with its own permissions?
  - No, Services should not present internal tokens across modules. They should pass/rely on the AuthPrincipal, since it is the ultimate source of truth.
- Do we want a formal notion of “scopes” (beyond permissions) for token issuance, or are permissions sufficient?
  - What would the difference be?
- How aggressively should we back-migrate existing endpoints vs. allowing both patterns for a time?
  - Complete migration

---

## Success Criteria

- Most authorization checks in the critical path no longer hit the DB; they use claims on `AuthPrincipal` / `User`.
- There is a single, documented way to get the current authenticated principal/user in FastAPI endpoints.
- Middlewares and services that need auth context rely on `AuthPrincipal` rather than ad-hoc `request.state` fields.

## Verification & Regression Slice

- **Primary test modules relied on (v0.1)**:
  - Permissions and claim-first behavior: `tldw_Server_API/tests/AuthNZ_Unit/test_permissions_claim_first.py`.
  - Metrics admin and AuthNZ claim gates: `tldw_Server_API/tests/AuthNZ_Unit/test_metrics_permissions_claims.py`.
  - Resource-Governor admin/diag claim gates: `tldw_Server_API/tests/AuthNZ_Unit/test_resource_governor_permissions_claims.py` and `tldw_Server_API/tests/Resource_Governance/integration`.
  - Chat slash commands (claim-first routing): `tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py` and `tldw_Server_API/tests/Chat_NEW/integration/test_chat_commands_endpoint.py`.
  - Prompt Studio dependencies and claims: `tldw_Server_API/tests/AuthNZ_Unit/test_prompt_studio_user_claims.py` and `tldw_Server_API/tests/prompt_studio/unit/test_prompt_studio_deps_headers.py`.
- **Recommended regression slice (SQLite/Postgres)**:
  - SQLite-focused slice: `python -m pytest tldw_Server_API/tests/AuthNZ_SQLite -m "not slow"` to exercise AuthNZ SQLite behavior (sessions, rate limits, usage, API keys).
  - Postgres-focused slice: `python -m pytest tldw_Server_API/tests/AuthNZ_Postgres -m "not slow" tldw_Server_API/tests/AuthNZ/integration -m "not slow"` to cover AuthNZ Postgres repos and HTTP-level auth/guardrail flows.

## Implementation Plan

### Stage 1: AuthPrincipal + Claim Invariants
**Goal**: Establish `AuthPrincipal` and `get_auth_principal` as the single source of truth for authenticated identity and claims.

**Success Criteria**:
- `get_auth_principal` is used by core auth dependencies to derive current user context.
- `AuthPrincipal` always carries `roles`, `permissions`, and `is_admin` consistent with RBAC tables at authentication time.

**Tests**:
- Unit tests validating `AuthPrincipal` creation for:
  - JWT access tokens.
  - API keys (regular and virtual).
- Integration tests confirming `User` objects derived from `AuthPrincipal` contain correct roles/permissions.

**Status**: Done

**Notes**:
- `AuthPrincipal` / `AuthContext` are implemented in `tldw_Server_API/app/core/AuthNZ/principal_model.py`, and `get_auth_principal(request)` is implemented in `tldw_Server_API/app/core/AuthNZ/auth_principal_resolver.py` with unit tests for single-user, JWT, and API-key flows.
- Core dependencies (`auth_deps.get_current_user`, `User_DB_Handling.verify_jwt_and_fetch_user` / `get_request_user`) now populate `request.state.auth` / `AuthPrincipal` from their resolved user context and, in multi-user flows, reuse an existing `AuthContext`/`AuthPrincipal` when present instead of re-running JWT/API-key logic, while preserving existing 401/403 semantics.
- Integration coverage includes:
  - `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_state_consistency.py` – single-user API-key flow and 401 semantics for `get_current_user` vs `get_auth_principal`.
  - `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_jwt_happy_path.py` – full multi-user JWT flow (register → login → protected endpoint) asserting that `AuthPrincipal` aligns with `get_current_user` and `request.state` on a real FastAPI app instance.

### Stage 2: Claim-First Permissions
**Goal**: Make runtime permission and role checks rely solely on claims in the common path.

**Success Criteria**:
- `permissions.py` does not hit the DB during typical request processing; it uses `user.permissions` and `user.roles`.
- Any DB fallback logic is either removed or gated behind explicit debug/admin paths.

**Tests**:
- Permission test matrix covering:
  - Multiple role combinations.
  - User-specific allow/deny overrides.
  - Admin implied permissions.

**Status**: Done

**Notes**:
- `permissions.py` now treats `user.permissions` / `user.roles` as authoritative when present, returning False without hitting the DB when claims exist but lack the required permission/role.
- DB-based fallbacks are retained only for caller contexts that do not provide claim lists at all (e.g., legacy user objects without `permissions` / `roles` attributes), reducing database usage on typical, claim-bearing code paths. Additional tests explicitly simulate DB unavailability when claims are present to prove that hot paths remain purely claim-based (`tests/AuthNZ_Unit/test_permissions_claim_first.py::test_check_permission_uses_claims_even_if_db_unavailable` and `::test_check_role_uses_claims_even_if_db_unavailable`).
- Route coverage expanding: admin router now enforces `require_roles("admin")` in addition to legacy `require_admin`, and media ingestion’s `/process-web-scraping` endpoint layers `require_permissions(MEDIA_CREATE)` alongside the legacy `PermissionChecker`. Claim-first `require_permissions` / `require_roles` matrices and HTTP-level admin 401/403 semantics are covered in `tests/AuthNZ_Unit/test_permissions_claim_first.py` and `tests/AuthNZ/integration/test_rbac_admin_endpoints.py::test_admin_roles_require_auth_and_admin`.
- Single-user deployments now use the same claim-first semantics as multi-user for permission and role checks: `permissions.py` no longer treats `is_single_user_mode()` as an “allow-all” fallback when claims are missing. New tests in `tests/AuthNZ_Unit/test_permissions_claim_first.py` (e.g., `test_check_permission_single_user_mode_prefers_claims`, `test_check_permission_single_user_mode_without_claims_falls_back_to_db`, `test_check_role_single_user_mode_treats_admin_as_admin_and_user`, `test_check_role_single_user_mode_without_roles_falls_back_to_db`) assert that single-user admins are governed by claims and DB fallbacks rather than global mode flags.
- API-key authentication now enriches users with roles/permissions from RBAC tables (matching the JWT path) so claim-first checks succeed for X-API-KEY callers on protected routes.
- Usage logging middleware now derives `user_id` / `api_key_id` from `AuthPrincipal` when `request.state.auth` is present, falling back to legacy `request.state` attributes for compatibility, aligning usage metrics with the unified principal model.
- Additional matrix coverage has been added for the “any” / “all” helpers to ensure they also remain claim-first when claims are attached, even if the RBAC DB is unavailable:
  - `tests/AuthNZ_Unit/test_permissions_claim_first.py::test_check_any_permission_uses_claims_even_if_db_unavailable` and `::test_check_all_permissions_uses_claims_even_if_db_unavailable` validate that `check_any_permission` / `check_all_permissions` never call `get_user_database` when `user.permissions` is a list, and instead rely purely on the claim set.

### Stage 3: Unified Dependencies & Adoption
**Goal**: Provide and adopt unified auth dependencies across a set of key endpoints and middlewares.

**Success Criteria**:
- New dependencies (`get_auth_principal`, `get_current_user`, `require_permissions`, `require_roles`) are implemented and documented.
- Representative admin and media/RAG endpoints use `require_permissions` / `require_roles`.
- `UsageLoggingMiddleware` and `llm_budget_guard` derive context from `AuthPrincipal`.

**Tests**:
- Route-level tests ensuring that:
  - Required permissions/roles are enforced correctly.
  - Usage logging and budget guard see the expected principal data.

**Status**: In Progress

**Notes**:
- New claim-first FastAPI dependencies (`get_auth_principal`, `require_permissions`, `require_roles`) are implemented in `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py` with unit tests.
- A representative media endpoint (`/api/v1/media/add`) and an admin endpoint (`/api/v1/metrics/reset`) now also enforce claims using these dependencies alongside their existing auth checks.
- `llm_budget_guard` has been updated to consume `AuthPrincipal` (via `AuthContext` / `request.state.auth`) when consulting governance for LLM virtual-key budgets.
- RAG search endpoints (`/api/v1/rag/search`, `/search/stream`, `/simple`, `/batch`) and media processing (`/api/v1/media/process-videos`, `/api/v1/media/process-web-scraping`, `/api/v1/media/add`) now depend on `require_permissions`, with integration coverage (skipped when Postgres is unavailable) in `tests/AuthNZ/integration/test_rag_media_permissions_claims.py` validating 401/403 semantics for JWT and API-key flows.
- Claim-first route-level semantics are additionally covered by dedicated tests that stub `get_auth_principal` and exercise `require_permissions` / `require_roles` under different principal kinds, including `service` and `anonymous` (`tests/AuthNZ_Unit/test_auth_claim_route_level.py`), ensuring clear 401 vs 403 behavior when principals are missing or lack required claims.
- Notes graph endpoints now adopt `require_permissions` for claim-first enforcement in addition to token scopes: `tldw_Server_API/app/api/v1/endpoints/notes_graph.py` uses `require_permissions(NOTES_GRAPH_READ)` / `require_permissions(NOTES_GRAPH_WRITE)` alongside `require_token_scope("notes", ...)` and rate limiting. Integration coverage is provided by `tldw_Server_API/tests/Notes_NEW/integration/test_notes_graph_rbac.py`, which:
  - Asserts that a virtual key with the wrong `scope` receives 403 for both read (`GET /api/v1/notes/graph`) and write (`POST /api/v1/notes/{note_id}/links`) operations.
  - Asserts that a virtual key with `scope="notes"` and a principal with appropriate graph permissions succeeds (200) for both read and write paths.
- SQLite regression coverage mirrors the claim-first HTTP semantics without Postgres by stubbing RAG/media backends in `tests/AuthNZ_SQLite/test_rag_media_permissions_sqlite.py`.
- Evaluations CRUD and runs endpoints are now wired through claim-first dependencies as a high-value administrative surface. `tldw_Server_API/app/api/v1/endpoints/evaluations_crud.py` imports `require_permissions` and uses dedicated permissions (`EVALS_READ`, `EVALS_MANAGE`) from `tldw_Server_API/app/core/AuthNZ/permissions.py`:
  - Read-oriented routes (`GET /api/v1/evaluations/`, `GET /api/v1/evaluations/{eval_id}`, and list/read run endpoints) depend on `require_permissions(EVALS_READ)` in addition to existing API-key checks.
  - Mutating routes (`POST /api/v1/evaluations/`, `PATCH /api/v1/evaluations/{eval_id}`, `DELETE /api/v1/evaluations/{eval_id}`, `POST /api/v1/evaluations/{eval_id}/runs`, and `POST /api/v1/evaluations/runs/{run_id}/cancel`) depend on `require_permissions(EVALS_MANAGE)` alongside the existing RBAC rate limits and auth helpers.
  - Route-level tests in `tldw_Server_API/tests/AuthNZ/integration/test_evaluations_permissions_claims.py` stub `get_auth_principal`, `verify_api_key`, and `get_request_user` to assert:
    - 403 responses for principals that are authenticated but lack the required `evals.read` / `evals.manage` permissions on list endpoints.
    - 200 responses for principals with appropriate evaluation permissions while the underlying evaluation service is stubbed, ensuring claim-based allow paths behave as expected without touching the real Evaluations DB.
    - The existing `require_admin` helper for heavy evaluations remains the admin gate for `/api/v1/evaluations/admin/idempotency/cleanup`, and the test file documents its behavior as an admin-only compatibility shim independent of the new `require_permissions` wiring on CRUD routes.
- Workflow scheduler admin endpoints now also participate in the unified, claim-first dependency stack:
  - `tldw_Server_API/app/core/AuthNZ/permissions.py` defines `WORKFLOWS_ADMIN = "workflows.admin"` as the canonical permission for scheduler administration.
  - `tldw_Server_API/app/api/v1/endpoints/scheduler_workflows.py::admin_rescan` now depends on both:
    - `require_token_scope("workflows", require_if_present=True, endpoint_id="scheduler.workflows.admin_rescan")` for token-scoped gating, and
    - `require_permissions(WORKFLOWS_ADMIN)` for claim-first enforcement via `AuthPrincipal`.
  - Route-level tests in `tldw_Server_API/tests/AuthNZ_Unit/test_scheduler_workflows_permissions_claims.py` build a small FastAPI app around the scheduler router and stub:
    - `get_auth_principal` to attach an `AuthContext` with different principal kinds (`user`, `service`).
    - `get_request_user` and `require_token_scope` to avoid touching real DB/scope logic.
    - `get_workflows_scheduler` to a fake scheduler that records `_rescan_once` calls.
  - The tests assert that:
    - Non-admin principals without scheduler claims receive 403 for `POST /api/v1/scheduler/workflows/admin/rescan`.
    - User and service principals with `is_admin=True` succeed (200) and trigger the fake scheduler’s rescan call, confirming that admin-style claims (via `is_admin`) remain the primary gate while also flowing through the `require_permissions` / `AuthPrincipal` stack for observability and future fine-grained permissions.
- MCP admin diagnostics are beginning to adopt the same pattern: `tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py::get_modules_health` now depends on `require_permissions(SYSTEM_LOGS)` alongside its module-local admin checks, and route-level tests in `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_admin_permissions_claims.py` exercise 401 vs 403 vs 200 behavior by overriding `get_auth_principal` for different principals.
- Topic monitoring admin endpoints (`/api/v1/monitoring/...`) now also enforce claim-first diagnostics permissions: `tldw_Server_API/app/api/v1/endpoints/monitoring.py` adds `dependencies=[Depends(require_permissions(SYSTEM_LOGS))]` on watchlist/alert/notification routes in addition to `require_admin`. Route-level tests in `tldw_Server_API/tests/AuthNZ_Unit/test_monitoring_permissions_claims.py` cover 401 (no principal), 403 (principal without `system.logs`), and 200 (admin principal) cases while stubbing the underlying monitoring service.
- MCP admin diagnostics are beginning to adopt the same pattern: `tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py::get_modules_health` now depends on `require_permissions(SYSTEM_LOGS)` alongside its module-local admin checks, and route-level tests in `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_admin_permissions_claims.py` exercise 401 vs 403 vs 200 behavior by overriding `get_auth_principal` for different principals.

### Remaining Mode-Based Decisions

- A targeted `is_single_user_mode()` audit confirms that mode checks are now limited to:
  - Coordination/governance (startup banners, WebUI API-key injection for local single-user, ChaChaNotes warm-up, backpressure/tenant RPS toggles, embedding quota defaults).
  - Profile selection for auth flows (single-user API key vs multi-user JWT/API-key) and diagnostics (e.g., MCP single-user API key acceptance), with authorization decisions driven by claims on `AuthPrincipal` / `User`.
- The only auth-adjacent exception is Jobs admin domain-scoped RBAC:
  - `_enforce_domain_scope` in `tldw_Server_API/app/api/v1/endpoints/jobs_admin.py` bypasses domain filters in single-user mode unless `JOBS_RBAC_FORCE=true`, treating single-user as implicitly allowed for domain-scoped jobs operations.
  - For this iteration, this is treated as a deliberate governance exception for single-tenant/local admin deployments; it is documented in `Docs/Design/AuthNZ-Refactor-Implementation-Plan.md` and may be migrated to claim-first (`get_auth_principal` + `require_roles/require_permissions`) in a future phase if domain-scoped jobs RBAC becomes a primary product surface.

### Stage 4: Cleanup & Documentation
**Goal**: Remove legacy, overlapping auth dependencies and update documentation.

**Success Criteria**:
- Deprecated or redundant auth dependencies are either removed or clearly marked.
- AuthNZ README and integration guide contain examples using the unified dependencies.

**Tests**:
- Documentation lint/checks where applicable, plus smoke tests for routes updated to the new dependencies.

**Status**: In Progress

**Notes**:
- `Docs/Code_Documentation/Guides/AuthNZ_Code_Guide.md` explicitly documents the split between modern claim-first dependencies and legacy compatibility shims:
  - Modern pattern:
    - `get_auth_principal` → returns `AuthPrincipal` with roles/permissions.
    - `require_permissions` / `require_roles` → enforce claims and return the principal; representative usage is called out for media, RAG, notes graph, evaluations CRUD, scheduler workflows admin, and chat queue diagnostics (`system.logs`).
  - Legacy shims:
    - `PermissionChecker`, `RoleChecker`, `AnyPermissionChecker`, `AllPermissionsChecker` in `permissions.py` are described as maintained for existing routes but not recommended for new endpoints.
    - `require_admin` in evaluations auth is documented as an admin-only gate for heavy evaluations flows, while new admin surfaces should prefer `get_auth_principal` plus `require_permissions` / `require_roles`.
- The code guide now includes a short “securing a new route” example that shows:
  - Defining a permission constant in `permissions.py`.
  - Applying `Depends(require_permissions("your.permission"))` to an endpoint.
  - Overriding `get_auth_principal` in tests to exercise 401 vs 403 semantics, reusing patterns from `tests/AuthNZ_Unit/test_auth_claim_route_level.py` and `tests/AuthNZ_Unit/test_scheduler_workflows_permissions_claims.py`.
- Selected RBAC helpers now use `AuthnzRbacRepo`, and the admin `GET /api/v1/admin/roles/{role_id}/permissions/effective` endpoint delegates to `AuthnzRbacRepo.get_role_effective_permissions`, with behavior locked in by SQLite and Postgres-backed admin endpoint tests.
