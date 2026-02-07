## Stage 1: Profiles & Modes
**Goal**: Introduce a small set of blessed RAG profiles (e.g., production, research, cheap/fast) with well-documented defaults that map directly onto `unified_rag_pipeline` parameters without breaking existing callers.
**Success Criteria**:
- A lightweight profile abstraction exists (e.g., `RAGProfile`) with three named profiles and clear defaults.
- Callers can opt into a profile via a simple API (e.g., helper or `profile` argument) while still being able to override individual knobs.
- Documentation describes each profile’s intent, defaults, and tradeoffs (latency, cost, safety).
- Unit tests cover profile → pipeline-args mapping and guard against regression.
**Tests**:
- New unit tests for the profile helper module.
- Adjusted/added tests in `tests/RAG_NEW` that exercise at least one profile end-to-end.
**Status**: Moved to active follow-up plan (`Docs/Plans/IMPLEMENTATION_PLAN_authnz_refactor_remaining_items.md`)

## Stage 2: Eval Harness & Dataset
**Goal**: Provide a reproducible evaluation harness for the unified RAG pipeline with a known dataset and clear retrieval/factuality metrics that can be run locally or in CI.
**Success Criteria**:
- A small, versioned eval dataset exists in-repo (or clearly documented external dataset with loader config).
- A single CLI / script path runs the eval harness against `unified_rag_pipeline` and emits retrieval and factuality metrics.
- Quality eval scheduler is wired to a real default dataset path with docs on how to customize.
- Docs briefly summarize which metrics are reported and how to interpret them.
**Tests**:
- Unit tests for the harness configuration/runner (using a tiny synthetic dataset).
- Smoke-style test that calls the runner in a constrained mode to ensure it doesn’t regress.
**Status**: Complete

## Stage 3: Multi-Tenant Isolation Story
**Goal**: Clarify and, where needed, tighten multi-tenant isolation across DBs, caches, exemplars, and telemetry for the RAG pipeline.
**Success Criteria**:
- Design doc (or section in existing RAG docs) explicitly states tenant/user boundaries and trust assumptions.
- Caches and any persisted artifacts (semantic/adaptive cache, rewrite cache, exemplars) are keyed or scoped by user/namespace/tenant where appropriate, or explicitly disabled in multi-tenant profiles.
- Telemetry/metrics and tracing include tenant-safe labels and guidance on off-box export.
- Tests and/or linters guard against obvious cross-tenant leakage patterns in new code.
**Tests**:
- Unit tests for cache keying / namespacing behavior.
- Focused tests for exemplar logging to ensure user/namespace metadata is present and redaction is applied.
**Status**: Moved to active follow-up plan (`Docs/Plans/IMPLEMENTATION_PLAN_authnz_refactor_remaining_items.md`)

## Stage 4: Pipeline Refactor & API Cleanups
**Goal**: Factor the ~2000-line `unified_rag_pipeline` into composable, testable steps with clearer required/optional components, enforced budgets, and a cleaner public API.
**Success Criteria**:
- A `RAGPipelineContext` (or equivalent) internal abstraction exists and is used across phases (retrieval, expansion, caching, guardrails, reranking, generation, claims, post-verification, telemetry).
- The main entry point becomes a thin orchestrator over smaller functions or classes, without changing external behavior.
- Required vs optional modules are clearly separated; production profiles fail loudly when required components are missing, while “experimental” paths remain opt-in.
- Time/cost budgets are enforced in a centralized way, with sensible defaults per profile.
- API surface issues (e.g., `enable_streaming` semantics, duplicate helpers, return-type guarantees) are documented and at least partially addressed without breaking existing clients.
**Tests**:
- Existing `tests/RAG_NEW` suites continue to pass.
- New unit tests for at least one extracted phase (e.g., retrieval or guardrails) to validate behavior in isolation.
**Status**: Moved to active follow-up plan (`Docs/Plans/IMPLEMENTATION_PLAN_authnz_refactor_remaining_items.md`)

