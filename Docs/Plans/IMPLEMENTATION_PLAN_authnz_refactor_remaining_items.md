## Context
This active plan tracks unfinished work split from:
`Docs/Product/Completed/AuthNZ-Refactor/IMPLEMENTATION_PLAN.md`

## Stage 1: Profiles & Modes
**Goal**: Introduce a small set of blessed RAG profiles (e.g., production, research, cheap/fast) with documented defaults that map onto `unified_rag_pipeline` parameters without breaking existing callers.
**Success Criteria**:
- A lightweight profile abstraction exists (e.g., `RAGProfile`) with three named profiles and clear defaults.
- Callers can opt into a profile via a simple API (e.g., helper or `profile` argument) while still being able to override individual knobs.
- Documentation describes each profile's intent, defaults, and tradeoffs (latency, cost, safety).
- Unit tests cover profile-to-pipeline-args mapping and guard against regression.
**Tests**:
- New unit tests for the profile helper module.
- Adjusted/added tests in `tests/RAG_NEW` that exercise at least one profile end-to-end.
**Status**: Complete

## Stage 2: Multi-Tenant Isolation Story
**Goal**: Clarify and tighten multi-tenant isolation across DBs, caches, exemplars, and telemetry for the RAG pipeline.
**Success Criteria**:
- Design doc (or section in existing RAG docs) explicitly states tenant/user boundaries and trust assumptions.
- Caches and persisted artifacts (semantic/adaptive cache, rewrite cache, exemplars) are keyed or scoped by user/namespace/tenant where appropriate, or explicitly disabled in multi-tenant profiles.
- Telemetry/metrics and tracing include tenant-safe labels and guidance on off-box export.
- Tests and/or linters guard against obvious cross-tenant leakage patterns in new code.
**Tests**:
- Unit tests for cache keying/namespacing behavior.
- Focused tests for exemplar logging to ensure user/namespace metadata is present and redaction is applied.
**Status**: Complete

## Stage 3: Pipeline Refactor & API Cleanups
**Goal**: Factor the ~2000-line `unified_rag_pipeline` into composable, testable steps with clearer required/optional components, enforced budgets, and cleaner public API boundaries.
**Success Criteria**:
- A `RAGPipelineContext` (or equivalent) internal abstraction exists and is used across phases (retrieval, expansion, caching, guardrails, reranking, generation, claims, post-verification, telemetry).
- The main entry point becomes a thin orchestrator over smaller functions or classes, without changing external behavior.
- Required vs optional modules are clearly separated; production profiles fail loudly when required components are missing, while experimental paths remain opt-in.
- Time/cost budgets are enforced in a centralized way, with sensible defaults per profile.
- API surface issues (e.g., `enable_streaming` semantics, duplicate helpers, return-type guarantees) are documented and partially addressed without breaking existing clients.
**Tests**:
- Existing `tests/RAG_NEW` suites continue to pass.
- New unit tests for at least one extracted phase (e.g., retrieval or guardrails) to validate behavior in isolation.
**Status**: Not Started

