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
### Baseline Notes
- The frozen baseline commit for this review is `ec30354a2`.
- The implementation files most relevant to Slice 1 were already dirty at review start: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`, and `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`.
- The findings below were checked against the frozen baseline with `git show ec30354a2:...`; the Slice 1 issues recorded here are present in the baseline, not introduced only by the current dirty tree.
- The focused pytest run did not complete cleanly because `tldw_Server_API/tests/Evaluations/test_evaluations_unified.py` currently errors during fixture setup in `Evaluations_DB` A/B-test store initialization due to a trusted-path rejection for temp DB files. That failure is outside the Slice 1 endpoint/auth surface and is recorded as verification context, not as a Slice 1 finding.
### Control and Data Flow Notes
- Router surface: the Slice 1 router is `APIRouter(prefix="/evaluations", tags=["evaluations"])` in `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`, then mounted under `/api/v1` by the main app. Slice 1 directly owns `/health`, `/metrics`, `/rate-limits`, `/geval`, `/rag`, `/response-quality`, `/propositions`, `/batch`, `/ocr`, `/ocr-pdf`, `/history`, and the admin idempotency cleanup route. It also reviews the inclusion/auth surface for the nested CRUD, datasets, benchmarks, recipes, synthetic, webhooks, RAG pipeline, and embeddings A/B routers, but not the downstream business logic for those routers, which is deferred to later slices.
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
### Verification Run
- `git show ec30354a2:tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py | sed -n '90,280p'`
  `git show ec30354a2:tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py | sed -n '150,240p'`
  `git show ec30354a2:tldw_Server_API/app/core/Evaluations/user_rate_limiter.py | sed -n '298,360p'`
  `git show ec30354a2:tldw_Server_API/app/core/Evaluations/user_rate_limiter.py | sed -n '838,870p'`
  Result: baseline verification for the recorded Slice 1 findings. These baseline snapshots matched the current-tree guard paths relevant to the findings: single-user auth still returns the raw token, the multi-user `TEST_MODE` shortcut is still present, and the success-path limiter metadata still omits a concrete per-minute remaining value.
- `source .venv/bin/activate && rg -n "except Exception|_is_test_mode|pytest|TEST|fallback|record_byok_missing_credentials|HTTPException|require_eval_permissions|check_evaluation_rate_limit" tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_auth.py tldw_Server_API/app/core/Evaluations/user_rate_limiter.py`
  Result: identified the Slice 1 guard-heavy branches for manual review, including pytest/test-mode bypasses, BYOK credential checks, the diagnostics-only route limiter shim, and broad exception handling in auth/header paths.
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Evaluations/test_evaluations_stage1_route_and_error_regressions.py tldw_Server_API/tests/Evaluations/test_evaluations_unified.py tldw_Server_API/tests/AuthNZ/unit/test_evaluations_auth_runtime_guards.py tldw_Server_API/tests/AuthNZ/integration/test_evaluations_permissions_claims.py tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_evaluations_invariants.py`
  Result: mixed signal. `test_evaluations_stage1_route_and_error_regressions.py`, `test_evaluations_auth_runtime_guards.py`, and `test_evaluations_permissions_claims.py` passed; two invariant tests skipped; `test_evaluations_unified.py` errored repeatedly during fixture setup before endpoint assertions ran because `Evaluations_DB` initialization now rejects temporary embeddings A/B test DB paths outside trusted roots (`InvalidStoragePathError("invalid_path")` from `db_path_utils.resolve_trusted_database_path`). This is useful environmental/baseline context but is outside the Slice 1 auth/API findings recorded above.
