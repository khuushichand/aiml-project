# AuthNZ Refactor Implementation Plan

This plan coordinates the implementation of the three AuthNZ PRDs:

- `Docs/Product/Principal-Governance-PRD.md`
- `Docs/Product/User-Unification-PRD.md`
- `Docs/Product/User-Auth-Deps-PRD.md`

The stages are designed to be incremental and backwards-compatible. Each stage should result in a compilable, test-passing system with a clear, testable outcome.

---

## Stage 0: Invariants & Guardrails

**Goal**: Capture current AuthNZ behavior (especially dependencies and error semantics) so later refactors can be safely validated against it.

**Success Criteria**:
- Smoke tests exist for:
  - `auth_deps.get_current_user` (single-user, multi-user JWT, API key).
  - `User_DB_Handling.get_request_user` (single-user and multi-user).
- Tests assert:
  - 401 vs 403 behavior and basic error payload shapes for common failure modes.
  - `request.state.user_id` and `request.state.api_key_id` are set as they are today for representative endpoints.
- A small helper (or doc comment) exists that documents the intended 401/403 semantics for AuthNZ dependencies.

**Tests**:
- New `pytest` module(s) under `tldw_Server_API/tests/AuthNZ/` (or similar) that:
  - Exercise `auth_deps.get_current_user` and `User_DB_Handling.get_request_user` in both single and multi-user configurations.
  - Assert on HTTP status codes and key headers (`WWW-Authenticate`, test-only diagnostics headers).

**PRDs Touched**:
- Used for reference only; no edits expected in this stage.

**Status**: In Progress

**Notes**:
- Initial invariant tests exist in `tldw_Server_API/tests/AuthNZ_Unit/test_authnz_invariants.py` to assert 401 behavior and headers for missing-credential cases in `auth_deps.get_current_user` and `User_DB_Handling.get_request_user`, as well as successful single-user API-key auth wiring `request.state.user_id`.
%- Broader integration coverage (multi-user JWT/API-key flows across backends) remains future work and will build on existing AuthNZ integration suites.

---

## Stage 1: Principal Skeleton & Compatibility Facades

**Goal**: Introduce `AuthPrincipal` / `AuthContext` and `get_auth_principal`, and have existing dependencies (`auth_deps`, `User_DB_Handling`) call into it internally while preserving external behavior.

**Success Criteria**:
- A shared `AuthPrincipal` model and `AuthContext` type exist (e.g., in `app/core/AuthNZ/principal_model.py`), including:
  - `kind` (user, api_key, service, anonymous).
  - `principal_id` (stable, non-PII identifier).
  - `user_id`/`api_key_id` (when applicable).
  - `roles`, `permissions`, `is_admin`.
- `get_auth_principal(request)`:
  - Is implemented once and used as the **single source of truth** for identity + claims.
  - Handles credential detection (Bearer, `X-API-KEY`, single-user key) using existing JWTService, APIKeyManager, SessionManager.
- `request.state.auth` is populated as an `AuthContext` on authenticated routes, and:
  - `request.state.user_id` / `api_key_id` / `org_ids` / `team_ids` are mirrored from `AuthContext.principal` for backwards compatibility.
- `auth_deps.get_current_user` and `User_DB_Handling.get_request_user`:
  - Are refactored to internally call `get_auth_principal` and then map `AuthPrincipal` to their current return shapes (dict / `User`).
  - Maintain existing 401/403 behavior and external signatures.

**Tests**:
- Unit tests for `get_auth_principal` covering:
  - Single-user API key.
  - Multi-user JWT (access tokens).
  - User-bound API key and virtual key.
- Integration tests asserting, for representative endpoints:
  - `request.state.auth` is set and contains a populated `AuthPrincipal`.
  - `request.state.user_id` and `request.state.api_key_id` match previous behavior.
  - Existing tests for `auth_deps.get_current_user` and `User_DB_Handling.get_request_user` pass without modification.

