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
- `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`
- `tldw_Server_API/app/core/Evaluations/eval_runner.py`
- `tldw_Server_API/app/core/Evaluations/ms_g_eval.py`
- `tldw_Server_API/app/core/Evaluations/rag_evaluator.py`
- `tldw_Server_API/app/core/Evaluations/response_quality_evaluator.py`
### Baseline Notes
- The frozen baseline commit for this review is `ec30354a2`.
- The core Slice 2 implementation files were already dirty at review start, including `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`. The batch route file `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py` was also already dirty at review start and materially affects one Slice 2 verification item below.
- The orchestration baseline in `eval_runner.py` and `unified_evaluation_service.py` was checked against `git show ec30354a2:...` before classifying findings. The batch route/service keyword mismatch recorded under `Open Questions` is not present in the frozen baseline route and is therefore working-tree-specific.
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
### Open Questions
- Needs verification: beyond the now-proven blind DB fallback in `cancel_run()`, there may be a narrower startup race between `UnifiedEvaluationService.create_run()` and `_run_evaluation_async()` task registration. `create_run()` detaches `_run_evaluation_async()` with `asyncio.create_task(...)` before any durable task handle is stored, while `_run_evaluation_async()` only registers `runner.running_tasks[run_id]` after the spawned task starts running. File references: `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:493`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:515`. I did not promote this narrower window into Findings because the current environment made clean end-to-end reproduction noisy; it should be validated with a targeted async regression test and then either folded into the cancellation fix above or dismissed as benign scheduling behavior.
- Needs verification: the current dirty-tree batch route now passes `webhook_user_id=` into `evaluate_geval()`, `evaluate_rag()`, and `evaluate_response_quality()`, while the focused Slice 2 regression test still patches a service double that follows the older keyword contract. That causes the test harness to fail with a 500 `TypeError` before it can exercise strict fail-fast semantics. File references: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1540`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1550`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1562`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1759`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1769`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py:1781`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:640`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:756`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:861`. I kept this out of Findings because the current evidence shows a working-tree test-double/caller mismatch, not a confirmed production break in the default `UnifiedEvaluationService` wiring. It should remain a verification gap until a real runtime consumer besides the focused test scaffold is shown to depend on the older call shape.
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
- `tldw_Server_API/app/core/Evaluations/evaluation_manager.py`
- `tldw_Server_API/app/core/Evaluations/db_adapter.py`
- `tldw_Server_API/app/core/Evaluations/connection_pool.py`
- `tldw_Server_API/app/core/Evaluations/audit_adapter.py`
- `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- `tldw_Server_API/app/core/DB_Management/db_path_utils.py`
### Baseline Notes
- The slice-3 persistence code is baseline-stable relative to `ec30354a2`.
- The `tldw_Server_API/tests/Evaluations/unit/test_evaluation_manager.py` setup failure caused by `resolve_trusted_database_path()` rejecting the temp DB path reproduces against the frozen baseline path logic, so the temp-path issue recorded below is baseline behavior rather than a dirty-tree regression.
### Control and Data Flow Notes
- `EvaluationManager._get_db_path()` resolves the default evaluations DB from `DatabasePaths`, but the explicit `db_path` branch returns any resolved path after null-byte stripping and does not apply the same user-directory containment check used for config-driven paths.
- Config-driven `evaluations_db_path` values are contained with `relative_to(base_resolved)` and fall back to the default path when they escape the user directory.
- `BackendAdapter` routes unified backends through the shared `DatabaseBackend` abstraction, but `fetch_one()` and `fetch_value()` currently surface `QueryResult.first` / `QueryResult.scalar` as attributes instead of calling the accessors.
- `EvaluationManager.store_evaluation()` writes to `internal_evaluations` and `evaluation_metrics`; `get_history()` filters by type/date and computes aggregates; `list_evaluations()` is session-scoped and clears `_recent_created_ids` after each readback.
### Findings
1. Severity: High
   Confidence: High
   Priority: Immediate
   Applicability: Baseline
   Why it matters: The explicit `db_path` constructor path bypasses the containment rule that protects config-driven evaluations paths. A caller can pass an absolute path outside the per-user database tree and `EvaluationManager` will accept it after `resolve()`, which defeats the path-safety model used everywhere else in this slice.
   File references: `tldw_Server_API/app/core/Evaluations/evaluation_manager.py:46`, `tldw_Server_API/app/core/Evaluations/evaluation_manager.py:51`, `tldw_Server_API/app/core/Evaluations/evaluation_manager.py:62`, `tldw_Server_API/app/core/Evaluations/evaluation_manager.py:65`, `tldw_Server_API/app/core/Evaluations/evaluation_manager.py:70`
   Recommended fix: Apply the same containment check used for config-driven paths to the explicit `db_path` branch, or reject explicit paths that do not resolve under the user base directory / trusted roots.
   Recommended tests: Add a regression that instantiates `EvaluationManager` with an explicit path outside the user tree and asserts it is rejected or normalized back to the default per-user evaluations DB.
   Verification note: Baseline comparison with `git show ec30354a2:tldw_Server_API/app/core/Evaluations/evaluation_manager.py` shows the same explicit-path branch. A targeted probe with `_init_database` patched out and `Path.mkdir` intercepted produced `resolved_db_path=/Users/appledev/Documents/escape/evals.db` and `mkdir_target=/Users/appledev/Documents/escape` for `EvaluationManager(db_path='../../escape/evals.db', user_id=1)`, confirming that the explicit branch escapes the user storage root before any trusted-path gate intervenes.

2. Severity: Medium
   Confidence: High
   Priority: Near-term
   Applicability: Baseline
   Why it matters: `resolve_trusted_database_path()` resolves trusted roots such as `tempfile.gettempdir()` to real paths like `/private/var/...`, but it compares them against a merely normalized candidate path that can remain on the symlinked alias `/var/...`. In macOS test contexts, that makes trusted temp DB paths fail containment checks even though both paths resolve to the same location. The failure is large enough to collapse the entire `test_evaluation_manager.py` suite during fixture setup before any persistence assertions run.
   File references: `tldw_Server_API/app/core/DB_Management/db_path_utils.py:145`, `tldw_Server_API/app/core/DB_Management/db_path_utils.py:152`, `tldw_Server_API/app/core/DB_Management/db_path_utils.py:161`, `tldw_Server_API/app/core/DB_Management/db_path_utils.py:165`, `tldw_Server_API/app/core/DB_Management/db_path_utils.py:170`, `tldw_Server_API/app/core/DB_Management/db_path_utils.py:177`
   Recommended fix: Resolve the candidate path with `strict=False` before containment checks so trusted roots and candidate paths are compared in the same canonical form. Keep the trusted-root policy, but normalize roots and candidates symmetrically.
   Recommended tests: Add a regression that passes a macOS-style `/var/...` temp path while `tempfile.gettempdir().resolve()` yields `/private/var/...` and assert the path is accepted. Keep a companion test proving that genuinely untrusted absolute paths are still rejected after canonicalization.
   Verification note: The frozen baseline has the same code shape. A direct probe showed `normalized.relative_to(root)` fails for `/var/...` against `/private/var/...`, while `normalized.resolve(strict=False).relative_to(root)` succeeds. The focused `python -m pytest -v tldw_Server_API/tests/Evaluations/unit/test_evaluation_manager.py` run then failed all 20 cases with `InvalidStoragePathError(\"invalid_path\")` from this trusted-path rejection.

3. Severity: High
   Confidence: High
   Priority: Immediate
   Applicability: Baseline
   Why it matters: `BackendAdapter.fetch_one()` and `BackendAdapter.fetch_value()` return bound methods instead of the underlying row/value data because `QueryResult.first` and `QueryResult.scalar` are accessed as attributes, not invoked. Any call site routed through the shared backend abstraction will get the wrong type and may fail in non-SQLite backend paths.
   File references: `tldw_Server_API/app/core/Evaluations/db_adapter.py:271`, `tldw_Server_API/app/core/Evaluations/db_adapter.py:279`
   Recommended fix: Call the `QueryResult` accessors (`result.first()` and `result.scalar()`) or normalize the backend result contract so the adapter always returns concrete rows/scalars.
   Recommended tests: Add unit coverage for `BackendAdapter.fetch_one()` and `BackendAdapter.fetch_value()` against a stub backend result object that exposes `first()` / `scalar()`, plus a backend-routing smoke test that exercises the adapter through the unified backend path.
   Verification note: `QueryResult` in the shared backend contract exposes `first()` and `scalar()` methods, so the current adapter code is returning callables. This is baseline code, not a dirty-tree change.
### Open Questions
- Needs verification: whether `list_evaluations()` is meant to be a session-isolated helper only. The current implementation clears `_recent_created_ids` after each readback, so it does not behave like a persistent “list all evaluations” API.
- Needs verification: `EvaluationManager._init_database()` silently falls back to `_init_database_fallback()` in non-production environments when migrations fail, creating a legacy schema instead of failing loudly. The code-path evidence is clear, but I did not promote it to a finding because I have not yet proven a supported runtime path still depends on this manager strongly enough for that fallback to mask a real migration failure in practice.
### Verification Run
- `git show ec30354a2:tldw_Server_API/app/core/DB_Management/db_path_utils.py | sed -n '120,210p'`
  `git show ec30354a2:tldw_Server_API/app/core/Evaluations/evaluation_manager.py | sed -n '1,140p'`
  Result: baseline path containment and migration fallback logic match the current tree, including the trusted-root set used by `resolve_trusted_database_path()` and the explicit-path branch in `EvaluationManager._get_db_path()`.
- `source .venv/bin/activate && rg -n "resolve|fallback|migrate|sqlite|postgres|db_path|relative_to|CREATE TABLE|OperationalError|RuntimeError" tldw_Server_API/app/core/Evaluations/evaluation_manager.py tldw_Server_API/app/core/Evaluations/db_adapter.py tldw_Server_API/app/core/Evaluations/connection_pool.py`
  Result: confirmed the Slice 3 hotspots for path resolution, migration fallback, SQLite-only fallbacks, and adapter/backend routing.
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Evaluations/unit/test_evaluation_manager.py`
  Result: `20 errors` from `InvalidStoragePathError: invalid_path` in the `temp_db_path` fixture while `EvaluationsDatabase` initialized its embeddings A/B store. The failing path normalized to `/var/folders/.../tmp*_test_eval.db` and was rejected by `resolve_trusted_database_path()`.
- `python - <<'PY'`
  `from pathlib import Path`
  `import tempfile, os`
  `root = Path(tempfile.gettempdir()).resolve()`
  `candidate = Path('/var/folders/qc/m53gw5bs70q_xf10fz52dlmw0000gn/T/tmpr6iu163l_test_eval.db')`
  `normalized = Path(os.path.normpath(str(candidate)))`
  `print('root=', root)`
  `print('normalized=', normalized)`
  `try: normalized.relative_to(root); print('contained=True')`
  `except Exception as exc: print('contained=False', type(exc).__name__)`
  `print('normalized_resolved=', normalized.resolve(strict=False))`
  `try: normalized.resolve(strict=False).relative_to(root); print('resolved_contained=True')`
  `except Exception as exc: print('resolved_contained=False', type(exc).__name__)`
  `PY`
  Result: reproduced the macOS temp-path alias failure directly. `root` resolved to `/private/var/...`, `normalized` stayed `/var/...`, `contained=False ValueError`, and `resolved_contained=True` once the candidate path was resolved before containment checking.
- `source .venv/bin/activate && python - <<'PY'`
  `from pathlib import Path`
  `from unittest.mock import patch`
  `from tldw_Server_API.app.core.Evaluations.evaluation_manager import EvaluationManager`
  `mkdir_calls = []`
  `def fake_mkdir(self, *args, **kwargs):`
  `    mkdir_calls.append(str(self))`
  `    return None`
  `with patch.object(EvaluationManager, '_init_database', lambda self: None):`
  `    with patch.object(Path, 'mkdir', fake_mkdir):`
  `        mgr = EvaluationManager(db_path='../../escape/evals.db', user_id=1)`
  `        print('resolved_db_path=', mgr.db_path)`
  `        print('mkdir_target=', mkdir_calls[-1] if mkdir_calls else None)`
  `PY`
  Result: reproduced the explicit-path escape without relying on sandbox denial. `EvaluationManager` resolved the path to `/Users/appledev/Documents/escape/evals.db` and attempted to create `/Users/appledev/Documents/escape`, confirming that the explicit-path branch bypasses the per-user containment policy.
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Evaluations/unit/test_evaluations_db_filters.py`
  Result: `2 passed`.
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Evaluations/test_evaluations_backend_dual.py`
  Result: `1 passed, 1 skipped`.
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Evaluations/test_evaluations_postgres_crud.py`
  Result: `1 passed, 1 skipped`.
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Evaluations/test_evaluations_migration_cli.py`
  Result: `1 skipped`.
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_evaluations_unified_and_crud.py`
  Result: `1 passed, 1 skipped`.
### Slice Status
- reviewed

## Slice 4: CRUD and Run Lifecycle Endpoints
### Files Reviewed
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_crud.py`
- `tldw_Server_API/app/api/v1/schemas/evaluation_schema.py`
- `tldw_Server_API/app/core/Evaluations/audit_adapter.py`
- `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`
### Baseline Notes
- `evaluations_crud.py` and `evaluation_schema.py` are baseline-stable relative to `ec30354a2`.
- `audit_adapter.py` and `unified_evaluation_service.py` have working-tree deltas, but the Slice 4 review surface here only needs the CRUD/run flow, audit, and backend-selection behavior they expose.
### Control and Data Flow Notes
- Evaluation creation and reads flow through `create_evaluation()`, `list_evaluations()`, and `get_evaluation()` in `evaluations_crud.py`, which all normalize to the stable authenticated user id before calling `UnifiedEvaluationService`.
- Run creation and retrieval flow through `create_run()`, `list_runs()`, `get_run()`, and `cancel_run()`. `create_run()` also forwards `webhook_user_id` into the service, which then emits run-start audit and webhook events from `unified_evaluation_service.py`.
- Pagination is cursor-based in the CRUD router (`limit` + `after`) for both evaluations and runs, while `evaluation_schema.py` also defines a separate history request model that uses `limit` + `offset`. That history model is not exercised by the CRUD handlers in this slice.
- Audit touchpoints are present for evaluation create/update/delete, run start/cancel, and export in `audit_adapter.py`, but the reviewed CRUD file does not expose an export endpoint, so export wiring is not verifiable end-to-end from this slice alone.
- User isolation is consistently passed via `created_by=stable_user_id` on CRUD reads/writes, and the service-level audit/webhook calls carry the same stable user identity through `log_*` helpers.
### Findings
1. Severity: Medium
   Confidence: High
   Priority: Near-term
   Applicability: Baseline
   Why it matters: `list_runs()` shadows the imported FastAPI `status` module with its `status` query parameter. If `svc.list_runs()` raises, the exception handler then tries to access `status.HTTP_500_INTERNAL_SERVER_ERROR` on the query argument instead of the module, which turns the intended HTTP 500 into an `AttributeError` and hides the real failure.
   File references: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_crud.py:349`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_crud.py:353`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_crud.py:364`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_crud.py:368`
   Recommended fix: Rename the query parameter to something like `run_status`, or alias the imported FastAPI status module to `http_status` in this file so the error path cannot collide with a request parameter.
   Recommended tests: Add a regression that forces `svc.list_runs()` to raise and asserts the router still returns a 500 error response instead of leaking an `AttributeError`.
   Verification note: A targeted probe patched `get_unified_evaluation_service_for_user()` with a stub that raises `ValueError("boom")`; calling `list_runs()` produced `AttributeError: 'Query' object has no attribute 'HTTP_500_INTERNAL_SERVER_ERROR'`, confirming the error-path breakage.
### Open Questions
- `evaluation_schema.py` defines `EvaluationHistoryRequest` with `limit`/`offset`, but this slice only exposes cursor-based evaluation/run listing. Confirm the intended history endpoint and whether the two pagination styles are deliberately split across different routes.
- `audit_adapter.py` exposes `log_evaluation_exported*`, but no export caller is present in the reviewed CRUD/service files. Confirm the export route wiring in the later slice before treating the audit hook as covered.
### Verification Run
- Hotspot scan: `source .venv/bin/activate && rg -n "status|history|page|limit|offset|user_id|owner|audit|export|run_id|evaluation_id" tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_crud.py tldw_Server_API/app/core/Evaluations/audit_adapter.py`
- Required tests: `python -m pytest -q tldw_Server_API/tests/Evaluations/test_evaluations_crud_create_run_api.py`
- Required tests: `python -m pytest -q tldw_Server_API/tests/Evaluations/test_evaluation_integration.py`
- Required tests: `python -m pytest -q tldw_Server_API/tests/Evaluations/test_evaluations_stage2_user_isolation_and_usage_accounting.py`
- Required tests: `python -m pytest -q tldw_Server_API/tests/DB_Management/test_evaluations_unified_and_crud.py`
- Result: all four required suites passed. The hotspot scan hit the expected CRUD/audit/history/pagination/user-id/export/run-id terms, and the targeted failure probe reproduced the `list_runs()` error-path `AttributeError`.
### Slice Status
- reviewed

## Slice 5: Retrieval and Recipe-Driven Evaluation Surfaces
### Files Reviewed
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py`
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_recipes.py`
- `tldw_Server_API/app/api/v1/schemas/evaluation_recipe_schemas.py`
- `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py`
- `tldw_Server_API/app/core/DB_Management/db_path_utils.py`
- `tldw_Server_API/app/core/Evaluations/eval_runner.py`
- `tldw_Server_API/app/core/Evaluations/rag_evaluator.py`
- `tldw_Server_API/app/core/Evaluations/response_quality_evaluator.py`
- `tldw_Server_API/app/core/Evaluations/recipe_runs_service.py`
- `tldw_Server_API/app/core/Evaluations/recipe_runs_jobs.py`
- `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`
- `tldw_Server_API/app/core/Evaluations/recipes/base.py`
- `tldw_Server_API/app/core/Evaluations/recipes/registry.py`
- `tldw_Server_API/app/core/Evaluations/recipes/rag_answer_quality.py`
- `tldw_Server_API/app/core/Evaluations/recipes/rag_answer_quality_execution.py`
- `tldw_Server_API/app/core/Evaluations/recipes/rag_retrieval_tuning.py`
- `tldw_Server_API/app/core/Evaluations/recipes/rag_retrieval_tuning_execution.py`
- `tldw_Server_API/app/core/Evaluations/recipes/embeddings_retrieval.py`
- `tldw_Server_API/app/core/RAG/rag_service/vector_stores/chromadb_adapter.py`
- `tldw_Server_API/app/core/RAG/rag_service/vector_stores/factory.py`
- `tldw_Server_API/app/core/RAG/rag_service/vector_stores/pgvector_adapter.py`
### Baseline Notes
- The reviewed slice is baseline-stable relative to `ec30354a2`; the requested code paths are present in the frozen baseline and the current tree.
### Control and Data Flow Notes
- The recipe API layer normalizes requests through `evaluations_recipes.py`, then delegates to `RecipeRunsService` for dataset validation, reuse hashing, persistence, and report shaping.
- The RAG pipeline preset routes in `evaluations_rag_pipeline.py` pass the authenticated stable user id into `EvaluationsDatabase`, but the persistence layer still keys presets by `name` alone.
- RAG pipeline eval runs build ephemeral vector indexes in `eval_runner.py` from `index_namespace` plus a deterministic config ordinal (`cfg_001`, `cfg_002`, ...), then register those names in `ephemeral_collections`.
- Cleanup is exposed as an authenticated user endpoint in `evaluations_rag_pipeline.py`, but it enumerates expired ephemeral collections from the shared evaluations database and deletes them through whatever vector-store adapter is initialized for the current user/backend.
- `response_quality_evaluator.py` is a leaf scorer in this slice, but the hotspot scan shows its direct route wiring still lives under `evaluations_unified.py`, not the recipe or RAG pipeline routers reviewed here. I did not find a new slice-local defect in that evaluator beyond the service-level orchestration surface already covered in Slice 2.
- The registry path is intentionally small: manifests are registered up front, and recipe-specific execution helpers build the report payloads returned by the API.
### Findings
1. Severity: High
   Confidence: High
   Priority: Immediate
   Applicability: Baseline
   Why it matters: pipeline presets are treated as user-scoped rows, but the shared-backend schema still keys `pipeline_presets` by `name` alone. The default SQLite path hides this because `DatabasePaths.get_evaluations_db_path()` creates a per-user DB file, but `UnifiedEvaluationService` routes through `create_evaluations_database()`, which binds the service to a shared PostgreSQL content backend when that backend is configured. In that supported deployment shape, two users saving the same preset name will race on the same row and the second `upsert_pipeline_preset()` call will overwrite the first user's preset and `user_id`.
   File references: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py:59`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py:69`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py:157`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py:209`, `tldw_Server_API/app/core/DB_Management/DB_Manager.py:406`, `tldw_Server_API/app/core/DB_Management/DB_Manager.py:413`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:744`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:745`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2740`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2747`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2750`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2760`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2807`, `tldw_Server_API/app/core/DB_Management/db_path_utils.py:496`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:137`, `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py:1603`
   Recommended fix: migrate `pipeline_presets` to a composite uniqueness model such as `(user_id, name)` or a surrogate primary key plus unique constraint on `(user_id, name)`, then update all CRUD helpers to upsert and delete on that composite key.
   Recommended tests: add a PostgreSQL-backed multi-user integration test that creates the same preset name for two users and asserts both can list, fetch, update, and delete their own copy without affecting the other user.
   Verification note: a direct SQLite probe using the same `ON CONFLICT(name)` statement stored only `{'name': 'shared', 'config': '{"b":2}', 'user_id': 'user-2'}` after inserting `shared` for `user-1` and then `user-2`, showing the schema conflict. Code inspection then confirmed that the default SQLite path is per-user, while the shared PostgreSQL backend path still routes all users through that same name-only schema.
2. Severity: High
   Confidence: High
   Priority: Immediate
   Applicability: Baseline
   Why it matters: ephemeral RAG pipeline indexes are not isolated by run. `eval_runner.py` names them as `"{index_namespace}_{cfg_id}"`, where `cfg_id` is only the loop ordinal inside the config grid. Re-running the same pipeline with the same `index_namespace` reuses the same collection names, and the persistence layer records them with `INSERT OR IGNORE`, so later runs silently inherit earlier registry metadata. On Chroma this contaminates repeated runs for the same user because `create_collection()` is `get_or_create_collection()`. On pgvector it is worse: `create_collection()` is `CREATE TABLE IF NOT EXISTS`, and the adapter ignores `user_id`, so identical collection names can collide across users on that backend. The cleanup route then compounds the problem by sweeping a global `ephemeral_collections` table with no owner column.
   File references: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py:233`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py:242`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py:252`, `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py:253`, `tldw_Server_API/app/core/Evaluations/eval_runner.py:593`, `tldw_Server_API/app/core/Evaluations/eval_runner.py:608`, `tldw_Server_API/app/core/Evaluations/eval_runner.py:691`, `tldw_Server_API/app/core/Evaluations/eval_runner.py:703`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:443`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:444`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2816`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2823`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2831`, `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py:2844`, `tldw_Server_API/app/core/RAG/rag_service/vector_stores/chromadb_adapter.py:103`, `tldw_Server_API/app/core/RAG/rag_service/vector_stores/chromadb_adapter.py:109`, `tldw_Server_API/app/core/RAG/rag_service/vector_stores/factory.py:103`, `tldw_Server_API/app/core/RAG/rag_service/vector_stores/factory.py:155`, `tldw_Server_API/app/core/RAG/rag_service/vector_stores/factory.py:160`, `tldw_Server_API/app/core/RAG/rag_service/vector_stores/pgvector_adapter.py:281`, `tldw_Server_API/app/core/RAG/rag_service/vector_stores/pgvector_adapter.py:287`, `tldw_Server_API/app/core/RAG/rag_service/vector_stores/pgvector_adapter.py:315`
   Recommended fix: include a run-unique component in every ephemeral collection name, persist owner identity with the registry row, and scope cleanup queries by owner/backend context before deleting and marking rows. For pgvector-backed deployments, ensure the namespace derivation also incorporates user isolation instead of only collection name reuse.
   Recommended tests: add a regression that launches two RAG pipeline runs with the same `index_namespace` and asserts they receive different ephemeral collection names; add cleanup tests that prove one user's cleanup path cannot mark or delete another user's registry rows; add pgvector-specific coverage that rejects or isolates identical collection names across users.
   Verification note: code inspection shows `collection_name = f"{base_namespace}_{cfg_id}"` with `cfg_id` derived only from enumeration order. A direct probe reproduced the collision pattern and registry overwrite behavior: two runs that both derive `shared_cfg_001` leave the first row intact under `INSERT OR IGNORE`. The backend adapters then reuse existing namespaces via `get_or_create_collection()` (Chroma) or `CREATE TABLE IF NOT EXISTS` (pgvector).
3. Severity: Medium
   Confidence: High
   Priority: Near-term
   Applicability: Baseline
   Why it matters: `RecipeRegistry` silently overwrites earlier entries when two definitions share the same `recipe_id`. That makes registration order significant and can shadow the intended recipe implementation without any warning, which is risky for both custom registries and future builtin additions.
   File references: `tldw_Server_API/app/core/Evaluations/recipes/registry.py:39`, `tldw_Server_API/app/core/Evaluations/recipes/registry.py:42`, `tldw_Server_API/app/core/Evaluations/recipes/registry.py:43`
   Recommended fix: Reject duplicate `recipe_id` values during registry initialization, or raise a deterministic error or warning when a collision is detected.
   Recommended tests: Add a unit test that constructs a `RecipeRegistry` with two recipe definitions using the same `recipe_id` and asserts that initialization fails instead of silently keeping the later recipe.
   Verification note: A direct probe with two `StaticRecipeDefinition` instances that both used `recipe_id="dup"` returned the second manifest from `get_manifest("dup")`, confirming the silent shadowing behavior. The baseline code shows the same overwrite path.
### Open Questions
- None.
### Verification Run
- `source .venv/bin/activate && rg -n "registry|execute|candidate|metric|retrieval|quality|job|background|dataset|snapshot" tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_rag_pipeline.py tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_recipes.py tldw_Server_API/app/core/Evaluations/recipe_runs_service.py tldw_Server_API/app/core/Evaluations/recipes`
  Result: confirmed the expected registry, execution, dataset, and report-shaping hotspots across the slice.
- `source .venv/bin/activate && rg -n "ResponseQualityEvaluator|response_quality" tldw_Server_API/app/core/Evaluations/response_quality_evaluator.py tldw_Server_API/app/core/Evaluations/recipes tldw_Server_API/app/api/v1/endpoints/evaluations -g '*.py'`
  Result: `response_quality_evaluator.py` is present in the slice, but direct route wiring still points at `evaluations_unified.py`; no recipe or RAG pipeline route in this slice invokes it directly.
- `source .venv/bin/activate && rg -n "create_evaluations_database|get_evaluations_db_path|pipeline_presets|ephemeral_collections|create_collection" tldw_Server_API/app/core/DB_Management/DB_Manager.py tldw_Server_API/app/core/DB_Management/Evaluations_DB.py tldw_Server_API/app/core/DB_Management/db_path_utils.py tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py tldw_Server_API/app/core/Evaluations/eval_runner.py tldw_Server_API/app/core/RAG/rag_service/vector_stores/chromadb_adapter.py tldw_Server_API/app/core/RAG/rag_service/vector_stores/pgvector_adapter.py`
  Result: confirmed the backend-sensitive preset storage path, the per-user SQLite DB path, the shared-backend factory branch, the deterministic ephemeral collection naming, and the collection creation semantics for Chroma and pgvector.
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py tldw_Server_API/tests/Evaluations/integration/test_recipe_runs_api.py tldw_Server_API/tests/Evaluations/test_recipe_runs_jobs_worker.py tldw_Server_API/tests/Evaluations/test_rag_pipeline_runner.py tldw_Server_API/tests/Evaluations/test_recipe_registry.py tldw_Server_API/tests/Evaluations/test_recipe_dataset_snapshot.py tldw_Server_API/tests/Evaluations/test_recipe_rag_answer_quality.py`
  Result: `84 passed`.
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Evaluations/test_rag_evaluator_embeddings.py tldw_Server_API/tests/Evaluations/unit/test_rag_evaluator.py tldw_Server_API/tests/Evaluations/test_recipe_embeddings_retrieval.py tldw_Server_API/tests/Evaluations/test_recipe_rag_retrieval_tuning.py`
  Result: `63 passed, 2 skipped`.
- `source .venv/bin/activate && python - <<'PY'`
  `import sqlite3`
  `conn = sqlite3.connect(':memory:')`
  `conn.row_factory = sqlite3.Row`
  `conn.execute('CREATE TABLE pipeline_presets (name TEXT PRIMARY KEY, config TEXT NOT NULL, created_at TEXT, updated_at TEXT, user_id TEXT)')`
  `conn.execute("INSERT INTO pipeline_presets (name, config, user_id) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET config=excluded.config, updated_at=CURRENT_TIMESTAMP, user_id=COALESCE(excluded.user_id, pipeline_presets.user_id)", ('shared', '{"a":1}', 'user-1'))`
  `conn.execute("INSERT INTO pipeline_presets (name, config, user_id) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET config=excluded.config, updated_at=CURRENT_TIMESTAMP, user_id=COALESCE(excluded.user_id, pipeline_presets.user_id)", ('shared', '{"b":2}', 'user-2'))`
  `print(dict(conn.execute('SELECT name, config, user_id FROM pipeline_presets WHERE name = ?', ('shared',)).fetchone()))`
  `print(conn.execute('SELECT COUNT(*) FROM pipeline_presets WHERE name = ? AND user_id = ?', ('shared', 'user-1')).fetchone()[0])`
  `print(conn.execute('SELECT COUNT(*) FROM pipeline_presets WHERE name = ? AND user_id = ?', ('shared', 'user-2')).fetchone()[0])`
  `PY`
  Result: the second upsert replaced the row with `user_id='user-2'`; the same preset name could not exist for both users simultaneously.
- `source .venv/bin/activate && python - <<'PY'`
  `import sqlite3`
  `base_namespace = 'shared'`
  `name_a = f'{base_namespace}_cfg_001'`
  `name_b = f'{base_namespace}_cfg_001'`
  `print(name_a == name_b)`
  `conn = sqlite3.connect(':memory:')`
  `conn.row_factory = sqlite3.Row`
  `conn.execute('CREATE TABLE ephemeral_collections (collection_name TEXT PRIMARY KEY, namespace TEXT, run_id TEXT, ttl_seconds INTEGER DEFAULT 86400, created_at TEXT DEFAULT CURRENT_TIMESTAMP, deleted_at TEXT NULL)')`
  `conn.execute('INSERT OR IGNORE INTO ephemeral_collections (collection_name, ttl_seconds, run_id, namespace) VALUES (?, ?, ?, ?)', (name_a, 10, 'run-a', base_namespace))`
  `conn.execute('INSERT OR IGNORE INTO ephemeral_collections (collection_name, ttl_seconds, run_id, namespace) VALUES (?, ?, ?, ?)', (name_b, 99, 'run-b', base_namespace))`
  `print(dict(conn.execute('SELECT collection_name, namespace, run_id, ttl_seconds FROM ephemeral_collections WHERE collection_name = ?', (name_a,)).fetchone()))`
  `PY`
  Result: both runs derived the same collection name, and the second registration was ignored, leaving the first run's metadata in place.
- `source .venv/bin/activate && python - <<'PY'`
  `from tldw_Server_API.app.core.Evaluations.recipes.base import StaticRecipeDefinition`
  `from tldw_Server_API.app.core.Evaluations.recipes.registry import RecipeRegistry`
  `from tldw_Server_API.app.api.v1.schemas.evaluation_recipe_schemas import RecipeManifest`
  `first = StaticRecipeDefinition(RecipeManifest(recipe_id='dup', recipe_version='1', name='first', description='first'))`
  `second = StaticRecipeDefinition(RecipeManifest(recipe_id='dup', recipe_version='1', name='second', description='second'))`
  `registry = RecipeRegistry(recipes=(first, second))`
  `print(registry.get_manifest('dup').name)`
  `PY`
  Result: the registry returned `second`, confirming that duplicate `recipe_id` values are overwritten silently.
### Slice Status
- reviewed

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
