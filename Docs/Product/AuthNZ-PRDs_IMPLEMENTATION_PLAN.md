# AuthNZ PRDs Implementation Plan (Remaining Work v0.1)

This plan tracks the remaining implementation work for the three AuthNZ-related PRDs:

- `Docs/Product/Resource_Governor_PRD.md`
- `Docs/Product/User-Auth-Deps-PRD.md`
- `Docs/Product/User-Unification-PRD.md`

It is intentionally incremental and aligned with `Docs/Design/AuthNZ-Refactor-Implementation-Plan.md`.

---

## Stage 1: Resource-Governor Legacy Limiters & Ingress Coverage

**Goal**: Finish unifying AuthNZ guardrails under `ResourceGovernor`, retiring legacy per-module limiters and making ingress coverage explicit for high-value routes.

**Success Criteria**:
- All guardrails listed in `Resource_Governor_PRD.md` are either:
  - Enforced via `ResourceGovernor` policies (memory/Redis backends + DB), or
  - Explicitly documented as intentionally out-of-scope for v0.1 (with rationale).
- Legacy limiters called out in `AuthNZ-Refactor-Implementation-Plan.md` Stage 6 (“Remaining Work”) are handled as follows:
  - Chat `ConversationRateLimiter`, embeddings `UserRateLimiter`, Evaluations/AuthNZ/Character-Chat/Web-Scraping shims, legacy SlowAPI counters, and non-RG audio concurrency counters are either removed, wrapped around `ResourceGovernor`, or explicitly gated behind compatibility flags that default to RG-first behavior.
- For each major ingress surface (at minimum: `/api/v1/chat/completions`, `/api/v1/embeddings*`, `/api/v1/rag/*`, `/api/v1/media/*`, `/api/v1/research/*`, `/api/v1/workflows/*`, `/api/v1/prompt-studio/*`, `/api/v1/audio/*`, `/api/v1/auth/*`), the `route_map` / policy configuration:
  - Either has a concrete RG policy entry (per-principal and/or per-tenant) with documented defaults, or
  - Is documented in `Resource_Governor_PRD.md` as explicitly RG-free for v0.1 (e.g., low-risk or local-only routes).
- Configuration flags and startup logs clearly indicate which guardrails are driven by RG vs legacy paths, and toggling legacy flags does not change core 402/429 semantics on RG-governed routes.

**Tests**:
- Extend `tldw_Server_API/tests/Resource_Governance/` to cover:
  - Over-budget / over-limit behavior for the newly RG-governed routes, asserting stable 402/429 payloads and headers.
  - That enabling/disabling legacy limiter flags does not affect RG-governed routes’ behavior (or only affects routes documented as legacy-only).
- Add targeted AuthNZ integration tests (where needed) to ensure:
  - Login lockouts and general AuthNZ rate limits still behave as documented when mediated through `AuthGovernor` + RG.
  - Virtual-key budget enforcement paths continue to emit the expected structured 402 responses with RG metadata.

**Status**: Done

**Notes (v0.1 snapshot)**:
- ResourceGovernor is wired into startup (`app.main`) with file- and DB-backed policy loaders, and `tldw_Server_API/Config_Files/resource_governor_policies.yaml` defines concrete policies and `route_map.by_path` entries for:
  - `/api/v1/chat/*` → `chat.default`
  - `/api/v1/embeddings*` → `embeddings.default`
  - `/api/v1/audio/*` → `audio.default`
  - `/api/v1/mcp/*` → `mcp.ingestion`
  - `/api/v1/evaluations/*` → `evals.default`
- Chat rate limiting:
  - `ConversationRateLimiter.check_rate_limit` consults ResourceGovernor via `_maybe_enforce_with_rg_chat` when global RG is enabled. When an RG decision is available it is enforced as canonical and legacy counters are bypassed; the legacy limiter is retained as a fallback only when RG is disabled/unavailable. Behavior is covered by `tldw_Server_API/tests/Resource_Governance/test_chat_rg_limiter_cutover.py` and `/api/v1/chat/completions` HTTP tests in `tests/Chat/integration/test_chat_endpoint_simplified.py`.