- `source .venv/bin/activate && python - <<'PY'`
  `import asyncio, os`
  `from starlette.requests import Request`
  `from fastapi import HTTPException`
  `from fastapi.security import HTTPAuthorizationCredentials`
  `from tldw_Server_API.app.api.v1.endpoints.evaluations import evaluations_auth as eval_auth`
  `from tldw_Server_API.app.core.AuthNZ.settings import reset_settings`
  `def mkreq(headers):`
  `    return Request({'type':'http','method':'GET','path':'/api/v1/evaluations/geval','headers':headers,'client':('127.0.0.1',1234),'scheme':'http','query_string':b'','server':('testserver',80)})`
  `async def main():`
  `    os.environ['AUTH_MODE']='multi_user'; os.environ['TEST_MODE']='true'; os.environ['PYTEST_CURRENT_TEST']='manual::evals'; os.environ['SINGLE_USER_API_KEY']='primary-key-123456'; reset_settings()`
  `    req=mkreq([(b'authorization', b'Bearer primary-key-123456')])`
  `    creds=HTTPAuthorizationCredentials(scheme='Bearer', credentials='primary-key-123456')`
  `    user_ctx=await eval_auth.verify_api_key(credentials=creds, x_api_key=None, request=req); print('verify_api_key=', user_ctx)`
  `    try: await eval_auth.get_eval_request_user(req, _user_ctx=user_ctx, api_key=None, token='primary-key-123456', legacy_token_header=None)`
  `    except HTTPException as exc: print('get_eval_request_user_http_exception=', exc.status_code, exc.detail)`
  `    os.environ['AUTH_MODE']='single_user'; os.environ['TEST_MODE']='false'; reset_settings()`
  `    req2=mkreq([(b'x-api-key', b'primary-key-123456')])`
  `    single_ctx=await eval_auth.verify_api_key(credentials=None, x_api_key='primary-key-123456', request=req2); print('single_user_verify_api_key=', single_ctx)`
  `asyncio.run(main())`
  `PY`
  Result: this reproducible manual auth-branch probe confirmed two concrete Slice 1 behaviors: multi-user `TEST_MODE` returned `verify_api_key= test_user` but `get_eval_request_user` still failed with `401 Invalid API key`, and single-user `verify_api_key` returned the raw API key string (`single_user_verify_api_key= primary-key-123456`).
### Slice Status
- reviewed

## Slice 2: Core Orchestration and Execution
### Files Reviewed
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`
- `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`
- `tldw_Server_API/app/core/Evaluations/eval_runner.py`
- `tldw_Server_API/app/core/Evaluations/ms_g_eval.py`
- `tldw_Server_API/app/core/Evaluations/rag_evaluator.py`
- `tldw_Server_API/app/core/Evaluations/response_quality_evaluator.py`
### Baseline Notes
- The frozen baseline commit for this review is `ec30354a2`.
- The core Slice 2 implementation files were already dirty at review start, including `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`. The batch route file `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py` was also already dirty at review start and materially affects one Slice 2 finding below.
- The orchestration baseline in `eval_runner.py` and `unified_evaluation_service.py` was checked against `git show ec30354a2:...` before classifying findings. The batch route/service keyword mismatch recorded below is not present in the frozen baseline route and is therefore working-tree-specific.
### Control and Data Flow Notes
- Foreground and background run orchestration split in `UnifiedEvaluationService.create_run()` and `_run_evaluation_async()`. `create_run()` persists the run row, spawns a detached `asyncio.create_task(...)`, and returns immediately; `_run_evaluation_async()` then registers the current task in `runner.running_tasks`, calls `runner.run_evaluation(..., background=False)` through the circuit breaker, and emits lifecycle webhooks on completion, failure, or cancellation.
- The runner’s execution path is `EvaluationRunner.run_evaluation()` into `_execute_evaluation()`. Standard runs load the evaluation, fetch samples, choose the evaluator via `_get_evaluation_function()`, then process samples batch-by-batch through `_process_batch()`. `model_graded/rag_pipeline` is a separate orchestration branch that bypasses `_process_batch()` and manages its own config-grid progress accounting.
- Evaluator routing for the model-graded family depends on `eval_spec["sub_type"]`: missing/empty sub-types default to summarization in the runner, while CRUD creation in `UnifiedEvaluationService.create_evaluation()` maps `geval`, `rag`, and `response_quality` into `model_graded` plus fixed sub-types.
- Timeout and concurrency semantics are layered. `EvaluationRunner` has a service-wide semaphore plus a per-batch semaphore. `_process_batch()` applies `asyncio.wait_for(...)` per sample, not per batch or per run, so long batches can exceed `timeout_seconds` overall as long as each individual sample finishes before its own timeout.
- The direct one-off evaluation helpers in `UnifiedEvaluationService` (`evaluate_geval`, `evaluate_rag`, `evaluate_response_quality`) do not share the runner’s batching or timeout logic. They execute evaluator calls directly, persist ad hoc results, and optionally schedule completion webhooks inline in test mode or as detached tasks otherwise.
- Cross-evaluator helper behavior is not uniform. `ms_g_eval.run_geval()` has a built-in `test_` API-key shortcut that returns mock data synchronously, while `RAGEvaluator.evaluate()` and `ResponseQualityEvaluator.evaluate()` fan out internal metric checks with `asyncio.gather(...)` and absorb many metric-level failures into score-shaped responses rather than surfacing orchestration errors.
### Findings
1. Severity: High
   Confidence: High
   Priority: Immediate
   Applicability: Baseline
   Why it matters: `UnifiedEvaluationService.cancel_run()` treats any run that exists but is no longer present in `runner.running_tasks` as cancellable and unconditionally rewrites its DB status to `cancelled`. That means completed or failed runs can be retroactively relabeled as cancelled, and any caller receives a success response even though no running task was actually stopped. This corrupts run terminal state, audit meaning, and any downstream logic that relies on completed versus cancelled semantics.
   File references: `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:616`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:620`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:624`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:626`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:628`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:632`, `tldw_Server_API/app/core/Evaluations/eval_runner.py:2364`, `tldw_Server_API/app/core/Evaluations/eval_runner.py:2366`, `tldw_Server_API/app/core/Evaluations/eval_runner.py:2372`
   Recommended fix: Make `cancel_run()` state-aware before the DB fallback. If `runner.cancel_run(run_id)` returns false, load the current run state and only apply a direct status transition when the run is still in a cancellable pre-terminal state and the fallback is explicitly meant to cover a verified startup window. Completed or failed runs should return a non-success result without mutating status, and audit logging should only record cancellation when a real state transition occurred.
   Recommended tests: Add a unit regression proving `cancel_run()` on a completed run returns false or a no-op result and leaves the stored status unchanged. Add a second async regression that exercises the intended fallback path for a truly running-but-not-yet-registered task so the fix does not break legitimate cancellation behavior.
   Verification note: The frozen baseline at `ec30354a2` has the same fallback logic. A targeted manual probe with a completed-run stub and `runner.cancel_run(...) -> False` returned `ok=True` and captured `update_run_status('run_done', 'cancelled')`, confirming terminal-state corruption without needing the full background-run stack.
