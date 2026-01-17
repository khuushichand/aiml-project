# Test Gates Implementation

Purpose: establish a pragmatic, long‑term approach to keep unit tests fast and deterministic by lazily initializing heavy subsystems and gating their route imports. This prevents timeouts/hangs caused by import‑time side effects (e.g., connection pools, background threads) while preserving full functionality for opt‑in integration suites and production.

## Summary

- Make heavy subsystems lazy: no connections/threads at import time.
- Gate heavy routers behind environment/config toggles and import inside those gates.
- Default tests to a minimal app profile; provide opt‑in markers/env for heavy suites.
- Harmonize `TEST_MODE` semantics and use small pool sizes under tests.

Targets (initial):
- Evaluations (connection pool + webhook manager)
- Jobs/metrics workers that start at app startup
- Any router with heavy import‑time work (e.g., OCR/VLM only if needed)

## Goals & Non‑Goals

Goals
- Fast unit tests by default (< a few seconds per file) without rewriting tests.
- Deterministic startup/teardown in TestClient.
- Simple, explicit switches to run heavy integration suites locally and in CI.

Non‑Goals
- Changing production behavior when routes are enabled.
- Removing features; this is about initialization timing and control.

## Design Overview

1) Lazy singletons for heavy managers
- Replace module‑level globals with getters that construct on first use.
- Example (Evaluations):
  - Before: `connection_manager = EvaluationsConnectionManager()` at import.
  - After: `@lru_cache(maxsize=1) def get_connection_manager(...): return EvaluationsConnectionManager(...)`.
  - Update helpers: `get_connection() -> get_connection_manager().get_connection()`.
- Provide `shutdown_*_if_initialized()` helpers that no‑op if never created.

2) Route import gating (main app)
- Import heavy routers only inside `route_enabled("…")` gates, right before `include_router`.
- Use existing route policy from config/env (`API-Routes` in `config.txt`, `ROUTES_DISABLE`, `ROUTES_ENABLE`).
- Effect: if a route is disabled, its module is not imported and cannot trigger heavy work.

- Precedence: `enable` overrides `disable`; `disable` overrides defaults; `enable` overrides `stable_only`.
  - During tests, certain routes are force‑enabled to avoid 404s (workflows, sandbox, scheduler, mcp‑unified, mcp‑catalogs, jobs, personalization).

3) Minimal test profile by default
- In tests, set `MINIMAL_TEST_APP=1` and extend `ROUTES_DISABLE` to include heavy keys (e.g., `evaluations`) unless explicitly opted‑in.
- Provide pytest marker/fixture to enable heavy routes for specific tests/suites.

4) TEST_MODE normalization and pool sizing
- Normalize truthiness across `TEST_MODE` and `TLDW_TEST_MODE` to {"1","true","yes","y","on"}.
- Under tests, use small pool sizes/timeouts to reduce overhead (e.g., pool_size=1, max_overflow=2, timeout=5) for subsystems like Evaluations.

## Environment & Config Toggles

Config file: `tldw_Server_API/Config_Files/config.txt` section `[API-Routes]`
- `stable_only = true|false` (default is false when config is loaded; if config cannot be read, a conservative default of true is used).
- `disable = a,b,c`
- `enable = x,y,z`
- `experimental_routes = k1,k2`

Environment variables (precedence > config.txt):
- `ROUTES_STABLE_ONLY`      — same as `stable_only`.
- `ROUTES_DISABLE`          — comma/space list of route keys to disable.
- `ROUTES_ENABLE`           — comma/space list of route keys to force‑enable.
- `ROUTES_EXPERIMENTAL`     — extend experimental list (affects `stable_only`).
- `MINIMAL_TEST_APP`        — enables minimal test app profile (fast startup; selective routers).
- `ULTRA_MINIMAL_APP`       — health‑only profile (diagnostics).
- `TEST_MODE` / `TLDW_TEST_MODE` — unified test flags; treat truthy values as {1,true,yes,y,on}.
- `RUN_EVALUATIONS`         — opt‑in heavy Evaluations routes for tests/CI.

