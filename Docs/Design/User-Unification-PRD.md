# User Unification PRD (v0.1)

## Summary

AuthNZ supports:

- **Single-user mode**: a fixed API key (`SINGLE_USER_API_KEY`), a synthetic user, SQLite users DB.
- **Multi-user mode**: username/password + MFA → JWT access/refresh, sessions, RBAC, orgs/teams, API keys, virtual keys.
- **Multiple DB backends**: SQLite by default; Postgres for production, with many dialect-specific code paths.

Today these are implemented as separate “modes” with special cases scattered across AuthNZ, and many modules contain inline Postgres/SQLite branching and DDL. This PRD proposes:

1. Treating single-user as a constrained configuration of the multi-user model (a bootstrap user + key) instead of a separate runtime mode.
2. Consolidating backend differences behind a small set of repositories, so most of AuthNZ does not care about SQLite vs Postgres.

The goal is to reduce special-case handling, make the mental model “always multi-user under the hood”, and simplify future migrations.

## Related Documents

- `Docs/Design/Principal-Governance-PRD.md` – principal model (`AuthPrincipal` / `AuthContext`) and AuthNZ guardrails.
- `Docs/Design/User-Auth-Deps-PRD.md` – unified auth dependencies, claim-first authorization, and FastAPI wiring.
- `Docs/Design/Resource_Governor_PRD.md` – global, cross-module resource governance (`ResourceGovernor`) used by AuthNZ guardrails.

---

## Problems & Symptoms

### 1. Mode Branching (Single vs Multi User)

- `settings.AUTH_MODE` influences:
  - JWT secret/algorithm validation (`get_jwt_secret`, `validate_jwt_secret`).
  - Database URL fallback (`_apply_single_user_fallback` forcing SQLite for single-user).
  - Permission checks (`permissions.check_*` treating single-user as full allow).
  - User fetching & API-key paths (`User_DB_Handling`).
- Many functions check `is_single_user_mode()` / `is_multi_user_mode()` and diverge behavior.
- Single-user mode bypasses much of the richer auth stack:
  - No JWTs or sessions.
  - No persistent user row required.
  - Permissions effectively bypassed.

### 2. Backend-Specific Logic Everywhere

- Many modules contain `if hasattr(conn, 'fetchval')` branches:
  - `api_key_manager`, `virtual_keys`, `rate_limiter`, `orgs_teams`, `quotas`, `usage_logging_middleware`, `token_blacklist`, etc.
- Each module:
  - Issues its own `CREATE TABLE IF NOT EXISTS` statements.
  - Maintains separate SQL for Postgres vs SQLite (placeholders, JSON vs TEXT, type differences).
- Backend detection is repeated (`DatabasePool.pool` check, `$N` → `?` conversions).

### 3. Cognitive Overhead and Risk

- Contributors must think “Does this run in single-user mode? multi-user? both? Which DB?” for every change.
- Dialect branches are easy to get wrong and hard to test exhaustively.
- Schema evolution is scattered; a new table/column may be created by multiple modules with slightly different DDL.

---

## Goals

### Primary Goals

- **G1: Conceptual Unification of User Model**
  - Make single-user a deployment profile of the multi-user system:
    - Exactly one admin user.
    - Exactly one primary API key.
    - Registration/login endpoints disabled by config.
  - Keep runtime auth and RBAC code identical across profiles.

- **G2: Minimize Mode Branching in Code**
  - Reduce direct `is_single_user_mode()` checks to a handful of coordination points (bootstrap, feature gating), not per-call behavior.
  - Permissions and roles should be determined by data (claims) rather than mode.

- **G3: Backend as Implementation Detail**
  - Create a small set of repository abstractions for AuthNZ data (users, sessions, API keys, orgs/teams, RBAC, usage) to hide Postgres/SQLite specifics.
  - Move DDL and migrations out of business logic modules into centralized migrations and/or repositories.

### Secondary Goals

- Simplify local environment setup and documentation:
  - “Single-user dev mode” becomes “multi-user with one bootstrapped account over SQLite”.