- Embeddings and MCP rate limiting:
  - Embeddings `AsyncRateLimiter.check_rate_limit_async` consults RG when global RG is enabled; when an RG decision exists it is enforced as canonical and the legacy per-user limiter is only used as a fallback. RG cutover is exercised in `tldw_Server_API/tests/Resource_Governance/test_rg_cutover_embeddings_mcp.py`.
  - MCP HTTP limiters consult and enforce RG decisions when global RG is enabled; legacy limiters remain as fallback-only shims. Cutover tests live in `tldw_Server_API/tests/Resource_Governance/test_rg_cutover_embeddings_mcp.py`.
- Evaluations/AuthNZ/Character Chat:
  - Evaluations `UserRateLimiter`, AuthNZ `RateLimiter`, and Character Chat limiter consult RG first when global RG is enabled, falling back to legacy DB/Redis counters only when RG is unavailable. Behavior is validated by `test_rg_cutover_evals_authnz_character_web.py` and the HTTP header tests in `test_e2e_evals_authnz_character_headers.py`.
- Web Scraping:
  - Enhanced web scraping `RateLimiter.acquire` calls `_maybe_enforce_with_rg_web_scraping` when global RG is enabled, reserving `RGRequest(entity="service:web_scraping", categories={"requests": {"units": 1}})` against `web_scraping.default` (or override). RG denials are modeled as backoff sleeps before the in-process second/minute/hour limiter runs. This behavior is covered by `test_rg_cutover_evals_authnz_character_web.py::test_web_scraping_rg_denies`.
- Audio quotas and concurrency:
  - Audio stream concurrency is governed via ResourceGovernor “streams” leases in `audio_quota.can_start_stream/finish_stream/heartbeat_stream`, with Redis/in-process counters as explicit fallbacks when RG is unavailable; RG behavior is locked in by `tldw_Server_API/tests/Audio/test_audio_quota_rg_and_ledger.py`.
  - Daily minutes caps use the shared `ResourceDailyLedger` first (`_ledger_remaining_minutes`), with legacy `audio_usage_daily` enforcement as a fallback; the ledger path is covered by the same test module.
- SlowAPI ingress:
  - Global SlowAPI middleware uses a test-aware key function (`get_test_aware_remote_address`) that:
    - Bypasses limits when `TEST_MODE`/`TLDW_TEST_MODE` is set.
    - Returns `None` when `RGSimpleMiddleware` is attached, so ingress enforcement is handled by ResourceGovernor while SlowAPI decorators act purely as config carriers. This behavior is validated by `tldw_Server_API/tests/RateLimiting/test_slowapi_rg_key_func.py` and the RG ingress e2e tests in `tldw_Server_API/tests/Resource_Governance/test_e2e_chat_audio_headers.py`.
- High-value domains that were RG-free in v0.1 are now governed at ingress in v1.1:
  - Default policies and `route_map.by_path` entries exist for `/api/v1/research/*`, `/api/v1/workflows/*` (and `/api/v1/scheduler/workflows/*`), `/api/v1/prompt-studio/*`, `/api/v1/rag/*`, and `/api/v1/media/*`.
  - Legacy ingress limiters are bypassed on RG-governed routes so ResourceGovernor is the single source for request-rate enforcement.

---

## Stage 2: User-Auth-Deps Long-Tail Adoption & Legacy Dependencies

**Goal**: Complete adoption of the claim-first dependency stack (`get_auth_principal`, `get_current_user`, `require_permissions`, `require_roles`) across AuthNZ-adjacent endpoints and remove remaining authorization paths that rely on `require_admin` or direct mode checks.

**Success Criteria**:
- A systematic audit covers all remaining uses of:
  - `require_admin` (and similar legacy admin helpers) in FastAPI endpoints.
  - `is_single_user_mode()` / `AUTH_MODE` in authorization or guardrail decisions (as opposed to coordination/UX).
  - Direct `request.state.user_id` / `api_key_id` checks used as gates rather than as derived context.
