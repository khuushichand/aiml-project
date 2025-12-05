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

**AuthNZ 401 vs 403 Semantics (Reference)**:
- `get_auth_principal`:
  - Returns `AuthPrincipal` when credentials are valid.
  - Raises **401 Unauthorized** when credentials are missing or invalid, with a stable detail string:
    - Multi-user: `"Not authenticated (provide Bearer token or X-API-KEY)"` for missing credentials.
    - Single-user: `"Could not validate credentials"` when principal resolution fails.
- `get_current_user`:
  - Returns a user-shaped dict when credentials are valid.
  - Raises **401 Unauthorized** when credentials are missing or invalid, with:
    - Detail containing `"Authentication required"` for missing credentials.
    - `WWW-Authenticate: Bearer` header.
- `require_permissions` / `require_roles`:
  - Depend on `get_auth_principal` and therefore propagate its **401** behavior when no principal is present.
  - When a principal is present but lacks required claims, they raise **403 Forbidden**:
    - `require_permissions` uses detail `"Permission denied. Required: <perm-list>"`.
    - `require_roles` uses detail `"Access denied. Required role(s): <role-list>"`.
  - These 403 payloads are considered part of the public API surface for admin/claim-first routes once shipped.

**PRDs Touched**:
- Used for reference only; no edits expected in this stage.

**Status**: Done

**Notes**:
- Unit-level invariant tests in `tldw_Server_API/tests/AuthNZ_Unit/test_authnz_invariants.py` capture 401 behavior, headers, and request-state wiring for `auth_deps.get_current_user` and `User_DB_Handling.get_request_user` in both single-user and multi-user configurations.
- Integration tests exercise principal/state alignment for real FastAPI routes in multi-user mode:
  - `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_jwt_happy_path.py` and `test_auth_principal_api_key_happy_path.py` assert that `request.state.user_id` / `request.state.api_key_id` and `request.state.auth.principal` stay in sync with `AuthPrincipal` across JWT and API-key flows.
  - `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_media_rag_invariants.py` extends these invariants to representative business endpoints (`/api/v1/rag/search` for JWT, `/api/v1/media/process-videos` for API keys), ensuring `request.state.*` mirrors `AuthPrincipal` in real application routes.
- The intended 401 vs 403 semantics for `get_auth_principal`, `get_current_user`, `require_permissions`, and `require_roles` are documented in `Docs/Code_Documentation/Guides/AuthNZ_Code_Guide.md` (see “HTTP status semantics (AuthNZ dependencies)”) and are treated as part of the stable compatibility surface.

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

**Status**: Done

**Notes**:
- `AuthPrincipal` / `AuthContext` implemented in `tldw_Server_API/app/core/AuthNZ/principal_model.py` with unit tests.
- `get_auth_principal(request)` implemented in `tldw_Server_API/app/core/AuthNZ/auth_principal_resolver.py` with unit tests covering single-user, JWT, and API-key flows.
- `User_DB_Handling.authenticate_api_key_user` centralizes multi-user API key authentication and is reused by both `get_request_user` and `get_auth_principal`.
- `auth_deps.get_current_user` and `User_DB_Handling.get_request_user` populate `request.state.auth` / `request.state._auth_user` and, in multi-user flows, reuse an existing `AuthContext`/`AuthPrincipal` when present instead of re-running JWT/API-key logic, while preserving existing 401/403 semantics.
- Integration coverage added in `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_state_consistency.py` to assert that `request.state.auth.principal` stays aligned with `request.state.user_id` and that 401 behaviors for `get_current_user` vs `get_auth_principal` remain stable.
- Budget guard/middleware paths now reuse `AuthPrincipal`/`AuthContext` and carry principal metadata in 402 responses; regression coverage lives in `tests/AuthNZ/integration/test_auth_principal_jwt_happy_path.py`, `tests/AuthNZ/integration/test_llm_budget_guard_http.py`, and `tests/AuthNZ_SQLite/test_llm_budget_402_sqlite.py`.

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

**Status**: Done

**Status details & notes**:
- `bootstrap_single_user_profile` is implemented in `tldw_Server_API/app/core/AuthNZ/initialize.py` and exercised by SQLite/Postgres integration tests:
  - `tldw_Server_API/tests/AuthNZ_SQLite/test_single_user_bootstrap_sqlite.py`
  - `tldw_Server_API/tests/AuthNZ_Postgres/test_single_user_bootstrap_postgres.py`