**PRDs Touched**:
- Principal-Governance:
  - Stage 1: Principal Skeleton (AuthContext).
- User-Auth-Deps:
  - Stage 1: AuthPrincipal + Claim Invariants.

**Status**: In Progress

**Notes**:
- `AuthPrincipal` / `AuthContext` implemented in `tldw_Server_API/app/core/AuthNZ/principal_model.py` with unit tests.
- `get_auth_principal(request)` implemented in `tldw_Server_API/app/core/AuthNZ/auth_principal_resolver.py` with unit tests covering single-user, JWT, and API-key flows.
- `auth_deps.get_current_user` and `User_DB_Handling.verify_jwt_and_fetch_user` / `get_request_user` now populate `request.state.auth` from their resolved user context; delegation of identity derivation to `get_auth_principal` is still pending (PR 4).

### Stage 1 – Suggested PR Breakdown

To keep Stage 1 incremental and reviewable, implement it as four focused PRs:

1. **PR 1: Introduce `AuthPrincipal` / `AuthContext` Types**
   - Add `AuthPrincipal` and `AuthContext` models in a new module (e.g., `principal_model.py`).
   - Implement a helper for computing a stable, non-PII `principal_id`.
   - Add unit tests for model construction and `principal_id` behavior.
   - Do not wire these types into existing code yet.

2. **PR 2: Implement `get_auth_principal` (Internal-Only)**
   - Add `get_auth_principal(request)` in a new resolver module.
   - Use existing JWTService, APIKeyManager, SessionManager, and single-user settings to build an `AuthPrincipal`.
   - Cover success and failure cases with unit tests.
   - Do not call `get_auth_principal` from `auth_deps` or `User_DB_Handling` yet.

3. **PR 3: Attach `AuthContext` via `auth_deps.get_current_user`**
   - After existing logic in `auth_deps.get_current_user`, construct an `AuthPrincipal`/`AuthContext` from the resolved user data.
   - Set `request.state.auth = AuthContext` and mirror `request.state.user_id/api_key_id/org_ids/team_ids` from the principal.
   - Add/extend tests to assert `request.state.auth` is present and consistent with legacy `request.state` fields.
   - Do not change how identity is derived yet.

4. **PR 4: Delegate `auth_deps` and `User_DB_Handling` to `get_auth_principal`**
   - Refactor `auth_deps.get_current_user` to call `get_auth_principal` and map the result to its current dict shape while preserving 401/403 behavior and headers.
   - Refactor `User_DB_Handling.get_request_user` to call `get_auth_principal` and map the result to the existing `User` Pydantic model.
   - Ensure `request.state` fields are set from `AuthContext` and that all existing tests (including Stage 0 invariants) continue to pass.

---

## Stage 2: Single-User Bootstrap & Profiles

**Goal**: Make single-user a bootstrap profile of multi-user by seeding a real admin user and primary API key, and route single-user auth through the same core flows (`get_auth_principal`) instead of synthetic code paths.

**Success Criteria**:
- A bootstrap routine exists (e.g., `AuthNZ.initialize_single_user_profile`) that:
  - Ensures a user with `SINGLE_USER_FIXED_ID` and username `single_user` exists in `users`.
  - Ensures a primary API key exists for that user:
    - If `SINGLE_USER_API_KEY` is set, the bootstrapped key matches it (hash/persist vs re-generating).
    - If no key is set, a new one is generated and surfaced according to configuration.
  - Ensures the bootstrapped user has admin role/permissions via RBAC tables.
- Bootstrap is idempotent:
  - Re-running it does not create duplicate users or keys.
  - Mixed/invalid states (e.g., multiple active admin users or primary keys) are detected and reported clearly.
- `get_auth_principal`:
  - Uses the bootstrapped user + API key in `local-single-user` profile.
  - No longer relies on synthetic, hard-coded single-user user objects in its own logic.
- Existing single-user dependencies (`auth_deps.get_current_user`, `User_DB_Handling.get_request_user`, `verify_single_user_api_key`) behave the same externally but are **internally** mapped to the bootstrapped user and key via `get_auth_principal`.