- For each audited cluster, concrete migrations are implemented:
  - Evaluations admin: legacy `require_admin` callsites are replaced with `get_auth_principal` + `require_roles("admin")` and, where appropriate, dedicated permissions (for example, heavy-evaluations admin) via `enforce_heavy_evaluations_admin(principal)` as outlined in `User-Auth-Deps-PRD.md`.
  - Embeddings v5 admin utilities: maintenance-only routes that still use a local `require_admin(current_user)` helper are migrated to explicit permissions/roles (for example, `EMBEDDINGS_ADMIN`, `EMBEDDINGS_TENANT_ADMIN`) or are explicitly tagged as compatibility-only and guarded by env flags.
  - MCP unified diagnostics: endpoints relying on module-local `require_admin` are migrated to `require_roles("admin")` / `require_permissions(SYSTEM_LOGS)` where feasible, or explicitly documented as compatibility shims when MCP-specific tokens are necessary.
- No new endpoints introduce:
  - Fresh `require_admin` usages (outside tests/compatibility stubs).
  - New `is_single_user_mode()`-based authorization branches or direct `request.state.user_id` gates.
- `Docs/Product/User-Auth-Deps-PRD.md` “Remaining adoption checklist” items are either:
  - Marked as completed with references to tests and code, or
  - Explicitly deferred to a later version with notes.

**Tests**:
- Extend and/or add suites under `tldw_Server_API/tests/AuthNZ_Unit/` to cover:
  - Updated evaluations admin flows, ensuring `require_roles("admin")` + heavy-evaluations permissions enforce correct 401/403/200 semantics.
  - Embeddings v5 admin utilities and MCP diagnostics, ensuring legacy paths (when kept) are clearly gated by env flags and claim-first paths behave identically across SQLite and Postgres.
- Add focused HTTP tests (where missing) under `tldw_Server_API/tests/AuthNZ/integration/` for any newly claim-first endpoints, asserting:
  - Correct behavior for JWT vs API-key principals.
  - Denial when called with `kind="service"` or `kind="anonymous"` but the endpoint expects a user principal.

**Status**: Done (core claim-first stack is in place; remaining legacy helpers are explicitly scoped and documented).

**Notes (v0.1 snapshot)**:
- Evaluations admin flows now use `enforce_heavy_evaluations_admin(AuthPrincipal)` together with claim-first dependencies; the legacy `require_admin(user)` helper in `evaluations_auth.py` has no remaining router-level callsites and is retained only as a compatibility shim for heavy-evaluations admin paths explicitly called out in `User-Auth-Deps-PRD.md`.
- Embeddings v5 admin utilities (model warmup/download, cache clear, tenant and DLQ maintenance) are gated via `require_roles("admin")` and dedicated permissions such as `SYSTEM_CONFIGURE` / `EMBEDDINGS_ADMIN` in `embeddings_v5_production_enhanced.py`; the older `require_admin(current_user)` helper lives only in an unused backup module and is not part of the supported surface.
- MCP unified diagnostics adopt claim-first guards for both JSON and Prometheus endpoints: `/mcp/modules/health`, `/mcp/metrics`, and `/mcp/metrics/prometheus` all depend on `require_permissions(SYSTEM_LOGS)` and reuse `get_auth_principal`, with behavior covered by `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_admin_permissions_claims.py`, `tldw_Server_API/tests/MCP_unified/test_mcp_http_auth_paths.py`, and the MCP metrics endpoint tests. The previous `require_admin_unless_public` compatibility shim and `MCP_PROMETHEUS_PUBLIC` flag are treated as deprecated and no longer influence access to the Prometheus endpoint.
- Topic monitoring, audit, chat diagnostics, RAG health, scheduler workflows admin, and notes graph endpoints all use `require_permissions(...)` / `require_roles(...)` on `AuthPrincipal` as their primary gates, with any remaining `require_admin` usage confined to narrow, documented abuse-cap or legacy flows (for example, flashcards import overrides).
- An audit of `request.state.user_id` / `api_key_id` consumers confirms they are used as derived context (usage logging, RG entity keys, budget guards) rather than as primary authorization gates; new code is expected to continue using `AuthPrincipal` for decisions and treat these fields as secondary context only. New endpoints MUST NOT introduce fresh `require_admin` or `is_single_user_mode()`-based authorization branches; they must build on the unified claim-first dependency stack instead.

