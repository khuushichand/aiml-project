# Evals Module Review

## Baseline Snapshot
- Frozen review baseline commit (short HEAD at review start): `ec30354a2`
- Dirty Evals-related files at review start:
  - `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py`
  - `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_benchmarks.py`
  - `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`
  - `tldw_Server_API/app/core/Evaluations/db_adapter.py`
  - `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`
  - `tldw_Server_API/app/core/Evaluations/webhook_manager.py`
  - `tldw_Server_API/app/core/Evaluations/webhook_security.py`
  - `tldw_Server_API/tests/AuthNZ/integration/test_jwt_refresh_rotation_blacklist.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_api_key_manager_validation.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_auth_endpoints_extended.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_evaluations_auth_runtime_guards.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_jwt_service.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_session_manager_configured_key.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_user_db_handling_api_keys.py`
  - `tldw_Server_API/tests/Evaluations/test_evaluations_audit_adapter.py`
  - `tldw_Server_API/tests/Evaluations/test_evaluations_stage1_route_and_error_regressions.py`
  - `tldw_Server_API/tests/Evaluations/unit/test_unified_evaluation_service_mapping.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_mfa_backend_support.py`
  - `tldw_Server_API/tests/Evaluations/unit/test_webhook_manager_backend_schema.py`

## Scope and Slice Order
1. Unified API and auth surface
2. Core orchestration and execution
3. Persistence and state management
4. CRUD and run lifecycle endpoints
5. Retrieval and recipe-driven evaluation surfaces
6. Benchmark, dataset, and synthetic evaluation surfaces
7. Embeddings A/B and webhook surfaces
8. Cross-slice contract synthesis

## Review Method
- findings before improvements
- uncertain items labeled `needs verification` in `Confidence` and/or `Verification note`
- working-tree-specific findings labeled explicitly

### Finding Schema
Use this exact structure for every later finding entry:

```markdown
1. Severity: High
   Confidence: High
   Priority: Immediate
   Applicability: Baseline
   Why it matters: ...
   File references: `path/to/file.py:line`
   Recommended fix: ...
   Recommended tests: ...
   Verification note: ...
```

Applicability values: `Baseline`, `Working-tree-specific`, `Mixed`.
`Mixed` means the finding spans both baseline and working-tree-specific scope.
Uncertainty belongs in `Confidence` and/or `Verification note`, not `Applicability`.

### Confidence Model
- High: directly observed in the current file set or verified with targeted evidence.
- Medium: supported by strong code-path evidence, but one or more assumptions still need confirmation.
- Low: tentative or inferred from surrounding context and should be treated as `needs verification` in the confidence or verification fields.

## Severity and Priority Model
- Critical / High / Medium / Low
- Immediate / Near-term / Later