**Tests**:
- Migration tests for legacy single-user deployments:
  - Seed DB with legacy single-user setup and `SINGLE_USER_API_KEY`.
  - Run bootstrap and assert:
    - Admin user and primary key exist and match expectations.
    - RBAC rows for admin are present.
  - Re-run bootstrap and confirm no further changes.
- Auth tests:
  - For `AUTH_MODE=single_user` / `local-single-user`:
    - Auth via `X-API-KEY` and Bearer flows still work and return the same user shape.
    - `AuthPrincipal.kind` is `api_key` and `is_admin=True` for the bootstrapped admin.

**PRDs Touched**:
- User-Unification:
  - Stage 1: Single-User Bootstrap.
  - Stage 2: Claims-Based Single-User Permissions.
- Principal-Governance:
  - Stage 1 (single-user principal semantics).
- User-Auth-Deps:
  - Stage 1 (local-single-user profile mapping to `AuthPrincipal`).

**Status**: Not Started

---

## Stage 3: AuthNZ Repositories & Backend Unification

**Goal**: Hide SQLite vs Postgres differences behind a small set of AuthNZ repositories (users, API keys, RBAC) so identity and claims can rely on them without scattering SQL across the codebase.

**Success Criteria**:
- Repositories are implemented:
  - `AuthnzUsersRepo` (users).
  - `AuthnzApiKeysRepo` (API keys).
  - `AuthnzRbacRepo` (roles, permissions, user overrides).
  - All use `DatabasePool` and encapsulate SQL/dialect differences.
- DDL for API-key- and AuthNZ-related tables is centralized in migrations / repository initialization helpers.
- `APIKeyManager` and relevant user/RBAC helpers:
  - Use repositories for DB access instead of inline SQL.
- `get_auth_principal`:
  - Pulls user and RBAC claims via repositories, not ad-hoc SQL.
- Business logic modules (including `auth_deps` and `User_DB_Handling`) do **not** perform direct Postgres/SQLite branching for these tables.

**Tests**:
- Unit tests for repositories against both backends (SQLite, Postgres):
  - Creation, lookup, update, revocation, and error handling (e.g., uniqueness violations).
- Regression tests:
  - Existing auth tests pass unchanged under both SQLite and Postgres configurations.
  - Any new tests for `get_auth_principal` run against both backends via fixtures.

**PRDs Touched**:
- User-Unification:
  - Stage 3: Repository Introduction.
  - Stage 4: Backend Drift Reduction (initial modules).
- Principal-Governance:
  - Underpins principal creation via repositories.

**Status**: Not Started

---

## Stage 4: Claim-First Dependencies & AuthContext Adoption

**Goal**: Make runtime authorization checks claim-first and introduce the new dependency stack (`get_auth_principal`, `get_current_user`, `require_permissions`, `require_roles`) across selected endpoints and middlewares.

**Success Criteria**:
- `permissions.py`:
  - Uses claims on `AuthPrincipal`/`User` (`roles`, `permissions`, `is_admin`) for runtime checks.
  - Removes or gates DB fallbacks behind explicit debug/admin paths.
- New FastAPI dependencies are implemented and documented:
  - `get_auth_principal(request) -> AuthPrincipal`.
  - `get_current_user(principal: AuthPrincipal) -> User` wrapper.
  - `require_permissions`, `require_roles` with well-defined 401/403 semantics and stable error payload shapes.
- Selected endpoints are migrated to the new dependencies:
  - A subset of admin and media/RAG endpoints use `require_permissions` / `require_roles`.
  - Behavior is preserved or intentionally tightened, with tests updated accordingly.
- Middlewares (`UsageLoggingMiddleware`, `llm_budget_guard`) rely on `request.state.auth` / `AuthPrincipal` rather than ad-hoc `request.state.user_id/api_key_id`.
- Existing dependencies (`auth_deps.get_current_user`, `User_DB_Handling.get_request_user`) are thinner:
  - Primarily wrappers around `get_auth_principal`.