- Claim-first semantics for single-user principals are locked in by:
  - `tldw_Server_API/tests/AuthNZ_Unit/test_permissions_claim_first.py` (e.g., `test_check_permission_single_user_mode_prefers_claims`, `test_check_role_single_user_mode_treats_admin_as_admin_and_user`).
  - `tldw_Server_API/tests/AuthNZ/integration/test_single_user_claims_permissions.py`, which verifies both:
    - The bootstrapped single-user admin has concrete roles/permissions claims and passes `require_permissions` / `require_roles`.
    - A non-admin single-user principal (overridden via `get_auth_principal`) is correctly denied on permission- and role-protected endpoints (403).
- The AuthNZ Code Guide documents single-user behavior and explicitly notes that claim-first dependencies respect single-user claims, with these tests referenced as invariants.

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

**Status**: Done

**Notes**:
- Core repositories are implemented and exercised in tests:
  - `AuthnzUsersRepo` and `AuthnzApiKeysRepo` (with SQLite + Postgres coverage).
  - `AuthnzRbacRepo` for roles/permissions.
  - New repos introduced for this stage:
    - `AuthnzOrgsTeamsRepo` encapsulates organizations, teams, and membership (including default-team helpers).
    - `AuthnzUsageRepo` centralizes `llm_usage_log`, `usage_log`, `usage_daily`, and `llm_usage_daily` aggregates and pruning, and is wired into `virtual_keys` and the AuthNZ scheduler.
    - `AuthnzRateLimitsRepo` owns all DB-backed rate-limiter tables (`rate_limits`, `failed_attempts`, `account_lockouts`) and is used by `rate_limiter.RateLimiter` for cleanup, per-window counters, failed-attempt tracking, and lockouts.
- Business logic modules that previously embedded dialect-specific SQL for these tables now delegate to repositories:
  - `virtual_keys.py` uses `AuthnzApiKeysRepo` and `AuthnzUsageRepo` for key limits and usage summaries.
  - `orgs_teams.py` is thin orchestration over `AuthnzOrgsTeamsRepo` for org creation, teams, and membership, with no direct SQL.
  - `rate_limiter.py` delegates `rate_limits` upserts, reads, failed-attempt accounting, lockout checks, and DB cleanup to `AuthnzRateLimitsRepo`.
  - `scheduler.py` uses `AuthnzUsageRepo` for usage/LLM-usage pruning instead of inline `usage_log`/`llm_usage_*` SQL.
  - `monitoring.py` and the AuthNZ scheduler now use `AuthnzMonitoringRepo` for audit-log metrics, pruning, and dashboard aggregates; SQLite and Postgres behavior is covered by dedicated repo tests.