- `DISABLE_HEAVY_STARTUP`   — force synchronous startup (disable deferral of heavy work).
- `DEFER_HEAVY_STARTUP`     — defer heavy/non‑critical startup tasks to background.
- Jobs/metrics worker toggles to avoid starting background workers in tests/CI:
  - `AUDIO_JOBS_WORKER_ENABLED`, `JOBS_WEBHOOKS_ENABLED`, `JOBS_WEBHOOKS_URL`, `JOBS_METRICS_GAUGES_ENABLED`, `JOBS_METRICS_RECONCILE_ENABLE`, `JOBS_CRYPTO_ROTATE_SERVICE_ENABLED`.

Notes:
- Route keys are lowercase and comma/space separated; both `-` and `_` are commonly used.

Recommended test defaults:
- `MINIMAL_TEST_APP=1`
- `ROUTES_DISABLE=research,evaluations` (extend existing value without clobbering)
- `TEST_MODE=1`

Opt‑in heavy suite:
- Set `RUN_EVALUATIONS=1` (fixture or job env) and remove `evaluations` from `ROUTES_DISABLE`.

## Implementation Plan (Stages)

Stage 1 — Design & Staging
- Add this doc and an IMPLEMENTATION_PLAN.md (optional) summarizing stages and success criteria.

Stage 2 — Lazy Singletons (Evaluations/Webhooks)
- File: `tldw_Server_API/app/core/Evaluations/connection_pool.py`
  - Replace global `connection_manager` with `get_connection_manager()` (lru_cache).
  - Update `get_connection()` / `get_connection_async()` to call the getter.
  - Add `shutdown_evaluations_pool_if_initialized()`.
- File: `tldw_Server_API/app/core/Evaluations/webhook_manager.py`
  - Provide `get_webhook_manager()` that constructs on first use.
  - Ensure schema init runs only when manager is first used.
- File: `tldw_Server_API/app/main.py`
  - Use shutdown helper; stop accessing module globals directly.

Stage 3 — Gate Heavy Router Imports
- File: `tldw_Server_API/app/main.py`
  - Move heavy router imports inside `if route_enabled("…"):` blocks.
  - Include only when enabled; otherwise avoid importing the module at all.

Stage 4 — Default Minimal Test Profile
- File: `tldw_Server_API/tests/conftest.py`
  - `os.environ.setdefault("MINIMAL_TEST_APP", "1")`.
  - Extend `ROUTES_DISABLE` to include `evaluations` unless `RUN_EVALUATIONS=1`.
- Add pytest marker `evaluations`; a session fixture toggles env accordingly for marked tests.

Stage 5 — TEST_MODE & Pool Sizing Harmonization
- File: Resource Governor ingress middleware and policy loader wiring
  - Accept truthy `TEST_MODE` / `TLDW_TEST_MODE` variants.
- File: `tldw_Server_API/app/core/Evaluations/connection_pool.py`
  - Use small pool sizes when `TEST_MODE` is truthy.

- Add shared helper `is_test_mode()` for consistent detection across modules (checks both envs; truthy set {1,true,yes,y,on}).

Stage 6 — Docs & CI
- Update project docs (this file + Development doc): usage of toggles and patterns.
- CI: default unit job uses minimal profile; nightly/weekly job sets `RUN_EVALUATIONS=1`.

## File/Code Pointers (initial)

- Route gating helpers: `tldw_Server_API/app/core/config.py` (route policy functions)
- App route inclusion: `tldw_Server_API/app/main.py` (import + include_router strategy)
- Evaluations connection pool: `tldw_Server_API/app/core/Evaluations/connection_pool.py`
- Evaluations webhook manager: `tldw_Server_API/app/core/Evaluations/webhook_manager.py`
- Test client setup: `tldw_Server_API/tests/conftest.py`

## Testing Strategy

Unit tests (default minimal profile)
- Ensure startup is fast and no heavy connections are created when routes disabled.
- Verify `get_connection_manager()` lazily constructs and returns a singleton.
- Verify rate limiting bypass respects all truthy `TEST_MODE`/`TLDW_TEST_MODE` forms.

