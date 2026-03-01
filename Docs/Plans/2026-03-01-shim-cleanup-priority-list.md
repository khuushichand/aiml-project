# Shim Cleanup Priority List (Follow-up)

## Scope
- Runtime shim inventory under `tldw_Server_API/app/**` (tests/docs excluded for prioritization).
- Focus on removals that are unlikely to break active runtime paths.

## Priority Tiers

### Tier 1: Safe next removals (low risk)
1. `app/core/DB_Management/UserDatabase.py` compatibility wrapper
   - Why low risk: no in-repo runtime imports remained after migrating `migrate_to_multiuser.py` to `UserDatabase_v2`.
   - Action: remove wrapper module and use `UserDatabase_v2` with explicit `DatabaseConfig`.
   - Status: completed in this follow-up branch.

2. Test-only backend-detection compatibility helper aliases
   - Targets:
     - `app/api/v1/endpoints/auth.py` (`is_postgres_backend` test shim)
     - `app/api/v1/endpoints/users.py` similar compatibility helper
   - Why low risk: intended for monkeypatching in tests; not part of public API contract.
   - Work needed: update tests patching legacy symbols before removal.

3. `app/core/Local_LLM/http_utils.py` fake-client compatibility path
   - Why low risk: explicitly marked deprecated/testing-only shim.
   - Work needed: convert remaining fake-client tests to `httpx.AsyncClient`-compatible stubs.

### Tier 2: Medium risk removals (require staged migration)
1. MCP single-user API-key compatibility shim
   - Target: `app/api/v1/endpoints/mcp_unified_endpoint.py`
   - Risk: single-user deployments may rely on current fallback behavior.
   - Migration path: enforce claim-first/API-key-manager path behind feature flag, then flip default.

2. Audio package-level compatibility shim exports
   - Target: `app/api/v1/endpoints/audio/__init__.py` and `_audio_shim_attr` callers.
   - Risk: widespread import indirection across streaming/transcriptions/tts endpoints.
   - Migration path: direct imports per endpoint module + remove package `__getattr__` indirection.

3. Auth dependency ingress compatibility shims
   - Target: `app/api/v1/API_Deps/auth_deps.py` (`check_rate_limit`, `check_auth_rate_limit`)
   - Risk: fallback path currently provides fail-closed behavior when RG is unavailable.
   - Migration path: prove RG-only reliability and preserve fallback via dedicated guard component.

### Tier 3: High risk / architectural shims
1. Phase-2 legacy rate-limiter shim modules
   - Targets:
     - `app/core/Chat/rate_limiter.py`
     - `app/core/Embeddings/rate_limiter.py`
     - `app/core/Evaluations/user_rate_limiter.py`
     - `app/core/Character_Chat/character_rate_limiter.py`
     - `app/core/Web_Scraping/enhanced_web_scraping.py`
     - audio RG diagnostics fallback in `app/core/Usage/audio_quota.py`
   - Risk: tied to Resource Governor rollout, telemetry, and fallback semantics across multiple domains.
   - Migration path: module-by-module RG parity verification with production metrics, then removal.

## Suggested Execution Order
1. Finish Tier 1 shims in small PRs with direct test updates.
2. For each Tier 2 item, add cutover flag + telemetry, then remove shim after one release cycle.
3. Treat Tier 3 as coordinated RG-completion effort, not opportunistic cleanup.