## Stage 5: AuthNZ Principal Skeleton
**Goal**: Introduce `AuthPrincipal` / `AuthContext` types and a stable `principal_id` helper as the foundation for the AuthNZ refactor PRDs (Principal-Governance, User-Auth-Deps, User-Unification).
**Success Criteria**:
- `AuthPrincipal` and `AuthContext` models exist in `tldw_Server_API/app/core/AuthNZ/principal_model.py`.
- A helper `compute_principal_id(kind, subject_key)` computes a stable, pseudonymous identifier derived from the principal kind and subject key.
- A resolver module `tldw_Server_API/app/core/AuthNZ/auth_principal_resolver.py` exposes `get_auth_principal(request)` that reuses existing AuthNZ helpers to derive an `AuthPrincipal`.
- Legacy dependencies (`User_DB_Handling.verify_jwt_and_fetch_user`, `User_DB_Handling.get_request_user`, `auth_deps.get_current_user`) populate `request.state.auth` with an `AuthContext` built from their resolved user and request metadata without changing external behavior.
- Unit tests validate model construction, resolver behavior for single-user/JWT/API-key flows, and request-scoped reuse of `AuthContext` without affecting existing AuthNZ code paths.
**Tests**:
- New unit tests in `tldw_Server_API/tests/AuthNZ_Unit/test_principal_model.py` cover `compute_principal_id`, `AuthPrincipal`, and `AuthContext`.
- New unit tests in `tldw_Server_API/tests/AuthNZ_Unit/test_auth_principal_resolver.py` cover `get_auth_principal` for single-user, JWT, API-key, and missing-credentials cases.
**Status**: Complete

## Stage 6: Resource Governor & AuthNZ v1 Alignment
**Goal**: Align the ResourceGovernor, claim-first auth dependencies, and AuthNZ user-unification repos with their PRDs for a cohesive v1 baseline.
**Success Criteria**:
- `ResourceGovernor` memory/Redis backends, policy loader, and admin/diagnostic endpoints are wired into `tldw_Server_API.app.main`, `tldw_Server_API/app/api/v1/endpoints/resource_governor.py`, and `tldw_Server_API/app/core/Resource_Governance`, with metrics and Redis failover semantics matching `Docs/Product/Resource_Governor_PRD.md`.
- Simple RG middleware and route-map-based policy resolution protect representative HTTP ingress paths (chat, MCP, SlowAPI facade) behind feature flags, with tests in `tldw_Server_API/tests/Resource_Governance` remaining green.
- AuthNZ claim-first dependencies (`get_auth_principal`, `require_permissions`, `require_roles`) are the canonical choice for new admin/diagnostic endpoints, and the main surfaces listed in `Docs/Product/User-Auth-Deps-PRD.md` use them with 401/403/200 semantics covered by tests.
- Single-user bootstrap and the initial AuthNZ repository layer (`AuthnzUsersRepo`, `AuthnzApiKeysRepo`, `AuthnzRbacRepo`, etc.) are the default path in AuthNZ, with both SQLite and Postgres tests covering core flows as described in `Docs/Product/User-Unification-PRD.md`.
**Tests**:
- Keep `tests/Resource_Governance/*`, `tests/AuthNZ_Unit/test_auth_principal_*`, `tests/AuthNZ_Unit/*permissions*_claims.py`, `tests/AuthNZ/integration/test_single_user_claims_permissions.py`, and the AuthNZ repo tests passing across SQLite/Postgres backends.
**Follow-up**:
- Remaining long-tail adoption work was moved to `Docs/Plans/IMPLEMENTATION_PLAN_authnz_refactor_remaining_items.md`.
- PRD-specific detail continues in `Docs/Product/AuthNZ-PRDs_IMPLEMENTATION_PLAN.md`.
**Status**: Complete for v1 baseline; active follow-up tracked in `Docs/Plans/IMPLEMENTATION_PLAN_authnz_refactor_remaining_items.md`

