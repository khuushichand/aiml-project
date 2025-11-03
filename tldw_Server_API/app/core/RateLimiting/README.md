# RateLimiting

## 1. Descriptive of Current Feature Set

- Purpose: Centralized request limiting to protect APIs and background operations. Supports explicit per-route caps and RBAC-aware selection of per-resource limits.
- Capabilities:
  - Global SlowAPI limiter for FastAPI routes, with test-aware bypass.
  - Route-level decorators like `@limiter.limit("10/minute")` and optional per-route key functions.
  - RBAC rate-limit selector (logs strictest user/role limits for a resource; enforcement path stubbed).
  - Token scope dependency (`require_token_scope`) with usage counting hints (`count_as="call"|"run"`).
- Inputs/Outputs:
  - Input: HTTP requests (and contextual user/role data).
  - Output: Allow or HTTP 429 with `Retry-After` header (where applicable).
- Related Endpoints (examples):
  - Audio TTS/STT routes — tldw_Server_API/app/api/v1/endpoints/audio.py:254, 463, 920, 973, 1958, 2143
  - Media ingestion — tldw_Server_API/app/api/v1/endpoints/media.py:2120, 2276; RBAC limiter on create — tldw_Server_API/app/api/v1/endpoints/media.py:4473, 8460
  - RAG search — tldw_Server_API/app/api/v1/endpoints/rag_unified.py:697
  - Chat completions — tldw_Server_API/app/api/v1/endpoints/chat.py:615
  - Embeddings — tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py:1630
  - Notes — tldw_Server_API/app/api/v1/endpoints/notes.py:174, 289, 351, 419, 482, 523, 567, 655, 736, 820, 905, 939, 977, 1009
  - Chatbooks — tldw_Server_API/app/api/v1/endpoints/chatbooks.py:120, 304, 514, 897

## 2. Technical Details of Features

- Architecture & Data Flow
  - Global limiter instance and test-aware key function: tldw_Server_API/app/api/v1/API_Deps/rate_limiting.py:1
    - `Limiter(key_func=get_test_aware_remote_address)` returns `None` in `TEST_MODE`, bypassing rate limits during tests.
  - RBAC selector: `rbac_rate_limit(resource)` returns a dependency that logs selected limits from `rbac_user_rate_limits` and `rbac_role_rate_limits` but does not enforce yet: tldw_Server_API/app/api/v1/API_Deps/auth_deps.py:994
  - Token-scope enforcement: `require_token_scope(scope, ..., endpoint_id=..., count_as=...)` injects scoped virtual-key checks and emits usage hints: tldw_Server_API/app/api/v1/API_Deps/auth_deps.py:1040

- Configuration
  - Testing bypass: `TEST_MODE=true` (and helpers in some modules, e.g., Watchlists supports `WATCHLISTS_DISABLE_RATE_LIMITS`).
  - Per-route rates are declared inline via decorators; for RBAC selection, limits are stored in DB tables and read by the selector (no env required).

- Concurrency & Performance
  - SlowAPI uses in-process counters by default. For multi-instance deployments, front an API gateway or add a shared limiter (future enhancement).

- Error Handling
  - When exceeded, HTTP 429 responses with `Retry-After` may be set explicitly (see auth endpoint path) or by the limiter behavior.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure
  - `Rate_Limit.py` — legacy utilities (keep minimal; prefer API_Deps limiter).
  - `app/api/v1/API_Deps/rate_limiting.py` — source of truth for limiter setup.
  - `app/api/v1/API_Deps/auth_deps.py` — `rbac_rate_limit` and `require_token_scope` dependencies.
- Extension Points
  - Use `@limiter.limit("N/unit")` on new endpoints. For resource-scoped behavior, add `Depends(rbac_rate_limit("<resource>"))`.
  - To enable true RBAC enforcement, extend `enforce_rbac_rate_limit` to check counters and raise 429 based on selected limits.
- Tests
  - Evaluations limiting shape and status: tldw_Server_API/tests/Evaluations/test_evaluations_unified.py:711, 733–736
  - Watchlists optional rate limit headers path: tldw_Server_API/tests/Watchlists/test_rate_limit_headers_optional.py:39
- Local Dev Tips
  - Set `TEST_MODE=true` to bypass `SlowAPI` limits during unit/integration tests.
  - Use small per-route limits to validate 429 behavior in dev.