- Make it possible to switch from SQLite to Postgres without touching business code.

### Non-Goals (Initial Version)

- Removing `AUTH_MODE` entirely in v1; we will deprecate its usage gradually.
- Unifying all DB access patterns across the entire project (this PRD focuses on AuthNZ).

---

## Proposed Solution

### 1. Single-User as a Bootstrap Profile

**Concept**

- Single-user deployments are just multi-user deployments seeded with:
  - One admin user in `users`.
  - One primary API key linked to that user.
  - Optional one “service” token for internal automation (e.g., scheduler).
- Registration/login endpoints and admin user-management endpoints are restricted by configuration.

**Implementation Sketch**

- Add a “bootstrap” function in `AuthNZ.initialize`:
  - Checks `AUTH_MODE` and a new setting like `SINGLE_USER_BOOTSTRAP_ENABLED`.
  - Ensures:
    - A user with a deterministic id (e.g., `SINGLE_USER_FIXED_ID`) and username (e.g., `single_user`) exists; if not, creates it.
    - A primary API key for that user exists; if not, create via `APIKeyManager` and display/record it.
    - That user has `admin` role and full permissions (via RBAC tables).
- Replace mode-specific auth logic with shared flows:
  - Single-user API key verification uses normal API-key code paths via `APIKeyManager`.
  - `AuthPrincipal` (from Principal-Governance PRD) always represents a user with claims; single-user is just a user with admin role and one API key.

**Bootstrap semantics & idempotency**

- **Existing `SINGLE_USER_API_KEY`**:
  - If `SINGLE_USER_API_KEY` is set, bootstrap MUST treat it as the canonical on-wire key.
  - Bootstrap hashes/persists this key for `SINGLE_USER_FIXED_ID` if no matching API-key row exists yet, rather than generating a new key.
  - This preserves existing single-user deployments without requiring users to rotate or rediscover their key.
- **No `SINGLE_USER_API_KEY` configured**:
  - If no key is configured, bootstrap MAY generate a new primary API key for `SINGLE_USER_FIXED_ID`.
  - Emission of the generated key (logs vs stdout vs “once-only” file) is controlled by configuration and documented.
- **Idempotency**:
  - Bootstrap is safe to run multiple times: it ensures exactly one admin user with `SINGLE_USER_FIXED_ID` and exactly one primary API key for that user.
  - Re-running bootstrap on an already bootstrapped database MUST NOT create duplicate users or keys and should be a no-op aside from validation.
- **Pre-existing data and conflicts**:
  - If multiple admin users or multiple “primary” keys for `SINGLE_USER_FIXED_ID` are detected, bootstrap SHOULD fail loudly with a clear error and guidance for remediation rather than guessing.
  - If `AUTH_MODE=single_user` is configured but the database already contains multiple active users, bootstrap logs a warning and either:
    - Treats this as a misconfiguration (fail fast, recommended default), or
    - Proceeds in a documented “mixed” mode only if explicitly allowed by configuration.

**Mode branching reduction**

- `is_single_user_mode()` becomes:
  - Primarily a configuration signal for:
    - Bootstrap logic.
    - Default database URL (still SQLite-leaning in docs).
    - Feature gating UI/docs (e.g., “no multi-tenant UI in single-user profile”).
- Permission functions no longer special-case single-user; they rely on claims on the principal.

**Existing single-user dependencies (transitional state)**

- Today, several AuthNZ components implement their own single-user mode handling:
  - `auth_deps.get_current_user` has dedicated branches for `SINGLE_USER_API_KEY` and synthetic single-user dicts.
  - `User_DB_Handling.get_request_user` constructs a dummy `User` with admin-style claims when `is_single_user_mode()` is true.
  - `verify_single_user_api_key` validates the fixed key independently of APIKeyManager.
- For v1, these must be treated as compatibility layers:
  - Internally, they will be refactored to rely on the bootstrapped user + API key and `get_auth_principal` / `AuthContext`.
  - Externally, their observable behavior (headers accepted, 401/403 responses, basic user fields) remains intact while single-user mode is redefined as a bootstrap profile.
  - New code MUST NOT introduce additional `is_single_user_mode()` branches for auth; instead, it should use profile/claims-based decisions and the unified principal model.