## Slice 1: Unified API and Auth Surface
### Files Reviewed
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py`
- `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`
- `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py`
- `tldw_Server_API/app/api/v1/schemas/evaluation_schemas_unified.py`
- `tldw_Server_API/tests/Evaluations/test_evaluations_stage1_route_and_error_regressions.py`
- `tldw_Server_API/tests/Evaluations/test_evaluations_unified.py`
- `tldw_Server_API/tests/AuthNZ/unit/test_evaluations_auth_runtime_guards.py`
- `tldw_Server_API/tests/AuthNZ/integration/test_evaluations_permissions_claims.py`
- `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_evaluations_invariants.py`
### Baseline Notes
- The frozen baseline commit for this review is `ec30354a2`.
- The implementation files most relevant to Slice 1 were already dirty at review start: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`, and `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`.
- The findings below were checked against the frozen baseline with `git show ec30354a2:...`; the Slice 1 issues recorded here are present in the baseline, not introduced only by the current dirty tree.
- The focused pytest run did not complete cleanly because `tldw_Server_API/tests/Evaluations/test_evaluations_unified.py` currently errors during fixture setup in `Evaluations_DB` A/B-test store initialization due trusted-path rejection for temp DB files. That failure is outside the Slice 1 endpoint/auth surface and is recorded as verification context, not as a Slice 1 finding.
### Control and Data Flow Notes
- Router surface: the Slice 1 router is `APIRouter(prefix="/evaluations", tags=["evaluations"])` in `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`, then mounted under `/api/v1` by the main app. Slice 1 directly owns `/health`, `/metrics`, `/rate-limits`, `/geval`, `/rag`, `/response-quality`, `/propositions`, `/batch`, `/ocr`, `/ocr-pdf`, `/history`, the admin idempotency cleanup route, and the top-level router inclusions for CRUD, datasets, benchmarks, recipes, synthetic, webhooks, RAG pipeline, and embeddings A/B test surfaces.
- Current-user resolution is split across two helpers in `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py`: `verify_api_key()` authenticates and returns a string context (`test_user`, `user_<id>`, or in single-user mode the raw API token), while `get_eval_request_user()` independently re-resolves the `User` object from request headers and bearer token. Several routes depend on both helpers at once.
- Permission and role checks are layered rather than centralized. `require_eval_permissions()` reads `current_user.roles` and `current_user.permissions` from `get_eval_request_user()`, while heavy-eval admin gating uses `AuthPrincipal` claims via `_get_admin_principal_if_needed()` plus `enforce_heavy_evaluations_admin()`. The `/history` route mixes both systems in one handler by comparing requested user ids against `current_user` and then consulting `principal.roles`/`principal.permissions` for cross-user access.
- Heavy-eval admin gating is currently attached to `/admin/idempotency/cleanup` through `Depends(_get_admin_principal_if_needed)` plus an in-handler `enforce_heavy_evaluations_admin(principal)` call. The helper is disabled entirely when `EVALS_HEAVY_ADMIN_ONLY` is false, so the dependency path and the enforcement path both branch on the same env flag.
- Provider credential validation for `geval`, `rag`, and `response_quality` flows uses `_resolve_and_validate_eval_provider()`, which resolves BYOK credentials from the current user and request, ignores per-request `api_key` overrides, and raises a 503 after `record_byok_missing_credentials()` when a provider requires credentials and none are available outside test mode. Batch evaluation reimplements a parallel variant of this logic in `_extract_provider_and_key()`.
- Rate limiting is also layered. `check_evaluation_rate_limit()` is now a diagnostics-only dependency shim and never blocks requests by itself; actual enforcement happens inside route handlers through `get_user_rate_limiter_for_user(...).check_rate_limit(...)`. Response headers are added later through `_apply_rate_limit_headers(...)`, which depends on limiter summary data plus optional `meta` fields from the enforcement step.
- Test-only and test-mode branches exist in both auth and evaluation execution paths. `verify_api_key()` and `get_eval_request_user()` have explicit pytest-gated `TESTING` and `TEST_MODE` bypass branches. `_is_eval_test_mode()` in `evaluations_unified.py` weakens provider-credential enforcement and turns webhook dispatch from background tasks into awaited inline calls. `get_user_rate_limiter_for_user()` also falls back to a shared global limiter whenever test mode or `PYTEST_CURRENT_TEST` is present.
### Findings
1. Severity: High
   Confidence: High
   Priority: Immediate
   Applicability: Baseline
   Why it matters: In single-user mode, the limiter subject for evaluations is the raw API key string, not the stable user id. That writes the secret token into limiter state, makes `/rate-limits` reflect token-scoped rather than user-scoped usage, and lets a rotated single-user API key start with a fresh quota ledger even though it is still the same account.
   File references: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py:147`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py:163`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:640`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:646`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:785`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:792`, `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py:301`
   Recommended fix: Normalize the limiter/audit/rate-limit subject to the stable authenticated user id everywhere in Slice 1. `verify_api_key()` can continue returning an auth context token if needed for compatibility, but route handlers should pass `current_user.id_str or str(current_user.id)` into rate-limit reads/writes and the rate-limit status endpoint should read usage for that stable id instead of the raw auth token.
   Recommended tests: Add a single-user regression test that calls an eval endpoint and `/rate-limits`, then asserts the limiter storage key is the stable user id rather than the configured API key. Add a second regression proving that rotating `SINGLE_USER_API_KEY` does not reset the same user's eval quota ledger.
   Verification note: Direct code-path review shows `verify_api_key()` returns the raw token in single-user mode, and Slice 1 routes pass that value into `check_rate_limit()`/`get_usage_summary()`. The frozen baseline at `ec30354a2` has the same behavior.

2. Severity: Medium
   Confidence: High
   Priority: Near-term
   Applicability: Baseline
   Why it matters: The multi-user `TEST_MODE` shortcut in `verify_api_key()` is internally inconsistent with `get_eval_request_user()`. Under explicit pytest runtime, `verify_api_key()` accepts a bearer equal to `SINGLE_USER_API_KEY` and returns `test_user`, but `get_eval_request_user()` still tries to resolve the same raw token as a real user credential and rejects it. That makes the advertised branch unusable for full request flows and creates misleading test-only behavior.
   File references: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py:166`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py:170`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py:246`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py:277`
   Recommended fix: Either remove the multi-user `TEST_MODE` bearer shortcut from `verify_api_key()` entirely, or teach `get_eval_request_user()` to honor the already-resolved `_user_ctx == "test_user"` branch under the same explicit pytest/runtime guard instead of re-authenticating the raw token.
   Recommended tests: Add an end-to-end runtime-guard test that exercises both helpers together in multi-user `TEST_MODE` with `SINGLE_USER_API_KEY` as bearer and asserts either a consistent allow path or a consistent reject path.
   Verification note: Manual runtime verification in the project venv produced `verify_api_key= test_user` followed by `get_eval_request_user_http_exception= 401 Invalid API key`. The frozen baseline at `ec30354a2` has the same branch structure.