2. Severity: Medium
   Confidence: High
   Priority: Near-term
   Applicability: Working-tree-specific
   Why it matters: The current batch route now passes `webhook_user_id=` into `evaluate_geval()`, `evaluate_rag()`, and `evaluate_response_quality()`, but the focused Slice 2 regression test still patches a service double that follows the older keyword contract. That means the test harness now fails with a 500 `TypeError` before it can exercise strict fail-fast semantics. The evidence supports a working-tree verification and test-double contract mismatch, not a confirmed production break in the default `UnifiedEvaluationService` wiring.
   File references: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1540`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1550`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1562`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1759`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1769`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1781`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:640`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:756`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:861`
   Recommended fix: Re-stabilize the batch route verification contract in one place. Either update the route-facing test doubles and any alternative injected service shims to accept the new optional `webhook_user_id` keyword, or add a compatibility wrapper around the batch route’s service calls so verification scaffolds do not break when optional webhook identity wiring changes.
   Recommended tests: Keep `tldw_Server_API/tests/Evaluations/test_evaluations_stage3_batch_failfast_and_metrics_none.py` as the regression guard, but update its service double to match the supported keyword contract so it can keep asserting strict fail-fast behavior. Add a dedicated batch-route test that patches a minimal service double with the supported kwargs and verifies the route returns the expected non-500 fail-fast response.
   Verification note: `git show ec30354a2:tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py` shows the baseline batch route passed only `user_id=user_id` to these service helpers. The current dirty-tree route adds `webhook_user_id=batch_webhook_user_id`, while both the baseline and current `UnifiedEvaluationService.evaluate_*` methods already accept `webhook_user_id`. The focused pytest failure therefore demonstrates a working-tree test-double/caller contract mismatch rather than a baseline service implementation bug.
### Open Questions
- Needs verification: beyond the now-proven blind DB fallback in `cancel_run()`, there may be a narrower startup race between `UnifiedEvaluationService.create_run()` and `_run_evaluation_async()` task registration. `create_run()` detaches `_run_evaluation_async()` with `asyncio.create_task(...)` before any durable task handle is stored, while `_run_evaluation_async()` only registers `runner.running_tasks[run_id]` after the spawned task starts running. File references: `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:493`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:515`. I did not promote this narrower window into Findings because the current environment made clean end-to-end reproduction noisy; it should be validated with a targeted async regression test and then either folded into the cancellation fix above or dismissed as benign scheduling behavior.
### Verification Run
- `git show ec30354a2:tldw_Server_API/app/core/Evaluations/eval_runner.py | sed -n '240,1405p'`
  `git show ec30354a2:tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py | sed -n '430,940p'`
  Result: baseline verification for the runner/service orchestration paths. The baseline already uses detached background run startup, the same `cancel_run()` DB fallback when `runner.cancel_run(...)` returns false, per-sample timeouts in `_process_batch()`, and service helper signatures that accept optional `webhook_user_id`.