---

## Stage 3: User-Unification – Inline DDL & Quota Tables → Migrations/Repos

**Goal**: Eliminate remaining runtime inline DDL and dialect branching for AuthNZ quota/counter tables by migrating them into canonical migrations and a focused repository, while keeping Postgres/SQLite behavior identical to v0.1.

**Success Criteria**:
- Inline Postgres/SQLite DDL for AuthNZ tables listed as tech debt in `AuthNZ-Refactor-Implementation-Plan.md` (“Remaining inline SQL / backend detection”) is fully migrated:
  - `initialize.py` bootstrap DDL for `audit_logs`, `sessions`, `registration_codes`, RBAC tables, organizations/teams is backed by migrations (SQLite + Postgres) and/or repository-level helpers; the bootstrap path becomes a guarded backstop only and is no longer the primary schema definition. For Postgres, this is now centralized in `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py::ensure_authnz_core_tables_pg`, which is invoked from `initialize.setup_database` instead of embedding raw DDL.
  - `api_key_manager.py` and `rate_limiter.py` retain at most minimal, clearly-marked bootstrap-only DDL; all runtime reads/writes go through repositories and migration-owned schema.
- Virtual-key quota counters are centralized:
  - A small `AuthnzQuotasRepo` (or equivalent) owns DDL and runtime operations for `vk_jwt_counters` and `vk_api_key_counters`, encapsulating the current `INSERT … ON CONFLICT` logic and dialect differences.
  - `tldw_Server_API/app/core/AuthNZ/quotas.py::increment_and_check_jwt_quota` and `increment_and_check_api_key_quota` delegate to the repo API instead of issuing raw SQL and inspecting `hasattr(conn, "fetchval")`.
- Canonical migrations exist for quota tables in both backends:
  - Migrations create `vk_jwt_counters` / `vk_api_key_counters` with the correct types and constraints for SQLite and Postgres.
  - `_ensure_tables(conn)` in `quotas.py` becomes a thin compatibility wrapper over these migrations (or is removed after at least one stable release), and is no longer the primary schema owner.
- `Docs/Product/User-Unification-PRD.md` “Recommended Next Steps” section reflects the completed state for this stage, with concrete references to migrations and `AuthnzQuotasRepo`.

**Tests**:
- Unit tests for `AuthnzQuotasRepo` covering:
  - Happy-path increments for JWT/API-key counters in both SQLite and Postgres.
  - Limit enforcement (allowed/denied) and error handling (fallback behavior when the DB is unreachable).
- Integration tests (per backend) that exercise:
  - Virtual-key quota enforcement in realistic flows (e.g., virtual-key usage over chat/embeddings endpoints) to confirm counters and limits are respected.
  - Safe coexistence with existing usage/LLM budget counters and RG-driven budgets.

**Status**: Done

### Stage 3 – Next PR TODOs (Inline Quotas Repo)

The following checklist is scoped for a single, reviewable PR that implements the core of Stage 3:

1. **Audit & Confirm Scope**
   - Re-scan `tldw_Server_API/app/core/AuthNZ` for `vk_jwt_counters` / `vk_api_key_counters` and inline DDL / `hasattr(conn, "fetchval")` branches, confirming that the only runtime quota logic lives in `quotas.py` and that bootstrap DDL for these tables is limited to `initialize.py` / `pg_migrations_extra.py`.
   - Write a short doc comment in `quotas.py` summarizing current behavior and the migration plan (repo + migrations) to guide reviewers.