**Tests**:
- Permission matrix tests for `permissions.py`:
  - Multiple role combinations.
  - User-specific allow/deny overrides.
  - Admin implied permissions.
- Route-level tests:
  - Endpoints guarded by `require_permissions` / `require_roles` enforce claims correctly.
  - Behavior for unauthorized vs unauthenticated callers matches documented 401/403 semantics.
- Middleware tests:
  - Usage logging and LLM budget guard see expected principal data via `request.state.auth`.

**PRDs Touched**:
- User-Auth-Deps:
  - Stage 2: Claim-First Permissions.
  - Stage 3: Unified Dependencies & Adoption.
- Principal-Governance:
  - G1: Unified Principal Model (dependencies now use it).

**Status**: In Progress

**Notes**:
- New FastAPI dependencies `get_auth_principal`, `require_permissions`, and `require_roles` are implemented in `API_Deps/auth_deps.py` with unit tests.
- Representative media (`/media/add`) and admin (`/metrics/reset`) endpoints now also enforce claims via `require_permissions` / `require_roles` alongside existing dependencies.
- `llm_budget_guard` has been updated to derive an `AuthPrincipal` (via `request.state.auth` when available) and now uses that principal when consulting governance for LLM budgets.

---

## Stage 5: Governance & Guardrail Consolidation

**Goal**: Route all AuthNZ guardrails (LLM budgets, login lockouts, AuthNZ-level rate limits) through `AuthGovernor` / `ResourceGovernor` using `AuthPrincipal`, and remove duplicated guardrail logic.

**Success Criteria**:
- `AuthGovernor` is implemented as an AuthNZ-focused façade over `ResourceGovernor` with support for:
  - Rate limits (requests/minute, burst).
  - LLM budgets (tokens/day, tokens/month, USD/day, USD/month).
  - Login lockouts and suspicious-activity metrics.
- `llm_budget_guard`, login lockouts, and AuthNZ-level rate limiting:
  - Use `AuthGovernor.check_and_increment(AuthPrincipal, metric, window, amount)` instead of custom per-module logic.
  - Have clearly documented semantics (atomicity, error behavior, idempotency) as specified in the Principal-Governance PRD.
- Guardrail storage:
  - Is accessed only through `AuthGovernor` and its repositories.
  - Does not rely on in-process-only counters for enforcement; any caching is best-effort and backed by shared Redis/DB.
- Legacy guardrail SQL and scattered counters are removed or left only as compatibility/reporting layers.

**Tests**:
- Unit tests for `AuthGovernor`:
  - Budget and rate-limit metrics with different windows and principals.
  - Lockout thresholds and state transitions.
- API-level tests:
  - Over-budget and over-limit scenarios return the expected 402/429 responses with structured detail.
  - Login lockouts behave as before for both SQLite and Postgres.
- Static/code-level checks:
  - No remaining direct SQL manipulation of guardrail tables from outside the governance layer.

**PRDs Touched**:
- Principal-Governance:
  - Stage 2: LLM Budgets via AuthGovernor.
  - Stage 3: Login Lockouts via AuthGovernor.
  - Stage 4: Consolidation & Clean-up.
- User-Auth-Deps:
  - Middleware adoption of `AuthPrincipal` for guardrails.

**Status**: In Progress

**Notes**:
- A minimal `AuthGovernor` facade for LLM budgets is implemented in `tldw_Server_API/app/core/AuthNZ/auth_governor.py`, decorating `is_key_over_budget` with principal metadata.
- `llm_budget_guard.enforce_llm_budget` now calls `AuthGovernor.check_llm_budget_for_api_key` using an `AuthPrincipal` (from `AuthContext` or derived from `request.state`) and preserves existing 402 response semantics while adding structured principal details.
- Rate-limit and login-lockout paths are not yet routed through `AuthGovernor`; they remain TODO for later stages.