## Stage 4: AuthNZ + Resource Governor Long-Tail Alignment
**Goal**: Complete the remaining adoption checklist items after the v1 baseline for Resource Governor and claim-first AuthNZ dependencies.
**Success Criteria**:
- Remaining legacy limiters are retired once RG parity is validated (Chat `ConversationRateLimiter`, Embeddings `UserRateLimiter`, Evaluations/AuthNZ/Character Chat/Web Scraping shims, legacy SlowAPI counters, and non-RG audio concurrency counters).
- Remaining RG-free ingress routes are explicitly documented and either mapped through `route_map` policies or kept out-of-scope with rationale.
- Remaining legacy `require_admin` helpers in evaluations, embeddings v5, and MCP endpoints are migrated to `get_auth_principal` + claims checks (`require_roles("admin")` and/or `require_permissions(...)`).
- New authorization checks stop branching on `is_single_user_mode()` where principal claims should be authoritative.
- Remaining inline AuthNZ SQL/backend detection is moved to repositories (remaining DDL in `initialize.py`, quota counters in `quotas.py`, residual `hasattr(conn, 'fetchval')` paths) while preserving SQLite/Postgres parity.
**Tests**:
- Keep `tests/Resource_Governance/*`, `tests/AuthNZ_Unit/test_auth_principal_*`, `tests/AuthNZ_Unit/*permissions*_claims.py`, `tests/AuthNZ/integration/test_single_user_claims_permissions.py`, and AuthNZ repo tests passing across SQLite/Postgres backends.
**Status**: In Progress
**Progress Notes**:
- 2026-02-08: Removed residual backend detection-by-`hasattr(conn, "fetchval")` in `app/core/AuthNZ/repos/quotas_repo.py`; backend path now keys off `DatabasePool` backend state. Added unit coverage in `tests/AuthNZ/unit/test_authnz_quotas_repo_backend_selection.py` to lock SQLite/Postgres path selection behavior.
- 2026-02-08: Removed remaining `hasattr(conn, "fetchval")` backend branching in `app/core/AuthNZ/repos/api_keys_repo.py` and `app/core/AuthNZ/repos/sessions_repo.py`; these paths now also key off `DatabasePool` backend state. Verified with focused AuthNZ repo tests under the venv (`10 passed, 5 skipped` across SQLite + unit repo suites).
- 2026-02-08: Embeddings policy enforcement now resolves admin bypass claim-first from `request.state.auth` principal (role/is_admin) with compatibility fallback to `User.is_admin`. Updated `/api/v1/embeddings` and `/api/v1/embeddings/batch` policy checks and metrics config reporting to use request-aware evaluation. Added unit coverage in `tests/Embeddings/test_embeddings_policy_claim_first.py`.
- 2026-02-08: Removed the legacy evaluations `require_admin` helper and migrated remaining tests to claim-first `enforce_heavy_evaluations_admin(principal)` checks. Verified with focused suites (`10 passed` for evaluations heavy-admin tests + permissions claims, and `3 skipped` for invariants suite).
- 2026-02-08: MCP endpoint claim-first slice: `list_tool_catalogs` now derives admin visibility from `request.state.auth` `AuthPrincipal` first (is_admin/role `admin`), with token-role fallback only when principal is absent. Added focused unit coverage in `tests/AuthNZ_Unit/test_mcp_tool_catalog_claim_first_admin.py` and verified alongside existing MCP admin permission claims tests (`10 passed`).
- 2026-02-08: Registration service backend branching no longer probes connection capabilities (`hasattr(conn, 'fetchrow'/'fetchval'/'execute')`). `app/services/registration_service.py` now derives backend path from `DatabasePool` state via `_is_postgres_backend()`, including registration-code listing parameter normalization. Added backend-selection unit coverage in `tests/AuthNZ/unit/test_registration_service_backend_selection.py` to ensure SQLite paths remain SQLite even when connection shims expose Postgres-like methods (`3 passed`).
- 2026-02-08: Storage quota service backend branching no longer probes connection capabilities (`hasattr(conn, 'execute'/'fetchrow'/'fetchval')`). `app/services/storage_quota_service.py` now uses `_is_postgres_backend()` derived from `DatabasePool` state for user quota updates and org/team usage recalculation paths. Added backend-selection unit coverage in `tests/AuthNZ/unit/test_storage_quota_service_backend_selection.py` (`3 passed`) and validated existing storage quota suites (`20 passed`).
- 2026-02-08: `UsersDB` backend checks in `app/core/DB_Management/Users_DB.py` now consistently use `_using_postgres_backend()` (DatabasePool-derived) instead of connection capability probing (`hasattr(conn, 'fetchval')`) in `create_user` and `update_user`. Updated backend-detection unit fixtures in `tests/DB_Management/unit/test_users_db_update_backend_detection.py` to set pool backend state explicitly; validated with DB management suites (`2 passed` + `3 passed`).
- 2026-02-08: Billing enforcer backend branching no longer probes connection capabilities (`hasattr(conn, 'fetchval')`) in `_get_api_calls_today`, `_get_llm_tokens_month`, and `_get_storage_bytes`. `app/core/Billing/enforcement.py` now resolves backend from pool state via `_is_postgres_pool(pool)`. Extended `tests/Billing/test_billing_enforcer_org_usage.py` with SQLite trap coverage for API calls and storage bytes plus updated Postgres pool fixtures; validated with billing suites (`5 passed` + `34 passed`).

## Stage 5: RG v1.1 Legacy Limiter Retirement
**Goal**: Safely retire remaining legacy limiters/shims once RG parity is verified, leaving ResourceGovernor as the sole enforcer.
**Success Criteria**:
- Per-module shadow mismatch metrics show near-zero drift for at least one release window on representative traffic.
- All mapped routes return stable 429/`Retry-After`/`X-RateLimit-*` headers under both memory and Redis backends.
- Legacy limiters are demoted to diagnostics-only shims (no counters) with deprecation warnings, then removed after one stable release.
- Unused `RG_ENABLE_*` aliases and legacy flags are deleted post-release and docs/examples reference RG policies/envs only.
**Tests**:
- For each module (chat, embeddings, authnz, evals, character-chat, web-scraping, audio, workflows), keep/extend parity tests and remove legacy-path assertions only after cutover.
- Regression suite ensures no route double-enforces after shim removal.
**Status**: In Progress
**Progress Notes**:
- 2026-02-08: Extended `tests/Resource_Governance/test_e2e_evals_authnz_character_headers.py` to run deny-header parity coverage across both `RG_BACKEND=memory` and `RG_BACKEND=redis` (8 parametrized cases). Each case now uses backend-scoped policy IDs to reduce cross-test key collisions when Redis stub state is reused.
- 2026-02-08: Extended `tests/Resource_Governance/test_e2e_domains_headers.py` to run deny-header parity coverage across both `RG_BACKEND=memory` and `RG_BACKEND=redis` (8 parametrized cases) for rag/media/research/prompt-studio routes, with backend-scoped policy IDs for Redis-stub isolation.
- 2026-02-08: Extended `tests/Resource_Governance/test_e2e_chat_audio_headers.py` to run both backends (14 parametrized cases) across chat, embeddings, mcp, audio websocket, and audio transcription header paths. Updated the audio transcription test to inject an `sf` shim via `audio` module patch-point (instead of assuming `audio_ep.sf` exists) for compatibility with current endpoint exports. Verified end-to-end with combined run: `30 passed` across the three updated E2E modules.
- 2026-02-08: Extended `tests/Resource_Governance/test_e2e_tokens_daily_cap.py` (chat + embeddings tokens daily-cap denial) and `tests/Resource_Governance/test_e2e_workflows_daily_cap.py` (workflows daily-cap denial) to run under both `RG_BACKEND=memory` and `RG_BACKEND=redis`, with backend-scoped policy IDs. Verified combined RG E2E parity set: `36 passed` across evals/authnz/character, domains, chat/audio, tokens, and workflows modules.
