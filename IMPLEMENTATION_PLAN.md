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
**Status**: In Progress

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: In Progress