2. **Design & Add Migrations**
   - Add SQLite and Postgres migrations that create `vk_jwt_counters` and `vk_api_key_counters` with the current schema semantics (types, PKs, `ON DELETE CASCADE` where applicable).
   - Ensure migrations are idempotent and consistent with the existing `pg_migrations_extra.ensure_virtual_key_counters_pg` helper; update `pg_migrations_extra` to rely on the new migration helpers where appropriate.

3. **Implement `AuthnzQuotasRepo`**
   - Introduce a new repository module (for example, `tldw_Server_API/app/core/AuthNZ/repos/quotas_repo.py`) with focused methods:
     - `ensure_schema(db_pool)` or similar, delegating to migrations/bootstrap helpers.
     - `increment_jwt_counter(jti, counter_type, bucket, limit)` → returns `(allowed: bool, count: int)`.
     - `increment_api_key_counter(api_key_id, counter_type, bucket, limit)` → returns `(allowed: bool, count: int)`.
   - Encapsulate all dialect-specific SQL inside the repo, using the existing asyncpg/aiosqlite patterns used by other AuthNZ repos.

4. **Refactor `quotas.py` to Use the Repo**
   - Update `increment_and_check_jwt_quota` / `increment_and_check_api_key_quota` to:
     - Construct/obtain `AuthnzQuotasRepo` from the shared `DatabasePool`.
     - Delegate increment-and-check logic to the repo methods.
     - Preserve existing error-handling semantics (`logger.debug` + `(True, -1)` fallback when DB-backed quotas fail).
   - Keep `_ensure_tables` temporarily as a thin compatibility wrapper (ideally calling into the repo/migrations), but mark it as legacy/guardrail-only in a docstring for future removal.

5. **Wire Initialization & Backstops**
   - Ensure that AuthNZ initialization and FastAPI startup paths that currently call `ensure_virtual_key_counters_pg` or inline DDL now route through migration helpers and/or `AuthnzQuotasRepo.ensure_schema`.
   - Verify that Postgres and SQLite startup behavior remains safe and idempotent (no failures when migrations have already run; no silent failures when they have not).

6. **Add Tests**
   - Add unit tests for `AuthnzQuotasRepo` (SQLite + Postgres fixtures) exercising increment and limit behavior, including error paths.
   - Add or extend integration tests to cover:
     - A virtual-key making repeated requests until the quota limit is hit, asserting the same `(allowed, count)` semantics as before.
     - Coexistence with existing usage/LLM budget counters and no regressions in 402 behavior for over-quota flows.

**Notes (v0.1 snapshot)**:
- SQLite migrations own the canonical schema for virtual-key counters via `migration_023_create_virtual_key_counters` in `tldw_Server_API/app/core/AuthNZ/migrations.py:1088`, and PostgreSQL backstops are centralized in `ensure_virtual_key_counters_pg` in `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py:284`, eliminating the need for new inline DDL in guardrail code paths.
- `AuthnzQuotasRepo` (`tldw_Server_API/app/core/AuthNZ/repos/quotas_repo.py`) encapsulates all runtime quota logic for `vk_jwt_counters` and `vk_api_key_counters`, including dialect-specific upserts for asyncpg vs aiosqlite; higher-level helpers no longer embed quota SQL or backend detection.
- `tldw_Server_API/app/core/AuthNZ/quotas.py` has been refactored to delegate `increment_and_check_jwt_quota` / `increment_and_check_api_key_quota` entirely to `AuthnzQuotasRepo`, preserving the `(allowed, count)` semantics and `(True, -1)` fallback behavior on errors.
- AuthNZ initialization (`initialize.py`) wires PostgreSQL startup through `ensure_virtual_key_counters_pg` alongside usage table helpers, while SQLite relies on the migrations pipeline via `ensure_authnz_tables`; schema bootstrap for quota tables is now migration-/helper-driven rather than ad hoc inline DDL.
- Unit and integration coverage for quotas is provided by `tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_quotas_repo_sqlite.py` and `tldw_Server_API/tests/AuthNZ/integration/test_authnz_quotas_repo_postgres.py`, which exercise increment/limit behavior on SQLite and Postgres and verify that repo-level semantics match the legacy `(allowed, count)` contract.