### 2. DB Backend Unification via Repositories

**Concept**

- Introduce a small “AuthNZ repository” layer that encapsulates all SQL and dialect specifics.
- Business logic modules depend on repositories, not direct SQL or `conn.execute(...)`.

**Repository contracts**

- Repositories acquire connections via the shared `DatabasePool` abstraction; they do not open raw connections directly.
- Repositories expose narrow, task-focused methods and hide Postgres/SQLite-specific SQL, placeholders, and JSON/TYPE differences.
- Expected domain errors (e.g., uniqueness violations, missing rows) are mapped to typed AuthNZ exceptions; unexpected driver errors surface as internal errors and are logged with context.
- v1 scope is intentionally limited:
  - Users, API keys, and core RBAC tables are covered by repositories.
  - Usage/metrics repositories (e.g., for `usage_log` / `llm_usage_log`) remain out of scope for this iteration and are future work.

**Initial repositories (examples)**

- `AuthnzUsersRepo`:
  - Methods:
    - `get_user_by_id`, `get_user_by_username_or_email`.
    - `create_user`, `update_user`, `deactivate_user`.
  - Under the hood, handles Postgres vs SQLite differences.

- `AuthnzApiKeysRepo`:
  - Methods used by `APIKeyManager`:
    - `insert_api_key`, `mark_revoked`, `rotate_key`.
    - `fetch_by_hashes`, `fetch_limits_for_key`, `list_keys_for_user`.

- `AuthnzRbacRepo`:
  - Methods used by RBAC helpers and bootstrap:
    - `assign_role_to_user`, `get_user_roles`, `get_effective_permissions`.

- `AuthnzOrgsTeamsRepo`, `AuthnzUsageRepo`, etc., added as needed.

**Refactors**

- Move DDL from:
  - `api_key_manager._create_tables`.
  - `virtual_keys`, `quotas`, `rate_limiter` (AuthNZ-specific tables).
  - `orgs_teams`, `usage_logging_middleware`, and relevant pieces of `token_blacklist`.
- Into:
  - Migrations in `AuthNZ.migrations` / `pg_migrations_extra`.
  - Repository initialization helpers (for compatibility with existing migrations).

**Backend detection**

- All backend detection and placeholder conversion (`$1` vs `?`) become internal to repositories or to `DatabasePool`.
- Business logic modules stop branching on `if hasattr(conn,'fetchval')`.

### 3. Deployment Profiles

Define and document profiles rather than modes:

- **Profile: local-single-user**
  - SQLite users DB (default path).
  - Bootstrap user + API key.
  - No registration endpoints for additional users (gated by config and service layer).
  - Creating additional users is forbidden as a hard constraint:
    - User-creation endpoints are disabled.
    - Repository and/or service-layer checks reject any attempt to create users beyond `SINGLE_USER_FIXED_ID` while in this profile.

- **Profile: multi-user-postgres**
  - Postgres users DB.
  - Full registration, MFA, orgs/teams, API keys, virtual keys.

Internally, both share the same code paths; only bootstrap, DB URL, and enabled endpoints differ.

**Profile matrix (behavior overview)**

| Feature / Capability        | local-single-user                | multi-user-postgres          |
|----------------------------|----------------------------------|------------------------------|
| User registration          | Disabled                         | Enabled                      |
| Additional user creation   | Forbidden (hard constraint)      | Enabled                      |
| MFA                        | Optional (config-gated)          | Enabled / strongly recommended |
| Orgs/teams                 | Optional / commonly unused       | Enabled                      |
| Virtual keys               | Optional                         | Enabled                      |
| Multi-tenant Web UI        | Disabled / single-tenant only    | Enabled                      |

Over time, `AUTH_MODE` may be decomposed into a `PROFILE` plus more granular feature flags (`ENABLE_REGISTRATION`, `ENABLE_MFA`, etc.), but v1 keeps `AUTH_MODE` for compatibility and treats profiles as an interpretation of the existing settings.