- Remaining inline SQL in AuthNZ touching users and selected bootstrap/monitoring paths (e.g., parts of `initialize`/`monitoring`) is explicitly out-of-scope for this phase and will be migrated in later iterations as tests and PRDs for those areas are extended. A focused audit of `hasattr(conn, 'fetch*')` branches confirms the remaining clusters:
  - **Sessions**: core session creation, validation, refresh, listing, and cleanup now go through `AuthnzSessionsRepo`. The revoke-all-tokens flow in `token_blacklist.TokenBlacklist.revoke_all_user_tokens` now uses `AuthnzSessionsRepo` for both session metadata reads and revocation updates, removing the last direct `sessions`-table SQL from AuthNZ business logic; only the legacy SQLite session-column harmonization helper remains in `token_blacklist.py`.
  - **Token blacklist**: `AuthnzTokenBlacklistRepo` (`repos/token_blacklist_repo.py`) now owns the `token_blacklist` table for inserts, active-expiry lookups, cleanup, and statistics, and `token_blacklist.TokenBlacklist` delegates those operations to the repo. Table-creation DDL and the SQLite session-column harmonization helper remain in `token_blacklist.py` for backwards compatibility and are explicitly out-of-scope for Stage 3/4.
  - **MFA**: `mfa_service.py` now delegates all MFA persistence on the `users` table (TOTP secret, two-factor flags, backup_codes, status rows, and regeneration/consumption updates) to `AuthnzMfaRepo` (`repos/mfa_repo.py`), while retaining the existing `MFAService` encryption, key-rotation logic, and TOTP/backup-code hashing behavior.
  - **Registration codes**: the AuthNZ scheduler’s expired-registration cleanup now uses `AuthnzRegistrationCodesRepo` (`repos/registration_codes_repo.py`) for the `registration_codes` table, removing the last scheduler-owned inline SQL for that table while preserving the existing retention semantics.
  - **API key manager / initialize**: `api_key_manager.py` and parts of `initialize.py` use limited inline SQL for bootstrap and schema backstops. Runtime SQL in `api_key_manager` for usage counters, expiry, and audit logging has now been migrated into `AuthnzApiKeysRepo` (`increment_usage`, `mark_key_expired`, `insert_audit_log`), and the manager calls those helpers instead of executing its own queries. Bootstrap-only PostgreSQL DDL for usage tables (`usage_log`, `usage_daily`, `llm_usage_log`, `llm_usage_daily`) and the `vk_*_counters` tables has been moved out of `initialize.py` into `pg_migrations_extra.py` (`ensure_usage_tables_pg`, `ensure_virtual_key_counters_pg`) and is invoked from both the AuthNZ initializer and FastAPI startup for Postgres backends. These helpers remain **bootstrap guardrails** (safe, idempotent DDL for environments that have not run migrations), while SQLite continues to rely on the canonical migrations (`migration_013`, `migration_015`, `migration_018`, `migration_023`).

### Repo Coverage Table (AuthNZ core tables)

The table below summarizes how core AuthNZ tables are covered by repositories as of this refactor stage. “Full” means all runtime read/write paths are repo-backed and remaining inline SQL is confined to migrations/bootstrap; “Partial” means there is still runtime inline SQL in addition to repo usage.

| Table / Concern                                      | Primary repo                | Coverage                                                                 | Notes |
|------------------------------------------------------|-----------------------------|--------------------------------------------------------------------------|-------|
| Users (`users`)                                      | `AuthnzUsersRepo`           | Full – runtime via repo; inline SQL only in migrations/bootstrap         | User lookups and listing go through `AuthnzUsersRepo`/`UsersDB`; remaining inline SQL lives in `initialize.py` and migration helpers. |
| API keys (`api_keys`, `api_key_audit_log`)           | `AuthnzApiKeysRepo`         | Full – runtime via repo; inline SQL only in migrations/bootstrap         | `APIKeyManager` uses `AuthnzApiKeysRepo` for validation, listing, primary-key upsert, creation (regular and virtual keys), rotation/revocation, usage counters, and audit-log inserts. Inline SQL remains only for table creation/backstops and migration helpers. |
| RBAC (`roles`, `permissions`, `role_permissions`, `user_roles`, `user_permissions`, `rbac_*_rate_limits`) | `AuthnzRbacRepo`           | Full – runtime via repo; inline SQL only in migrations/bootstrap         | RBAC checks and effective-permissions queries use `AuthnzRbacRepo`; schema creation and seed data remain in `initialize.py`/migrations. |
| Orgs/teams (`organizations`, `org_members`, `teams`, `team_members`) | `AuthnzOrgsTeamsRepo`      | Full – runtime via repo; inline SQL only in migrations/bootstrap         | `orgs_teams.py` is orchestration over `AuthnzOrgsTeamsRepo`; DDL and initial seeds are handled in `initialize.py`/migrations. |
| Usage / LLM usage (`usage_log`, `usage_daily`, `llm_usage_log`, `llm_usage_daily`) | `AuthnzUsageRepo`         | Full – runtime via repo; inline SQL only in migrations/tests/bootstrap   | Aggregation, pruning, and per-request usage inserts use `AuthnzUsageRepo`; inline SQL remains only in migrations, initialization helpers, and test fixtures. |
| Rate limits (`rate_limits`)                          | `AuthnzRateLimitsRepo`      | Full – runtime via repo; inline SQL only in migrations/bootstrap         | `rate_limiter.RateLimiter` uses the repo for counters and cleanup; DDL is centralized in migrations. |
| Lockouts (`failed_attempts`, `account_lockouts`)     | `AuthnzRateLimitsRepo`      | Full – runtime via repo; inline SQL only in migrations/bootstrap         | Login lockout and failed-attempt accounting go through `AuthnzRateLimitsRepo`; only migrations define schema. |
| Sessions (`sessions`)                                | `AuthnzSessionsRepo`        | Full – runtime via repo; inline SQL only in migrations/bootstrap         | Session create/refresh/validate/list/cleanup are repo-backed; `initialize.py` contains bootstrap DDL and token-blacklist harmonization helpers. |
| Token blacklist (`token_blacklist`)                  | `AuthnzTokenBlacklistRepo`  | Full – runtime via repo; inline SQL only in migrations/bootstrap         | All blacklist CRUD/cleanup/statistics use the repo; DDL and a SQLite harmonization helper live in `token_blacklist.py`/migrations. |
| MFA (`users` MFA columns / MFA tables)               | `AuthnzMfaRepo`             | Full – runtime via repo; inline SQL only in migrations/bootstrap         | `mfa_service.py` delegates MFA persistence to `AuthnzMfaRepo`; schema changes are handled by migrations. |
| Monitoring / AuthNZ metrics (monitoring tables)      | `AuthnzMonitoringRepo`      | Full – runtime via repo; inline SQL only in migrations/bootstrap         | Monitoring/audit metrics and pruning use `AuthnzMonitoringRepo`; table creation is migration-driven. |
| Registration codes (`registration_codes`)            | `AuthnzRegistrationCodesRepo` | Full – runtime via repo; inline SQL only in migrations/bootstrap       | Scheduler cleanup and registration-code lookups are repo-backed; DDL lives in `initialize.py`/migrations. |