---

## Stage 4: User-Unification – Claim-First Replacements for `is_single_user_mode()`

**Goal**: Replace remaining authorization/guardrail uses of `is_single_user_mode()` with claim-first alternatives built on `AuthPrincipal` + profiles/feature flags, so that “mode” becomes configuration/UX only.

**Success Criteria**:
- A repo-wide audit (guided by `rg "is_single_user_mode"` / code search) classifies each callsite into:
  - Coordination/UX (startup banners, WebUI config hints, warm-ups, quota hints).
  - Auth-adjacent / guardrail (auth deps, quotas, embeddings/MCP behavior, backpressure, tenant-RPS).
- For each auth-adjacent / guardrail callsite:
  - A principal-first alternative is implemented that takes `AuthPrincipal` and/or `AuthContext` plus feature flags/profile (`PROFILE`, `ENABLE_*`, `EMBEDDINGS_TENANT_RPS_PROFILE_AWARE`, `MCP_SINGLE_USER_COMPAT_SHIM`, etc.), as described in Stage 4 of `AuthNZ-Refactor-Implementation-Plan.md`.
  - The new path is gated behind a dedicated env flag so tests can exercise both legacy and principal-first behaviors before flipping defaults.
  - Single-user deployments are enforced purely through bootstrapped principal claims and profile/feature flags, not `is_single_user_mode()` shortcuts.
- After principal-first paths are validated:
  - `User-Unification-PRD.md` documents `is_single_user_mode()` as a compatibility helper used only for settings/bootstrap and coordination/UX.
  - New auth-path logic in AuthNZ modules is prohibited (by code review and documentation) from introducing `AUTH_MODE`/`is_single_user_mode()` branches.

**Tests**:
- Extend existing claim-first test suites to cover each migrated callsite:
  - Backpressure / tenant-RPS behavior (where profile-aware) under single-user vs multi-user profiles.
  - Embeddings and MCP endpoints whose behavior previously depended on mode, ensuring:
    - Single-user profile + bootstrapped admin principal yields the same effective permissions/quotas as before.
    - Multi-user SQLite/Postgres behavior remains unchanged.
- Add targeted unit tests where principal-first helpers are introduced (for example, profile-aware quota decisions that accept `AuthPrincipal`), validating that env flags cleanly select legacy vs principal-first behavior.

**Status**: Done

**Notes (v0.1 snapshot – `is_single_user_mode()` audit)**:
- Auth-adjacent callsites previously driven by `is_single_user_mode()` now have principal-/profile-first replacements behind explicit flags:
  - Org policy helpers use `get_org_policy_from_principal` with `ORG_POLICY_SINGLE_USER_PRINCIPAL` to drive the synthetic `org_id=1` path from `AuthPrincipal` + profile instead of mode.
  - Embeddings tenant quotas use `_should_enforce_tenant_rps` with `EMBEDDINGS_TENANT_RPS_PROFILE_AWARE` to decide when to enforce/disable tenant RPS based on profile and principals explicitly tagged as single-user (subject `"single_user"` via `is_single_user_principal`), rather than raw `AUTH_MODE`.
  - MCP single-user API-key behavior uses `_should_use_single_user_api_key_compat` with `MCP_SINGLE_USER_COMPAT_SHIM` so that single-user admin principals are claim-/flag-driven instead of mode-driven.
