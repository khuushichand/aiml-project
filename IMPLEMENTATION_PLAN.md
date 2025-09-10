## Stage 1: Create Tracking Plan
Goal: Document identified issues in the Evaluations module with proposed resolutions and status tracking.
Success Criteria: Plan file added with clear issues, owners (contractor), and acceptance criteria.
Status: In Progress

Issues and Resolutions

1) Duplicate routes in `evaluations_unified.py`
- Impact: Potential double-registration of endpoints, ambiguous behavior, maintenance risk.
- Resolution: Remove the duplicate definitions; keep a single authoritative implementation for each of: `get_evaluation`, `update_evaluation`, `delete_evaluation`, `create_run`, `list_runs`, and tldw eval endpoints. Verify no functionality loss.
- Acceptance: File contains only one definition per route. App boots without route conflicts; smoke tests for endpoints pass.

2) Health check always reports healthy
- Impact: Masks real DB connectivity failures.
- Resolution: Replace `db_healthy = self.db.get_evaluation("test") is not None or True` with a real connectivity probe (e.g., `SELECT 1` via `get_connection()`), handling exceptions. Return degraded/unhealthy appropriately.
- Acceptance: When DB unavailable, health indicates degraded/unhealthy. When available, health = healthy.

3) Missing per-user usage limits on unified tldw eval endpoints
- Impact: Regression from legacy behavior; risk of abuse/cost.
- Resolution: Use `user_rate_limiter.check_rate_limit` within `/geval`, `/rag`, `/response-quality`, `/batch` with simple token and estimated cost heuristics (based on input size). Return 429 with limiter metadata headers when exceeded.
- Acceptance: Requests exceeding per-user thresholds receive 429 and proper headers. Normal requests succeed.

4) Unused `BackgroundTasks` param in `create_run`
- Impact: Noise, confusion; not used since service manages async tasks directly.
- Resolution: Remove `background_tasks` parameter from endpoint signature.
- Acceptance: Endpoint still starts runs and returns 202 with run data; no unused parameters.

5) Auth token source inconsistency
- Impact: Uses `API_BEARER` fallback; project prefers `SINGLE_USER_API_KEY`.
- Resolution: In single-user mode, accept `X-API-KEY` header or Bearer token matching `SINGLE_USER_API_KEY` only; remove `API_BEARER` fallback.
- Acceptance: Auth works with `SINGLE_USER_API_KEY`. Tests using `SINGLE_USER_API_KEY` pass.

Notes / Non-blocking (deferred):
- Standardize all error responses to structured format across endpoints (most already consistent).
- Promote tests from `tests/Evaluations_backup/` to first-class; ensure CI covers them by default.

## Stage 2: Deduplicate Routes
Goal: Remove duplicate routes in unified endpoint.
Success Criteria: One definition per route; app boots; basic endpoint smoke tests pass.
Status: Not Started

## Stage 3: Fix Health Check
Goal: Implement real DB connectivity validation.
Success Criteria: Health reflects DB availability correctly.
Status: Not Started

## Stage 4: Per-user Rate Limits
Goal: Enforce per-user limits on tldw eval endpoints.
Success Criteria: 429 returned when exceeding limits; headers present.
Status: Not Started

## Stage 5: Param Cleanup
Goal: Remove unused `BackgroundTasks` param from `create_run`.
Success Criteria: Endpoint behavior unchanged; cleaner signature.
Status: Not Started

## Stage 6: Auth Consistency
Goal: Prefer `SINGLE_USER_API_KEY` exclusively in single-user mode.
Success Criteria: Auth works with `SINGLE_USER_API_KEY`; no `API_BEARER` fallback.
Status: Not Started