---

## Scope

### In-Scope (v1)

- Add bootstrap logic and data invariant for single-user profile (user + API key + admin role).
- Refactor:
  - Single-user API key validation to use API-key flow.
  - Permission checks to rely on claims instead of `is_single_user_mode`.
  - A small number of modules to use repositories instead of inline SQL:
    - `api_key_manager`.
    - `orgs_teams` (for core operations).
    - Parts of `virtual_keys` related to key limits.

### Out of Scope (v1)

- Fully migrating all AuthNZ-related SQL to repositories (will be incremental).
- Changing external configuration names (`AUTH_MODE`, `DATABASE_URL`) in this iteration.

---

## Risks & Mitigations

- **Risk: Breaking existing single-user deployments that rely on current behavior.**
  - Mitigation:
    - Keep `AUTH_MODE=single_user` semantics stable at the API surface.
    - Implement bootstrap to mirror current behavior (single admin-like user + API key).
    - Feature-flag any endpoint gating until tests cover both profiles.

- **Risk: Repository layer adds indirection.**
  - Mitigation:
    - Keep repositories thin and focused on SQL/dialect concerns.
    - Co-locate them with AuthNZ code and document clear contracts.

- **Risk: Migration complexity.**
  - Mitigation:
    - Start with a small, high-impact subset (API keys, core orgs/teams, RBAC).
    - Add tests that run both SQLite and Postgres variations where possible (as in current AuthNZ tests).

- **Risk: On-wire behavior changes (auth headers, status codes, error payloads).**
  - Mitigation:
    - Explicitly test both profiles to ensure 401/403 and success responses remain compatible with current behavior.
    - Document any unavoidable changes and, where needed, gate them behind configuration or versioning.

---

## Upgrade / Migration Strategy

- **Detect legacy single-user deployments**:
  - Presence of `AUTH_MODE=single_user` and/or `SINGLE_USER_API_KEY`.
  - Existing “synthetic” single-user patterns in the users/API-key tables.
- **Migration steps for operators**:
  - Take a database backup.
  - Enable the new bootstrap flow and run AuthNZ initialization once.
  - Verify that:
    - An admin user with `SINGLE_USER_FIXED_ID` exists.
    - The stored primary API key matches `SINGLE_USER_API_KEY` (if configured).
    - RBAC tables contain the expected admin role/permissions.
  - Re-run bootstrap to confirm idempotency.
- **Mixed / unexpected states**:
  - If bootstrap detects multiple active users or conflicting admin/primary key invariants under `AUTH_MODE=single_user`, it fails fast with a clear error message and remediation guidance (e.g., which rows to inspect or archive).
  - Operators are encouraged to resolve conflicts explicitly rather than relying on implicit migrations.
- **Multi-user deployments**:
  - For `AUTH_MODE=multi_user` / `multi-user-postgres`, bootstrap is a no-op beyond validation; repositories and migrations are introduced in a way that does not change on-wire auth behavior.

---

## Milestones & Phasing

### Phase 1: Single-User Bootstrap

- Implement bootstrap script/entrypoint in AuthNZ initialize:
  - Create admin user + API key if missing.
  - Wire into docs and quickstart scripts.
- Ensure single-user profile passes existing tests (and new ones).

### Phase 2: Claims-Based Single-User Permissions

- Update permissions code to:
  - Stop special-casing `is_single_user_mode()` for allow-all.
  - Rely on claims from `AuthPrincipal` / `User` (admin role).
- Add tests verifying that the single-user admin has all needed permissions via claims.

### Phase 3: Repository Introduction

- Create initial repositories (`AuthnzApiKeysRepo`, `AuthnzUsersRepo`, `AuthnzRbacRepo`) and migrate:
  - `APIKeyManager` to use `AuthnzApiKeysRepo`.
  - Some RBAC helpers to use `AuthnzRbacRepo`.
- Move DDL for API key-related tables into migrations or repositories.