### Inline SQL audit (hasattr(conn, 'fetch*') clusters)

An explicit audit of `hasattr(conn, 'fetch*')` usage in `tldw_Server_API/app/core/AuthNZ` shows:

- `api_key_manager.py` – **bootstrap/maintenance inline SQL only**  
  - Uses backend-branching (`if hasattr(conn, 'fetchval')` / `fetchrow`) for:
    - `_create_tables` DDL for `api_keys` / `api_key_audit_log` (bootstrap/backstop only).
    - `cleanup_expired_keys`, which performs a periodic maintenance update for expired keys.  
  - All request-time operations now delegate to `AuthnzApiKeysRepo` helpers:
    - `create_api_key_row`, `create_virtual_key_row`, `mark_rotated`, and `revoke_api_key_for_user` for create/rotate/revoke flows.
    - `increment_usage`, `mark_key_expired`, and `insert_audit_log` for usage counters, status transitions, and audit logging.  
  - Remaining inline SQL is explicitly treated as **bootstrap/maintenance guardrails** for v0.1 and may be migrated into migrations or repo helpers in a later iteration once operational requirements are fully captured.

- `rate_limiter.py` – **rate-limiter DDL guardrails + repo-backed runtime**  
  - `_ensure_sqlite_schema` / `_ensure_postgres_schema` contain minimal DDL for `rate_limits`, `failed_attempts`, and `account_lockouts` to backstop environments that have not yet applied migrations. These helpers are invoked from `RateLimiter.initialize()` and are treated as bootstrap-only guardrails; canonical schema remains migration-driven (`migration_005_create_rate_limits_table` and related helpers).
  - All runtime reads/writes for `rate_limits`, `failed_attempts`, and `account_lockouts` (including lockout accounting and per-window increments) are delegated to `AuthnzRateLimitsRepo`.
  - The AuthNZ scheduler’s `_monitor_rate_limits` job now uses `AuthnzRateLimitsRepo.list_recent_violations` to surface aggregated rate-limit violations instead of embedding its own SQL, so rate-limit monitoring remains dialect-agnostic and repo-backed.

- `initialize.py` – **bootstrap/DDL inline SQL (bootstrap only, partially consolidated)**  
  - Uses backend-branching DDL to ensure presence of `audit_logs`, `sessions`, `registration_codes`, RBAC tables, and organizations/teams in non-SQLite deployments.  
  - PostgreSQL DDL for usage tables (`usage_log`, `usage_daily`, `llm_usage_log`, `llm_usage_daily`) and virtual-key counters has been moved into `pg_migrations_extra.py` and is exercised via `ensure_usage_tables_pg` / `ensure_virtual_key_counters_pg`, which are called from both `initialize.setup_database` and FastAPI startup when a Postgres pool is present.  
  - Remaining inline SQL in `initialize.py` is explicitly treated as **bootstrap-only** for v0.1; it runs during explicit initialization to ensure core AuthNZ schemas are present but is not used on hot paths. Any new AuthNZ tables must be added via migrations or repo-backed helpers rather than new inline DDL here.