- Remaining uses of `is_single_user_mode()` are classified as coordination/UX or operational/backpressure, not authorization:
  - `tldw_Server_API/app/main.py`: startup banners, ChaChaNotes warm-up for the fixed single-user id, and `/webui/config.json` hints (including optional API-key injection for local single-user) branch on mode/profile purely for UX; no permissions or guardrails depend on these checks.
  - `tldw_Server_API/app/core/PrivilegeMaps/service.py::PrivilegeMapService._build_user_dataset` uses `is_single_user_mode()` only when synthesizing a fallback privilege dataset (empty AuthNZ DB) to pick a default role; this affects reporting/visualization, not access control.
  - `tldw_Server_API/app/core/AuthNZ/User_DB_Handling.py` and `tldw_Server_API/app/core/AuthNZ/auth_principal_resolver.py` branch on `is_single_user_mode()` solely to select between single-user API-key vs multi-user JWT/API-key flows; credentials are still fully verified and authorization decisions are made from `AuthPrincipal`/claims.
  - `tldw_Server_API/app/api/v1/API_Deps/backpressure.py::_is_single_user_mode_runtime` and the embeddings profile helper in `embeddings_v5_production_enhanced.py` use mode/profile checks only to decide whether to enforce tenant-style RPS quotas (ingest/embeddings) in local single-user/dev scenarios; they do not bypass claim-based authorization or change who is allowed to call the endpoints.
  - `tldw_Server_API/app/api/v1/endpoints/privileges.py` imports `is_single_user_mode` only for coordination/reporting and does not gate privilege-map access on mode; admin/self checks rely on `get_current_active_user` and claims, not `AUTH_MODE`.
- Legacy, mode-aware auth helpers that still exist (for example, `get_user_org_policy` in `auth_deps` and the heavy-evaluations `require_admin(user)` shim) are explicitly documented in `User-Auth-Deps-PRD.md` as compatibility-only surfaces; new endpoints MUST NOT depend on them and MUST use `get_auth_principal` + `require_permissions` / `require_roles` instead.
- New code is prohibited from introducing additional `AUTH_MODE`/`is_single_user_mode()`-based authorization branches or direct `request.state.user_id` gates; any future behavior changes around single-user vs multi-user must be expressed via `AuthPrincipal` + profiles/feature flags and covered by tests, following the patterns above.

---

## Stage 5: Cross-PRD Integration – Profiles, Flags, and Docs

**Goal**: Align configuration, profile/flag semantics, and documentation across all three PRDs so AuthNZ v0.1 has a clear, test-verified story for deployment profiles and guardrails.

**Success Criteria**:
- Configuration:
  - `Settings.PROFILE` / `get_profile()` and the associated feature flags (`ENABLE_REGISTRATION`, `ENABLE_MFA`, `ENABLE_ORGS_TEAMS`, `ENABLE_VIRTUAL_KEYS`, `EMBEDDINGS_TENANT_RPS_PROFILE_AWARE`, `MCP_SINGLE_USER_COMPAT_SHIM`, jobs-domain flags, etc.) are documented as the primary knobs for deployment behavior; `AUTH_MODE` is treated as a compatibility alias.
  - Startup logs and `/webui/config.json` hints accurately reflect the active profile and key feature flags for both SQLite and Postgres deployments.
- Documentation:
  - `Resource_Governor_PRD.md` documents which routes are RG-governed vs legacy-only after Stage 1, with a simple matrix.
  - `User-Auth-Deps-PRD.md` phases/milestones are updated to mark completed phases and clearly list any deferred adoption items.
  - `User-Unification-PRD.md` profile matrix and “Recommended Next Steps” are updated to reflect completed repo/DDL migrations and mode→profile/flags migration.
- Governance:
  - `Docs/Code_Documentation/Guides/AuthNZ_Code_Guide.md` is updated with:
    - A concise “How to secure a new endpoint” checklist (dependencies, permissions, RG policies, profile/flags).
    - A brief note discouraging new mode-based auth logic and direct `request.state.user_id` checks.

**Tests**:
- A small set of configuration/profile smoke tests:
  - `PROFILE=local-single-user` + SQLite users DB + bootstrapped admin principal.
  - `PROFILE=multi-user-postgres` + Postgres users DB + multi-user flows.
  - Each profile runs a short battery of AuthNZ/RAG/media/chat/evaluations tests to confirm that:
    - Claim-first auth, RG guardrails, and user-unification behavior match the documented profile matrix.
- Optional doc-tests / lints (if used elsewhere in the repo) to ensure PRD and code-guide references remain consistent when profiles/flags are changed.

**Status**: Done