### Phase 4: Backend Drift Reduction

- Identify and refactor 2–3 high-impact modules (e.g., `virtual_keys`, `orgs_teams`, parts of `rate_limiter` that are AuthNZ-specific) to use repositories.
- Remove duplicated Postgres/SQLite branches that are now redundant.

---

## Open Questions

- Should we eventually drop `AUTH_MODE` in favor of more specific flags (e.g., `ENABLE_REGISTRATION`, `ENABLE_MFA`, `PROFILE=single_user`), or keep it as a high-level profile indicator?
  - yes, drop `AUTH_MODE` for specific flags
- How much of DB backend selection should be driven by a central `DATABASE_URL` vs. per-module URLs?
  - Everything through the central DB URL, modules should only see a single DB/be agnostic.
- Should bootstrap be idempotent-only at startup, or also available as a one-time admin command?
  - one-time admin command

---

## Success Criteria

- Single-user deployments are implemented as a constrained configuration of multi-user infrastructure; no separate auth code path is required.
- The number of direct `is_single_user_mode()` checks in the codebase is significantly reduced and confined to a small set of coordination points.
- At least API-key and user-related AuthNZ modules no longer contain inline dialect branches or DDL; they use repositories instead.
 - For both profiles, authentication headers, HTTP status codes (401/403), and error payloads remain compatible with current behavior, or any intentional changes are explicitly documented and tested.

## Implementation Plan

### Stage 1: Single-User Bootstrap
**Goal**: Make single-user deployments a bootstrap profile of multi-user by creating an admin user and primary API key via normal AuthNZ flows.

**Success Criteria**:
- Running the AuthNZ initializer in single-user profile ensures:
  - A single admin user (`SINGLE_USER_FIXED_ID`) exists in `users`.
  - A primary API key exists and is stored/displayed according to configuration.
- Existing single-user workflows (API key access, no registration) continue to work.

**Tests**:
- Integration tests that:
  - Start in single-user profile, run bootstrap, and validate presence of the user and key.
  - Use the bootstrapped key to access representative endpoints.
  - Start from an existing single-user database with `SINGLE_USER_API_KEY` set and verify that bootstrap adopts the existing key rather than generating a new one.
  - Re-run bootstrap on an already bootstrapped database to confirm it is idempotent (no duplicate users/keys).

**Status**: Not Started

### Stage 2: Claims-Based Single-User Permissions
**Goal**: Replace mode-based permission allowances with claim-based admin role for the bootstrapped user.

**Success Criteria**:
- `permissions.py` and related checks no longer special-case `is_single_user_mode()` for allow-all.
- The bootstrapped single-user admin has full required permissions via roles/permissions claims.

**Tests**:
- Permission tests verifying:
  - Admin user in single-user profile can perform privileged operations.
  - Non-admin users (if any are created) are constrained by RBAC as expected.

**Status**: Not Started

### Stage 3: Repository Introduction
**Goal**: Introduce AuthNZ repositories and migrate API-key and core user/RBAC operations to them.

**Success Criteria**:
- `APIKeyManager` uses `AuthnzApiKeysRepo` for all DB interactions.
- Selected RBAC helpers use `AuthnzRbacRepo`.
- DDL for API key-related tables is centralized in migrations/repositories rather than scattered.

**Tests**:
- Unit tests for repository methods against both SQLite and Postgres.
- Failure-path tests for repository methods (uniqueness violations, missing rows) to ensure consistent exception mapping.
- Existing API-key and RBAC tests pass unchanged.

**Status**: Not Started

### Stage 4: Backend Drift Reduction
**Goal**: Reduce inline dialect branching in high-impact AuthNZ modules using repositories.

**Success Criteria**:
- `virtual_keys`, `orgs_teams`, and relevant parts of the AuthNZ rate limiter use repositories instead of raw SQL with `hasattr(conn,'fetchval')` checks.
- There are fewer duplicated Postgres/SQLite query variants in AuthNZ code.

**Tests**:
- Regression tests for affected modules under both backends (where supported by current test fixtures).

**Status**: Not Started