MFA-related SQL has already been migrated behind `AuthnzMfaRepo`; no `hasattr(conn, 'fetch*')` MFA cluster remains in runtime paths.

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
  - Metrics/admin and Resource-Governor admin surfaces are fully claim-first and covered by HTTP-level claim tests:
    - `POST /api/v1/metrics/reset` – `tldw_Server_API/tests/AuthNZ_Unit/test_metrics_permissions_claims.py`.
    - `/api/v1/resource-governor/policy*`, `/api/v1/resource-governor/diag/*` – `tldw_Server_API/tests/AuthNZ_Unit/test_resource_governor_permissions_claims.py` plus the existing `Resource_Governance` integration tests.
- Middleware tests:
  - Usage logging and LLM budget guard see expected principal data via `request.state.auth`.

**PRDs Touched**:
- User-Auth-Deps:
  - Stage 2: Claim-First Permissions.
  - Stage 3: Unified Dependencies & Adoption.
- Principal-Governance:
  - G1: Unified Principal Model (dependencies now use it).
- Resource-Governor:
  - Admin policy and diagnostics endpoints are claim-first and wired via `get_auth_principal` + `require_roles("admin")`, with HTTP-level tests covering 401/403/200 semantics for `/api/v1/resource-governor/policy*` and `/api/v1/resource-governor/diag/*`.

**Status**: In Progress

**Notes**:
- New FastAPI dependencies `get_auth_principal`, `require_permissions`, and `require_roles` are implemented in `API_Deps/auth_deps.py` with unit tests.
- Representative media (`/media/add`, `/media/process-videos`) and admin (`/metrics/reset`) endpoints now enforce claims via `require_permissions` / `require_roles` alongside existing dependencies; RAG search routes (`/rag/search`, `/search/stream`, `/simple`, `/batch`) are also claim-first.
- The Evaluations admin idempotency-cleanup endpoint (`/evaluations/admin/idempotency/cleanup`) now uses `require_roles("admin")` in addition to the existing `require_admin` helper, and is covered by HTTP-level claim tests in `tests/AuthNZ/integration/test_evaluations_permissions_claims.py` to ensure 401/403/200 semantics remain stable.
- Integration coverage for claim-first HTTP semantics is expanding in `tests/AuthNZ/integration/test_rag_media_permissions_claims.py` (skips when Postgres is unavailable) for JWT and API-key flows.
- SQLite regression coverage mirrors the claim-first HTTP semantics (RAG + media) in `tests/AuthNZ_SQLite/test_rag_media_permissions_sqlite.py` using dependency overrides to isolate auth behavior.
- Resource-Governor admin/config endpoints (`/api/v1/resource-governor/policy`, `/policies`, `/policy/{policy_id}`) and diagnostics endpoints (`/diag/peek`, `/diag/query`, `/diag/capabilities`) now use `require_roles("admin")` instead of `RoleChecker("admin")`. Their behavior is locked in by:
  - `tldw_Server_API/tests/AuthNZ_Unit/test_resource_governor_permissions_claims.py` (claim-first 401/403/200 matrix via `get_auth_principal`).
  - `tldw_Server_API/tests/Resource_Governance/test_rg_capabilities_endpoint.py` and `test_resource_governor_endpoint.py` (single-user API-key flows and policy admin integration) to confirm no behavior drift in existing RG tests.