## Stage 7: RG v1.1 — Daily Tokens Ledger (Chat + Embeddings)
**Goal**: Generalize daily token budgeting under ResourceGovernor using `ResourceDailyLedger`, and shadow‑/hard‑enforce tokens‑per‑day for chat and embeddings without breaking legacy behavior.
**Success Criteria**:
- A shared daily ledger category (`tokens`) is used for all LLM token budgets across modules.
- Chat writes daily token usage to `ResourceDailyLedger` after completions (real usage, idempotent op_id), with a one‑time “today so far” backfill from legacy usage tables on upgrade.
- Embeddings writes daily token usage to the same ledger (or explicitly stays request‑only with docs), with backfill on upgrade where applicable.
- RG policy DSL supports a daily cap for tokens (e.g., `tokens.daily_cap`) and the governor enforces it via the ledger on reserve/check.
- Legacy per‑module daily token guards are bypassed on RG‑governed routes once parity is proven.
**Tests**:
- Unit tests for chat/embeddings ledger shadow‑writes + backfill idempotency.
- Resource_Governance integration tests hitting `/api/v1/chat/*` and `/api/v1/embeddings*` under a tiny `tokens.daily_cap`, asserting 200 then 429 with correct `Retry‑After`/`X‑RateLimit-*` parity.
**Status**: Complete

## Stage 8: RG v1.1 — Workflows Daily Ledger Cutover
**Goal**: Move workflows daily run quotas from inline per‑module logic to RG + `ResourceDailyLedger`, making RG the single source for daily caps.
**Success Criteria**:
- A dedicated ledger category (e.g., `workflows_runs`) and matching RG policy field exist and are documented.
- `endpoints/workflows.py` no longer performs inline daily quota checks; instead it consults the ledger for remaining runs and denies via RG semantics/headers.
- Each workflow run records a deterministic ledger entry with stable op_id (workflow/run id), and upgrades backfill any existing “today” legacy counters.
- Legacy daily quota env knobs remain as short‑window aliases but do not change enforcement when RG is enabled.
**Tests**:
- Unit tests for ledger writes/backfill around workflow runs.
- Resource_Governance e2e tests on `/api/v1/workflows/*` under a tiny daily cap, asserting deny parity and headers.
**Status**: Complete

## Stage 9: RG v1.1 — Legacy Limiter Retirement
**Goal**: Safely retire remaining legacy limiters/shims once RG parity is verified, leaving ResourceGovernor as the sole enforcer.
**Success Criteria**:
- Per‑module shadow mismatch metrics show near‑zero drift for ≥1 release window on representative traffic.
- All mapped routes return stable 429/Retry‑After/`X‑RateLimit-*` headers under both memory and Redis backends.
- Legacy limiters are demoted to diagnostics‑only shims (no counters) with deprecation warnings, then removed after one stable release.
- Unused RG_ENABLE_* aliases and legacy flags are deleted post‑release and docs/examples reference RG policies/envs only.
**Tests**:
- For each module (chat, embeddings, authnz, evals, character‑chat, web‑scraping, audio, workflows), keep/extend parity tests and remove legacy‑path assertions only after flip.
- Regression suite to ensure no route double‑enforces after shim removal.
**Status**: Moved to active follow-up plan (`Docs/Plans/IMPLEMENTATION_PLAN_authnz_refactor_remaining_items.md`)