Opt‑in integration tests (`-m evaluations` or `RUN_EVALUATIONS=1`)
- Confirm `/api/v1/evaluations/*` routes are present and functional.
- Assert pools and background workers start/stop cleanly.

Regression checks
- With `ROUTES_DISABLE=evaluations`, importing `main.py` must not create Evaluations connections.
- Shutdown helpers must not error if never initialized.

## CI Guidance

- Unit job (default)
- Env: `MINIMAL_TEST_APP=1`, `TEST_MODE=1`, `ROUTES_DISABLE=research,evaluations` (merge with any existing value).
- Run standard markers: `-m "not evaluations and not jobs"`.

Evaluations job (opt‑in)
- Env: `RUN_EVALUATIONS=1`, `MINIMAL_TEST_APP=0` or remove `evaluations` from `ROUTES_DISABLE`.
- Run markers: `-m evaluations`.

Jobs/other heavy suites (optional)
- Maintain separate CI jobs with explicit env toggles, mirroring the pattern above.

## Backward Compatibility & Migration

- If any code imports Evaluations globals directly (e.g., `from …connection_pool import connection_manager`), add a temporary alias:
  - Define a module‑level property that returns `get_connection_manager()` and log a deprecation warning.
- Prefer dependency‑injection or accessor functions (`get_…()`) over importing singletons.

## Risks & Mitigations

- Hidden heavy imports remain elsewhere
  - Mitigation: search for module‑level instantiation patterns; convert to lazy as needed.
- Shutdown ordering issues in tests
  - Mitigation: centralize shutdown via helpers and app lifespan; add session‑level teardown fixtures.

## Operational Notes

- This approach does not change production behavior when routes are enabled.
- When debugging, you can temporarily disable lazy gating by enabling the routes to compare startup behavior.

## Quick Verification

1) Disable evaluations and run a single test
```
export MINIMAL_TEST_APP=1
export ROUTES_DISABLE="${ROUTES_DISABLE},evaluations"
export TEST_MODE=1
pytest -q tldw_Server_API/tests/WebScraping/test_webscraping_usage_events.py::test_webscrape_process_usage_event
```
Expect: fast startup, no Evaluations pool logs, test completes quickly.

2) Enable evaluations for integration run
```
export RUN_EVALUATIONS=1
unset MINIMAL_TEST_APP
ROUTES_DISABLE="$(echo "$ROUTES_DISABLE" | tr ',' '\n' | awk 'tolower($0)!="evaluations" && $0!=""' | paste -sd, -)"
export TEST_MODE=1
pytest -m evaluations -q
```
Expect: evaluations routes loaded; pools created; graceful shutdown.

Note: Some routes are force-enabled during tests by `route_enabled()` (workflows, sandbox, scheduler, mcp-unified, mcp-catalogs, jobs, personalization), independent of `ROUTES_DISABLE`. This avoids 404s in common test paths.

Examples
- Lazy getter with shutdown helper:
  - `from functools import lru_cache`
  - `@lru_cache(maxsize=1)`
  - `def get_connection_manager(): return EvaluationsConnectionManager(...)`
  - `def shutdown_evaluations_pool_if_initialized():` call `get_connection_manager().shutdown()` then `get_connection_manager.cache_clear()` if instantiated.
- Import-within-gate pattern (in `main.py`):
  - `if route_enabled("evaluations"):` then import and `app.include_router(...)`; otherwise log disabled.

- Shutdown helpers in `main.py` lifespan teardown (after app subsystems):
  - `from tldw_Server_API.app.core.Evaluations.connection_pool import shutdown_evaluations_pool_if_initialized`
  - `from tldw_Server_API.app.core.Evaluations.webhook_manager import shutdown_webhook_manager_if_initialized`
  - Call both in shutdown; helpers are no‑ops if never initialized.

Contributor checklist for heavy modules
- No import-time threads/connections or background tasks.
- Provide a lazy `get_...()` accessor and a `shutdown_..._if_initialized()` helper.
- Register a route key in `[API-Routes]` and honor `ROUTES_DISABLE`/`ROUTES_ENABLE`.
- If tests are heavy, add a pytest marker and CI skip by default.