3. Severity: Low
   Confidence: High
   Priority: Later
   Applicability: Baseline
   Why it matters: Successful eval responses can emit misleading per-minute rate-limit headers. `_apply_rate_limit_headers()` defaults `X-RateLimit-PerMinute-Remaining` to `0` whenever `meta["requests_remaining"]` is absent, but the allowed-path metadata returned by `UserRateLimiter.check_rate_limit()` usually omits that field. Clients that trust the headers can treat successful requests as quota exhaustion and back off unnecessarily.
   File references: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py:342`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py:355`, `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py:335`, `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py:353`, `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py:358`, `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py:365`
   Recommended fix: Stop defaulting missing per-minute metadata to zero. Either compute remaining requests from limiter summary data, or omit the per-minute remaining header when the enforcement backend does not provide a trustworthy value.
   Recommended tests: Add header-level assertions for one RG-backed allow response and one legacy-cost-only allow response, verifying that success responses do not advertise `X-RateLimit-PerMinute-Remaining: 0` unless the request is actually exhausted.
   Verification note: Baseline inspection shows `_apply_rate_limit_headers()` only gets a concrete per-minute remaining value from `meta`, while the success metadata returned by `check_rate_limit()` does not populate that field.
### Open Questions
- None.
### Verification Run
- `source .venv/bin/activate && rg -n "except Exception|_is_test_mode|pytest|TEST|fallback|record_byok_missing_credentials|HTTPException|require_eval_permissions|check_evaluation_rate_limit" tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py tldw_Server_API/app/core/Evaluations/user_rate_limiter.py`
  Result: identified the Slice 1 guard-heavy branches for manual review, including pytest/test-mode bypasses, BYOK credential checks, the diagnostics-only route limiter shim, and broad exception handling in auth/header paths.
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Evaluations/test_evaluations_stage1_route_and_error_regressions.py tldw_Server_API/tests/Evaluations/test_evaluations_unified.py tldw_Server_API/tests/AuthNZ/unit/test_evaluations_auth_runtime_guards.py tldw_Server_API/tests/AuthNZ/integration/test_evaluations_permissions_claims.py tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_evaluations_invariants.py`
  Result: mixed signal. `test_evaluations_stage1_route_and_error_regressions.py`, `test_evaluations_auth_runtime_guards.py`, and `test_evaluations_permissions_claims.py` passed; two invariant tests skipped; `test_evaluations_unified.py` errored repeatedly during fixture setup before endpoint assertions ran because `Evaluations_DB` initialization now rejects temporary embeddings A/B test DB paths outside trusted roots (`InvalidStoragePathError("invalid_path")` from `db_path_utils.resolve_trusted_database_path`). This is useful environmental/baseline context but is outside the Slice 1 auth/API findings recorded above.
- `source .venv/bin/activate && python - <<'PY' ... PY`
  Result: manual auth-branch probe confirmed two concrete Slice 1 behaviors: multi-user `TEST_MODE` returned `verify_api_key= test_user` but `get_eval_request_user` still failed with `401 Invalid API key`, and single-user `verify_api_key` returned the raw API key string (`single_user_verify_api_key= primary-key-123456`).
### Slice Status
- reviewed

## Slice 2: Core Orchestration and Execution
### Files Reviewed
### Baseline Notes
### Control and Data Flow Notes
### Findings
### Open Questions
### Verification Run
### Slice Status

## Slice 3: Persistence and State Management
### Files Reviewed
### Baseline Notes
### Control and Data Flow Notes
### Findings
### Open Questions
### Verification Run
### Slice Status

## Slice 4: CRUD and Run Lifecycle Endpoints
### Files Reviewed
### Baseline Notes
### Control and Data Flow Notes
### Findings
### Open Questions
### Verification Run
### Slice Status

## Slice 5: Retrieval and Recipe-Driven Evaluation Surfaces
### Files Reviewed
### Baseline Notes
### Control and Data Flow Notes
### Findings
### Open Questions
### Verification Run
### Slice Status

## Slice 6: Benchmark, Dataset, and Synthetic Evaluation Surfaces
### Files Reviewed
### Baseline Notes
### Control and Data Flow Notes
### Findings
### Open Questions
### Verification Run
### Slice Status

## Slice 7: Embeddings A/B and Webhook Surfaces
### Files Reviewed
### Baseline Notes
### Control and Data Flow Notes
### Findings
### Open Questions
### Verification Run
### Slice Status

## Slice 8: Cross-Slice Contract Synthesis
### Shared Schemas and Config
### Cross-Slice Systemic Issues
### Priority Summary
### Recommended Remediation Order
### Coverage Gaps and Verification Items
### Verification Run
### Slice Status