**Notes**:
- Removed per-module `RG_ENABLE_*` / chat primary flags so RG is controlled by global `RG_ENABLED`/config.
- Removed legacy ingress enable/disable aliases (`RG_ENABLE_SIMPLE_MIDDLEWARE`, `RG_ENABLE_SLOWAPI`); `RGSimpleMiddleware` is now controlled solely by `RG_ENABLED` and RG-focused tests set `RG_ENABLED=1` explicitly.
- Audio SlowAPI key function now defers to the shared RG-aware resolver so SlowAPI remains a config carrier when RG ingress middleware is attached (prevents double-enforcement).
- RG e2e tests now install `RGSimpleMiddleware` by temporarily injecting it into `app.user_middleware` (avoids import-order dependence without `importlib.reload` and restores the stack after each test).
- MCP legacy limiter shadow comparisons now use `peek_allowed` only (no counter consumption), and `TokenBucketRateLimiter.peek_allowed` is side-effect-free.
- Added RG vs legacy shadow mismatch metrics for MCP and embeddings (emits `rg_shadow_decision_mismatch_total`).
- Updated `resource_governor_policies.yaml` defaults to include `api_key` scopes for ingress policies so RG middleware can govern API-key/JWT requests before auth deps resolve `user_id`.
- Added RG policies + `route_map.by_path` entries for SlowAPI-decorated `chatbooks` and `watchlists` endpoints to preserve enforcement when SlowAPI is treated as a config carrier.
- Moved tokens/day backfill queries into `AuthnzUsageRepo` (new `summarize_user_day` helper) and extended SQLite/Postgres repo tests.
- `RGSimpleMiddleware` now enforces `requests` only; tokens/streams are endpoint-level (reserve/commit).
- Chat and embeddings module-level RG helpers no longer reserve `requests` (ingress-only) to avoid double-enforcement; they reserve only specialized categories (primarily `tokens`) when units are available.
- Evaluations module reserves `evaluations` (+ optional `tokens`) via RG; `requests` is ingress-only to avoid double-enforcement (`test_rg_cutover_evals_authnz_character_web.py`).
- Added end-to-end RG 429/header parity tests for newly mapped domains: research, RAG, media, and prompt studio (`tldw_Server_API/tests/Resource_Governance/test_e2e_domains_headers.py`).
- Added a safety test ensuring known SlowAPI-decorated routes are covered by RG `route_map` so SlowAPI bypass cannot accidentally remove enforcement (`tldw_Server_API/tests/Resource_Governance/test_slowapi_decorated_routes_mapped.py`).
- `pytest -q tldw_Server_API/tests/Resource_Governance` passes.
- Added flashcards JSON-import override tests to ensure only principals with `FLASHCARDS_ADMIN` can set `max_items`/`max_field_length` (`tldw_Server_API/tests/AuthNZ_Unit/test_flashcards_admin_permissions_claims.py`).
- Added optimistic versioning support for RG policy deletes (`DELETE /api/v1/resource-governor/policy/{policy_id}?version=...`) with 409 conflict on mismatch (`tldw_Server_API/app/api/v1/endpoints/resource_governor.py`, `tldw_Server_API/app/core/Resource_Governance/policy_admin.py`).
- Deleted a stale legacy backup endpoint file so `rg "require_admin\\("` only hits the intended shims (`tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production.py.backup` removed).
- Added missing example policies for default module-level `*_POLICY_ID` values (AuthNZ, Character Chat, Web Scraping, Embeddings Server) so enabling RG in file-store mode doesn’t fail closed due to missing policy IDs (`tldw_Server_API/Config_Files/resource_governor_policies.yaml`).
- Made AuthNZ and Character Chat rate limiters RG-primary (legacy counters are fallback-only) and added shadow mismatch metrics where applicable (`tldw_Server_API/app/core/AuthNZ/rate_limiter.py`, `tldw_Server_API/app/core/Character_Chat/character_rate_limiter.py`).

## Stage 10: Auth Deps Hardening (Logging + RL)
**Goal**: Address auth_deps review items: fail loud on sqlite commit errors in the test DB adapter, sanitize auth exception logging, and ensure admin rate-limit bypass is gated on canonical AUTH_MODE.
**Success Criteria**:
- SQLite commit errors in the test adapter are logged and re-raised.
- Production logs avoid raw exception messages for API-key/JWT failure paths; full stack traces only in TEST_MODE.
- Admin rate-limit bypass depends on `AUTH_MODE=single_user` (not PROFILE).
- Unit tests cover the above.
**Tests**:
- `pytest -q tldw_Server_API/tests/AuthNZ_Unit/test_auth_deps_hardening.py`
**Status**: Complete