- `source .venv/bin/activate && rg -n "asyncio|Semaphore|timeout|running_tasks|background|create_task|gather|CancelledError|eval_timeout" tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py tldw_Server_API/app/core/Evaluations/eval_runner.py`
  Result: identified the Slice 2 orchestration hotspots requested in the task, including detached background run startup (`create_task`), task bookkeeping via `running_tasks`, per-sample timeout enforcement in `_process_batch()`, dual semaphore usage, `asyncio.gather(...)` fan-out, and shutdown/cancellation handling.
- `git show ec30354a2:tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py | nl -ba | sed -n '616,632p'`
  `git show ec30354a2:tldw_Server_API/app/core/Evaluations/eval_runner.py | nl -ba | sed -n '2364,2372p'`
  `source .venv/bin/activate && python - <<'PY'`
  `import asyncio`
  `from types import SimpleNamespace`
  `from tldw_Server_API.app.core.Evaluations import unified_evaluation_service as svc_mod`
  `from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import UnifiedEvaluationService`
  `async def main():`
  `    svc_mod.log_run_cancelled_async = lambda **kwargs: asyncio.sleep(0)`
  `    svc = UnifiedEvaluationService(db_path='Databases/evals_slice2_probe.db', enable_webhooks=False)`
  `    calls = []`
  `    svc.db = SimpleNamespace(get_run=lambda run_id, created_by=None: {'id': run_id, 'status': 'completed'}, update_run_status=lambda run_id, status, error_message=None: calls.append((run_id, status, error_message)))`
  `    svc.runner = SimpleNamespace(cancel_run=lambda run_id: False)`
  `    ok = await svc.cancel_run('run_done', cancelled_by='tester', created_by='tester')`
  `    print('ok=', ok)`
  `    print('calls=', calls)`
  `asyncio.run(main())`
  `PY`
  Result: the baseline and current files both show `cancel_run()` falling back to `self.db.update_run_status(run_id, "cancelled")` whenever the runner reports no in-flight task. The isolated probe returned `ok= True` and `calls= [('run_done', 'cancelled', None)]`, confirming that a completed run can be rewritten to `cancelled` without stopping any running task.
- `git show ec30354a2:tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py | nl -ba | sed -n '1520,1775p'`
  `nl -ba tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py | sed -n '1528,1795p'`
  `git show ec30354a2:tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py | nl -ba | sed -n '640,930p'`
  `nl -ba tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py | sed -n '640,930p'`
  Result: confirmed the route/service keyword mismatch classification. The frozen baseline batch route did not pass `webhook_user_id` into `evaluate_geval()` / `evaluate_rag()` / `evaluate_response_quality()`, while the current dirty-tree route does. Both baseline and current service methods already accept that keyword, so the contract drift is in the dirty-tree caller surface rather than the baseline service implementation.
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Evaluations/unit/test_eval_runner.py tldw_Server_API/tests/Evaluations/unit/test_unified_evaluation_service_mapping.py tldw_Server_API/tests/Evaluations/test_evaluations_stage3_batch_failfast_and_metrics_none.py tldw_Server_API/tests/Evaluations/test_eval_test_mode_truthiness.py`
  Result: `21 passed, 1 failed`. The failing test was `tldw_Server_API/tests/Evaluations/test_evaluations_stage3_batch_failfast_and_metrics_none.py::test_batch_parallel_strict_fail_fast_cancels_remaining`, which returned `500` instead of `200`. Captured error: `Batch evaluation failed: test_batch_parallel_strict_fail_fast_cancels_remaining.<locals>._Service.evaluate_geval() got an unexpected keyword argument 'webhook_user_id'`.
### Slice Status
- reviewed

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