- `llm_budget_guard` derives an `AuthPrincipal` (via `request.state.auth` when available) and now uses that principal when consulting governance for LLM budgets; middleware and dependency paths include embeddings/chat overage regressions with principal metadata.
- Single-user deployments now share the same claim-first + DB-fallback semantics as multi-user for permission and role checks: `permissions.py` no longer treats `is_single_user_mode()` as an “allow-all” shortcut when claims are missing. This behavior is locked in by additional tests in `tldw_Server_API/tests/AuthNZ_Unit/test_permissions_claim_first.py` (e.g., `test_check_permission_single_user_mode_prefers_claims`, `test_check_permission_single_user_mode_without_claims_falls_back_to_db`, `test_check_role_single_user_mode_treats_admin_as_admin_and_user`, `test_check_role_single_user_mode_without_roles_falls_back_to_db`).
- A focused audit of `is_single_user_mode()` usages confirms that remaining mode checks are either:
  - Coordination/governance decisions (startup banners, WebUI configuration, ChaChaNotes warm-up, backpressure/tenant RPS toggles, embedding quotas), or
  - Profile selection for auth flows (single-user API key vs multi-user JWT/API-key) and diagnostics.
  The main auth-adjacent exception is the Jobs admin domain-scoped RBAC helper in `tldw_Server_API/app/api/v1/endpoints/jobs_admin.py`, which enforces domain filters via env-driven settings (`JOBS_DOMAIN_SCOPED_RBAC`, `JOBS_REQUIRE_DOMAIN_FILTER`, `JOBS_DOMAIN_ALLOWLIST_*`). As part of this iteration, all domain-scoped jobs-admin surfaces now have a principal-first domain RBAC path gated by `JOBS_DOMAIN_RBAC_PRINCIPAL`:
  - `_enforce_domain_scope_from_principal(principal: AuthPrincipal, domain: Optional[str])` builds the same “admin user” dict as before and forwards to `_enforce_domain_scope`, but is driven purely from `AuthPrincipal` rather than a user dict produced by `require_admin`.
  - Queue status/control, prune/reschedule/retry-now, events (list/SSE), TTL sweep, integrity sweep, stats, list, stale, batch cancel/reschedule, and batch requeue-quarantined endpoints all consult `_enforce_domain_scope_from_principal` when `JOBS_DOMAIN_RBAC_PRINCIPAL` is enabled and fall back to the legacy user-dict path otherwise.
  Tests in `tldw_Server_API/tests/AuthNZ_Unit/test_jobs_admin_permissions_claims.py` now lock in 401/403/200 and allowlist behavior for these endpoints under both the legacy and principal-driven paths, ensuring that principal-based domain RBAC faithfully mirrors the existing env-driven semantics. The long-term intent is to flip `JOBS_DOMAIN_RBAC_PRINCIPAL` on by default and retire the legacy user-dict/env toggles once existing deployments have validated the principal-based behavior.

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

**Status**: Done

**Notes**:
- A minimal `AuthGovernor` facade for LLM budgets is implemented in `tldw_Server_API/app/core/AuthNZ/auth_governor.py`, decorating `is_key_over_budget` with principal metadata and over-budget detail.
- `llm_budget_guard.enforce_llm_budget` and `LLMBudgetMiddleware` call `AuthGovernor.check_llm_budget_for_api_key` using an `AuthPrincipal` (from `AuthContext` or derived from `request.state`) and preserve 402 semantics while adding structured principal details; coverage now includes chat and embeddings overage regressions.
- Login lockout flows in `/auth/login` route lockout checks and failed-attempt counters through `AuthGovernor.check_lockout` / `record_auth_failure` (wrapping the shared RateLimiter) and return HTTP 429 when a client IP is locked out. Integration tests in `tldw_Server_API/tests/AuthNZ/integration/test_auth_login_lockout_via_auth_governor.py` and `test_auth_login_lockout_real_rate_limiter.py` cover both stubbed and real limiter backends.
- AuthNZ-level rate limiting for generic endpoints (`check_rate_limit`) and authentication flows (`check_auth_rate_limit`) now delegates to `AuthGovernor.check_rate_limit`, which in turn wraps `RateLimiter.check_rate_limit` and normalizes metadata. When the limiter is unavailable or disabled, `AuthGovernor.check_rate_limit` fails open with `(True, {})`, preserving existing behavior of treating guardrails as best-effort while keeping error semantics (HTTP 429 with `Retry-After` headers) stable where limits are enforced. Unit tests in `tldw_Server_API/tests/AuthNZ_Unit/test_auth_governor_budget.py` exercise the new rate-limit helper, and existing rate-limiter tests (`test_rate_limiter_*`) continue to cover the underlying storage and window logic.
