# App Shutdown Coordinator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current large serial FastAPI shutdown path with an app-scoped shutdown coordinator that fails readiness immediately, blocks new work during drain, shuts legacy components down by ordered parallel phases, and emits structured shutdown summaries.

**Architecture:** Keep `tldw_Server_API.app.main` as the FastAPI entry point, but move lifecycle state, admission gating, budgets, and phase orchestration into focused shutdown service modules. Land the work in thin slices: first app-scoped lifecycle state and control-plane correctness, then middleware and coordinator primitives, then legacy adapter migration, then transport/resource ownership and verification.

**Tech Stack:** FastAPI, Starlette middleware, asyncio, pytest, httpx/TestClient, Loguru, Bandit

---

## Scope Check

This remains one implementation plan because the spec’s stages are tightly coupled:

- app-scoped lifecycle state must exist before readiness and drain admission can move off module globals
- drain gating must exist before coordinator-managed shutdown can reliably reject new work
- shadow-mode inventory must exist before legacy teardown is parallelized
- transport/session ownership must exist before long-lived connections can be drained safely

Do not split this into separate execution plans unless you first break the spec into smaller approved sub-specs.

## Planned File Map

### Existing files to modify

- `tldw_Server_API/app/main.py`
  - Current hot spots:
    - `READINESS_STATE` near the lifespan setup section
    - `lifespan(...)` startup and shutdown orchestration
    - HTTP middleware stack
    - control-plane readiness routes (`/ready`, `/health/ready`)
  - End state:
    - delegates lifecycle state and shutdown orchestration to coordinator helpers
    - installs the drain gate middleware early in the stack
    - registers legacy shutdown adapters instead of owning one giant serial teardown block

- `tldw_Server_API/app/services/app_lifecycle.py`
  - Current responsibility: append startup/shutdown markers and mutate readiness bool
  - End state: own app-scoped lifecycle state initialization/reset, lifecycle event logging, and compatibility helpers for readiness/drain state

- `tldw_Server_API/app/core/Utils/executor_registry.py`
  - Current problem: `shutdown_all_registered_executors()` is internally sequential
  - End state: expose a coordinator-friendly snapshot or deadline-aware shutdown surface so executor shutdown does not hide a serial tail

- `tldw_Server_API/app/core/MCP_unified/server.py`
  - Current useful behavior: already tracks `connections` and can close them in bulk
  - End state: exposes a coordinator registration or explicit shutdown metadata for active long-lived MCP sessions

- `tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_websocket.py`
  - Current useful behavior: `ConnectionManager.active_connections` exists
  - End state: adds coordinator-visible registration/shutdown hook and handshake/work-start drain checks

- `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
  - Current problem: some WebSocket routes accept the socket before deeper work starts
  - End state: explicit handshake/start-boundary drain checks for covered shutdown-sensitive flows

- `tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py`
  - Current useful behavior: owns an `SSEStream`-based long-lived transport
  - End state: covered by explicit SSE start-boundary drain checks and coordinator-visible ownership

- `tldw_Server_API/tests/Services/test_main_lifecycle_contract.py`
  - Extend reentrancy assertions to cover app-scoped lifecycle state reset and event order

- `tldw_Server_API/tests/CI/test_e2e_inprocess_client_contract.py`
  - Keep started-TestClient fallback behavior intact while coordinator state moves off module globals

### New implementation files to create

- `tldw_Server_API/app/services/shutdown_models.py`
  - `Enum`/`Literal`-backed models for lifecycle phase, shutdown phase, policy, component result, deadline data

- `tldw_Server_API/app/services/shutdown_coordinator.py`
  - registration API
  - deadline/budget logic
  - ordered parallel phase runner
  - structured shutdown summary generation

- `tldw_Server_API/app/services/shutdown_legacy_adapters.py`
  - wraps existing `main.py` shutdown hooks into coordinator registrations
  - keeps migration logic out of `main.py`

- `tldw_Server_API/app/core/Security/drain_gate_middleware.py`
  - early HTTP admission gate based on coordinator state
  - narrow allowlist support for control-plane routes

- `tldw_Server_API/app/services/shutdown_transport_registry.py`
  - small shared protocol for long-lived transport families to expose active session counts and deadline-bounded close/drain hooks

- `Docs/Design/2026-03-30-shutdown-dependency-inventory.md`
  - records Stage 1.5 ordering edges, aggregate helpers, unknowns, and transport ownership inventory

### New test files to create

- `tldw_Server_API/tests/Services/test_app_lifecycle_state.py`
- `tldw_Server_API/tests/Services/test_main_readiness_shutdown.py`
- `tldw_Server_API/tests/Services/test_drain_gate_middleware.py`
- `tldw_Server_API/tests/Services/test_shutdown_coordinator.py`
- `tldw_Server_API/tests/Services/test_shutdown_transport_registry.py`
- `tldw_Server_API/tests/Services/test_executor_registry_shutdown.py`

## Task 1: Introduce App-Scoped Lifecycle State

**Files:**
- Modify: `tldw_Server_API/app/services/app_lifecycle.py`
- Modify: `tldw_Server_API/tests/Services/test_main_lifecycle_contract.py`
- Create: `tldw_Server_API/tests/Services/test_app_lifecycle_state.py`

- [ ] **Step 1: Write the failing lifecycle-state unit tests**

```python
from fastapi import FastAPI

from tldw_Server_API.app.services.app_lifecycle import (
    get_or_create_lifecycle_state,
    mark_lifecycle_shutdown,
    mark_lifecycle_startup,
)


def test_get_or_create_lifecycle_state_is_app_scoped() -> None:
    app = FastAPI()
    state = get_or_create_lifecycle_state(app)
    assert state.phase == "starting"
    assert state.ready is False


def test_mark_lifecycle_startup_and_shutdown_update_app_state() -> None:
    app = FastAPI()
    state = get_or_create_lifecycle_state(app)
    mark_lifecycle_startup(app)
    assert state.phase == "ready"
    assert state.ready is True
    mark_lifecycle_shutdown(app)
    assert state.phase == "draining"
    assert state.ready is False
```

- [ ] **Step 2: Run the new lifecycle-state tests and the existing contract test**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_app_lifecycle_state.py \
  tldw_Server_API/tests/Services/test_main_lifecycle_contract.py -v
```

Expected: FAIL because `app_lifecycle.py` does not yet expose app-scoped lifecycle state helpers.

- [ ] **Step 3: Implement app-scoped lifecycle state in `app_lifecycle.py`**

```python
@dataclass
class AppLifecycleState:
    phase: Literal["starting", "ready", "draining", "stopped"] = "starting"
    ready: bool = False
    draining: bool = False


def get_or_create_lifecycle_state(app: FastAPI) -> AppLifecycleState:
    state = getattr(app.state, "_tldw_lifecycle_state", None)
    if state is None:
        state = AppLifecycleState()
        app.state._tldw_lifecycle_state = state
    return state


def mark_lifecycle_startup(app: FastAPI) -> AppLifecycleState:
    state = get_or_create_lifecycle_state(app)
    state.phase = "ready"
    state.ready = True
    state.draining = False
    _append_lifecycle_event(app, "startup")
    return state
```

Implementation notes:

- keep lifecycle event logging behavior intact for existing tests
- remove the requirement to pass a mutable `READINESS_STATE` mapping around
- add a reset helper for tests and repeated lifespan reuse

- [ ] **Step 4: Update the existing lifecycle contract test to assert app-scoped state reset**

Add assertions like:

```python
assert app.state._tldw_lifecycle_state.phase == "ready"
assert app.state._tldw_lifecycle_state.ready is True
```

after startup, and:

```python
assert app.state._tldw_lifecycle_state.phase == "draining"
assert app.state._tldw_lifecycle_state.ready is False
```

after shutdown.

- [ ] **Step 5: Re-run the targeted lifecycle tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_app_lifecycle_state.py \
  tldw_Server_API/tests/Services/test_main_lifecycle_contract.py -v
```

Expected: PASS

- [ ] **Step 6: Commit the lifecycle-state slice**

```bash
git add \
  tldw_Server_API/app/services/app_lifecycle.py \
  tldw_Server_API/tests/Services/test_app_lifecycle_state.py \
  tldw_Server_API/tests/Services/test_main_lifecycle_contract.py
git commit -m "refactor: make lifecycle state app scoped"
```

## Task 2: Bridge Readiness Endpoints Off Module Globals

**Files:**
- Modify: `tldw_Server_API/app/main.py`
- Create: `tldw_Server_API/tests/Services/test_main_readiness_shutdown.py`
- Modify: `tldw_Server_API/tests/CI/test_e2e_inprocess_client_contract.py`

- [ ] **Step 1: Write the failing readiness tests**

```python
from fastapi.testclient import TestClient


def test_ready_endpoint_returns_503_when_draining() -> None:
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.services.app_lifecycle import get_or_create_lifecycle_state

    state = get_or_create_lifecycle_state(app)
    state.phase = "draining"
    state.ready = False
    state.draining = True

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["reason"] == "shutdown_in_progress"
```

Also add a test that forces the exception branch in `readiness_check()` and asserts a non-success HTTP status rather than a plain `200` dict response.

- [ ] **Step 2: Run the readiness tests and the started-TestClient contract**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_main_readiness_shutdown.py \
  tldw_Server_API/tests/CI/test_e2e_inprocess_client_contract.py -v
```

Expected: FAIL because `readiness_check()` still reads `READINESS_STATE` and returns bare dicts on some non-ready paths.

- [ ] **Step 3: Refactor `readiness_check()` to use app-scoped state**

Change the route signature so it can read `request.app.state`, for example:

```python
async def readiness_check(request: Request) -> JSONResponse:
    lifecycle = get_or_create_lifecycle_state(request.app)
    if lifecycle.draining or not lifecycle.ready:
        return JSONResponse(
            {"status": "not_ready", "reason": "shutdown_in_progress"},
            status_code=503,
        )
```

Implementation notes:

- remove the `READINESS_STATE` dependency from control-plane routes
- keep `/health`, `/ready`, and `/health/ready` registration behavior unchanged
- ensure the exception path returns `JSONResponse(..., status_code=503)`

- [ ] **Step 4: Update the fallback-client contract test only if needed**

If the readiness refactor changes import-time assumptions, add a small assertion that the fallback still reads the same FastAPI app object and successfully hits `/health` after `client.__enter__()`.

- [ ] **Step 5: Re-run readiness and fallback coverage**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_main_readiness_shutdown.py \
  tldw_Server_API/tests/Services/test_main_lifecycle_contract.py \
  tldw_Server_API/tests/CI/test_e2e_inprocess_client_contract.py -v
```

Expected: PASS

- [ ] **Step 6: Commit the readiness bridge**

```bash
git add \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Services/test_main_readiness_shutdown.py \
  tldw_Server_API/tests/CI/test_e2e_inprocess_client_contract.py
git commit -m "fix: move readiness checks to app lifecycle state"
```

## Task 3: Add The HTTP Drain Gate And Work-Start Guard Helpers

**Files:**
- Create: `tldw_Server_API/app/core/Security/drain_gate_middleware.py`
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/services/app_lifecycle.py`
- Create: `tldw_Server_API/tests/Services/test_drain_gate_middleware.py`

- [ ] **Step 1: Write failing drain-gate tests**

```python
def test_drain_gate_allows_health_but_rejects_mutation(test_app, draining_client):
    ok = draining_client.get("/health")
    blocked = draining_client.post("/api/v1/chat/completions", json={"messages": []})
    assert ok.status_code == 200
    assert blocked.status_code == 503
    assert blocked.json()["reason"] == "shutdown_in_progress"
```

Also add a test for the work-start helper:

```python
def test_assert_may_start_work_raises_when_draining(app):
    state = get_or_create_lifecycle_state(app)
    state.draining = True
    with pytest.raises(HTTPException):
        assert_may_start_work(app, kind="job_enqueue")
```

- [ ] **Step 2: Run the drain-gate tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_drain_gate_middleware.py -v
```

Expected: FAIL because no drain gate middleware or work-start assertion helper exists yet.

- [ ] **Step 3: Implement the middleware and helper**

```python
class DrainGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        lifecycle = get_or_create_lifecycle_state(request.app)
        if lifecycle.draining and not _is_allowlisted_control_plane_path(request):
            return JSONResponse(
                {"status": "not_ready", "reason": "shutdown_in_progress"},
                status_code=503,
            )
        return await call_next(request)


def assert_may_start_work(app: FastAPI, kind: str) -> None:
    lifecycle = get_or_create_lifecycle_state(app)
    if lifecycle.draining:
        raise HTTPException(
            status_code=503,
            detail={"message": "Shutdown in progress", "kind": kind},
        )
```

Implementation notes:

- add the middleware early in the HTTP stack, before expensive auth/dependency work
- keep the allowlist narrow and route-specific
- store the allowlist in one place so readiness/health tests stay stable

- [ ] **Step 4: Install the middleware in `main.py`**

Place it after the minimum request-context middleware needed for request IDs or equivalent context, but before heavyweight auth/logging/budget middleware.

- [ ] **Step 5: Re-run the drain-gate tests and a quick control-plane smoke test**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_drain_gate_middleware.py \
  tldw_Server_API/tests/Services/test_main_readiness_shutdown.py -v
```

Expected: PASS

- [ ] **Step 6: Commit the admission-gate slice**

```bash
git add \
  tldw_Server_API/app/core/Security/drain_gate_middleware.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/app/services/app_lifecycle.py \
  tldw_Server_API/tests/Services/test_drain_gate_middleware.py
git commit -m "feat: add shutdown drain gate middleware"
```

## Task 4: Build Coordinator Models, Registration, And Deadline Logic

**Files:**
- Create: `tldw_Server_API/app/services/shutdown_models.py`
- Create: `tldw_Server_API/app/services/shutdown_coordinator.py`
- Create: `tldw_Server_API/tests/Services/test_shutdown_coordinator.py`

- [ ] **Step 1: Write failing coordinator unit tests**

```python
async def test_coordinator_runs_components_by_phase_and_records_summary():
    coordinator = ShutdownCoordinator(profile="dev_fast")
    events = []

    coordinator.register(component("producer-a", phase="producers", stop=lambda: events.append("producer")))
    coordinator.register(component("resource-a", phase="resources", stop=lambda: events.append("resource")))

    summary = await coordinator.shutdown()

    assert events == ["producer", "resource"]
    assert summary.components["producer-a"].result == "stopped"
```

Add separate tests for:

- remaining-time budget allocation
- hard cutoff after soft overrun
- best-effort components not blocking exit
- idempotent second shutdown call

- [ ] **Step 2: Run the coordinator tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py -v
```

Expected: FAIL because the coordinator modules do not exist.

- [ ] **Step 3: Implement models and coordinator primitives**

```python
@dataclass
class ShutdownComponent:
    name: str
    phase: ShutdownPhase
    policy: ShutdownPolicy
    default_timeout_ms: int
    stop: Callable[[], Awaitable[None] | None]


class ShutdownCoordinator:
    async def shutdown(self) -> ShutdownSummary:
        self._transition_to_draining()
        for phase in ORDERED_PHASES:
            await self._run_phase(phase)
        return self._summary
```

Implementation notes:

- keep registration and summary logic pure enough for fast unit tests
- use `asyncio.gather(..., return_exceptions=True)` within a phase
- compute each phase budget from remaining deadline, not static per-phase constants
- make the second call to `shutdown()` return the existing summary or a clearly marked idempotent result

- [ ] **Step 4: Re-run coordinator tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the coordinator primitives**

```bash
git add \
  tldw_Server_API/app/services/shutdown_models.py \
  tldw_Server_API/app/services/shutdown_coordinator.py \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py
git commit -m "feat: add shutdown coordinator core"
```

## Task 5: Inventory Legacy Shutdown Dependencies And Add Shadow Mode

**Files:**
- Create: `tldw_Server_API/app/services/shutdown_legacy_adapters.py`
- Modify: `tldw_Server_API/app/main.py`
- Create: `Docs/Design/2026-03-30-shutdown-dependency-inventory.md`

- [ ] **Step 1: Document the current teardown inventory before changing behavior**

Create `Docs/Design/2026-03-30-shutdown-dependency-inventory.md` with sections for:

- ordered shutdown groups already implicit in `main.py`
- duplicate owners (usage aggregator, AuthNZ scheduler, etc.)
- aggregate helpers that hide serial work (`shutdown_all_registered_executors`, cache shutdown bundles)
- long-lived transport owners (MCP, Prompt Studio, audio WebSockets, ingest SSE)
- unknown ordering edges that need instrumentation

- [ ] **Step 2: Write a failing test for adapter registration inventory**

```python
def test_build_legacy_shutdown_plan_registers_known_components():
    plan = build_legacy_shutdown_plan(fake_app_state())
    assert "authnz_scheduler" in {component.name for component in plan}
    assert "usage_aggregator" in {component.name for component in plan}
```

- [ ] **Step 3: Run the adapter inventory test**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py -k legacy -v
```

Expected: FAIL because the legacy adapter builder does not exist.

- [ ] **Step 4: Implement `shutdown_legacy_adapters.py` and wire shadow mode in `main.py`**

```python
def build_legacy_shutdown_plan(app: FastAPI, locals_map: Mapping[str, Any]) -> list[ShutdownComponent]:
    return [
        shutdown_component(
            name="authnz_scheduler",
            phase="acceptors",
            policy="prod_drain",
            stop=lambda: _stop_authnz_scheduler_if_started(locals_map),
        ),
        ...
    ]
```

Implementation notes:

- shadow mode should log intended phase grouping and timing without yet replacing every real shutdown call
- keep the first integration narrow: transition phase plus inventory/summary visibility
- do not parallelize unknown dependencies in this task

- [ ] **Step 5: Re-run the adapter test and a lifecycle smoke test**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py \
  tldw_Server_API/tests/Services/test_main_lifecycle_contract.py -v
```

Expected: PASS

- [ ] **Step 6: Commit the shadow-mode inventory slice**

```bash
git add \
  tldw_Server_API/app/services/shutdown_legacy_adapters.py \
  tldw_Server_API/app/main.py \
  Docs/Design/2026-03-30-shutdown-dependency-inventory.md
git commit -m "refactor: inventory legacy shutdown dependencies"
```

## Task 6: Move Legacy Shutdown Into Ordered Parallel Phases

**Files:**
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/services/shutdown_coordinator.py`
- Modify: `tldw_Server_API/app/services/shutdown_legacy_adapters.py`
- Modify: `tldw_Server_API/tests/Services/test_shutdown_coordinator.py`

- [ ] **Step 1: Write failing integration-style tests for ordered phased shutdown**

```python
async def test_legacy_adapters_shutdown_in_phase_order():
    events = []
    coordinator = ShutdownCoordinator(profile="dev_fast")
    coordinator.register(component("producer", phase="producers", stop=lambda: events.append("producer")))
    coordinator.register(component("worker", phase="workers", stop=lambda: events.append("worker")))
    coordinator.register(component("resource", phase="resources", stop=lambda: events.append("resource")))

    await coordinator.shutdown()

    assert events == ["producer", "worker", "resource"]
```

Add a second test that registers multiple same-phase components and asserts they were awaited via a parallel gather rather than serial order assumptions.

- [ ] **Step 2: Run the phase-order tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py -k "phase or parallel" -v
```

Expected: FAIL until legacy adapters and coordinator phase execution are connected.

- [ ] **Step 3: Replace the serial `main.py` teardown with coordinator-driven phase execution**

Migration rules:

- keep transition logic first: readiness false + acquire gate true
- map existing stop hooks into `acceptors`, `producers`, `workers`, `resources`, `finalizers`
- preserve explicitly documented ordering edges from the inventory doc
- keep duplicate stop responsibilities single-owned through the adapter layer

Minimal shape:

```python
coordinator = get_or_create_shutdown_coordinator(app)
register_legacy_shutdown_components(coordinator, app, locals())
summary = await coordinator.shutdown()
logger.bind(shutdown_summary=summary.to_log_dict()).info("Shutdown summary")
```

- [ ] **Step 4: Re-run the coordinator and lifecycle integration tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py \
  tldw_Server_API/tests/Services/test_main_lifecycle_contract.py \
  tldw_Server_API/tests/Services/test_main_readiness_shutdown.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the coordinator-driven teardown**

```bash
git add \
  tldw_Server_API/app/main.py \
  tldw_Server_API/app/services/shutdown_coordinator.py \
  tldw_Server_API/app/services/shutdown_legacy_adapters.py \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py
git commit -m "refactor: run app shutdown through coordinator phases"
```

## Task 7: Add Transport Ownership And Resource Decomposition

**Files:**
- Create: `tldw_Server_API/app/services/shutdown_transport_registry.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/server.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_websocket.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py`
- Modify: `tldw_Server_API/app/core/Utils/executor_registry.py`
- Create: `tldw_Server_API/tests/Services/test_shutdown_transport_registry.py`
- Create: `tldw_Server_API/tests/Services/test_executor_registry_shutdown.py`

- [ ] **Step 1: Write failing tests for transport visibility and work-start race protection**

```python
def test_transport_registry_reports_active_session_counts():
    registry = ShutdownTransportRegistry()
    registry.register("prompt_studio_ws", active_count=lambda: 2, close=lambda deadline: None)
    assert registry.snapshot()["prompt_studio_ws"].active_count == 2
```

Add coverage for:

- MCP connection shutdown hook presence
- Prompt Studio registry hookup
- audio WebSocket start-boundary guard firing after handshake setup but before synthesis work starts
- ingest SSE start-boundary guard rejecting new session creation during drain

- [ ] **Step 2: Run the new transport and executor tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_shutdown_transport_registry.py \
  tldw_Server_API/tests/Services/test_executor_registry_shutdown.py -v
```

Expected: FAIL because the shared transport registry and executor decomposition behavior do not exist yet.

- [ ] **Step 3: Implement the shared transport registry and wire covered owners**

Implementation notes:

- MCP server should register its `connections` map and `_close_all_connections()` path
- Prompt Studio should expose its `ConnectionManager.active_connections`
- audio WebSocket handlers should call `assert_may_start_work(...)` before expensive synthesis/transcription start
- ingest SSE creation should reject with `503` before stream creation when draining

Example helper shape:

```python
@dataclass
class ManagedTransport:
    name: str
    active_count: Callable[[], int]
    close_or_drain: Callable[[float], Awaitable[None] | None]
```

- [ ] **Step 4: Decompose or bound executor shutdown**

Update `executor_registry.py` so coordinator-visible shutdown is not a hidden serial black box. Accept either of these approaches:

- expose `snapshot_registered_executors()` so the coordinator can register one component per executor, or
- make `shutdown_all_registered_executors()` accept a deadline and shut executors down concurrently

Do not leave the current one-by-one `await asyncio.to_thread(...)` loop unchanged.

- [ ] **Step 5: Re-run transport and resource tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_shutdown_transport_registry.py \
  tldw_Server_API/tests/Services/test_executor_registry_shutdown.py \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py -v
```

Expected: PASS

- [ ] **Step 6: Commit the transport/resource ownership slice**

```bash
git add \
  tldw_Server_API/app/services/shutdown_transport_registry.py \
  tldw_Server_API/app/core/MCP_unified/server.py \
  tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_websocket.py \
  tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py \
  tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py \
  tldw_Server_API/app/core/Utils/executor_registry.py \
  tldw_Server_API/tests/Services/test_shutdown_transport_registry.py \
  tldw_Server_API/tests/Services/test_executor_registry_shutdown.py
git commit -m "feat: add shutdown transport ownership and executor visibility"
```

## Task 8: Run Regression Coverage And Security Verification

**Files:**
- Modify: `tldw_Server_API/tests/Services/test_main_lifecycle_contract.py`
- Modify: `tldw_Server_API/tests/CI/test_e2e_inprocess_client_contract.py`
- Optionally modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_ablate_api.py`
- Optionally modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_agentic_api.py`
- Optionally modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_batch_checkpoint_api.py`
- Optionally modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_batch_resume_api.py`
- Optionally modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_benchmarks_ablation.py`
- Optionally modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_doc_researcher_api.py`

- [ ] **Step 1: Add any missing regression tests for lifespan-off and started-client fallback**

At minimum, cover:

- repeated `TestClient(app)` reuse on the same app object
- `lifespan="off"` clients still bypass shutdown coordinator safely
- started TestClient fallback still enters startup/shutdown correctly
- readiness endpoints remain callable during drain and return `503`

- [ ] **Step 2: Run the focused regression matrix**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Services/test_app_lifecycle_state.py \
  tldw_Server_API/tests/Services/test_main_lifecycle_contract.py \
  tldw_Server_API/tests/Services/test_main_readiness_shutdown.py \
  tldw_Server_API/tests/Services/test_drain_gate_middleware.py \
  tldw_Server_API/tests/Services/test_shutdown_coordinator.py \
  tldw_Server_API/tests/Services/test_shutdown_transport_registry.py \
  tldw_Server_API/tests/Services/test_executor_registry_shutdown.py \
  tldw_Server_API/tests/CI/test_e2e_inprocess_client_contract.py -v
```

Expected: PASS

- [ ] **Step 3: Run the known lifespan-off RAG regressions**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/RAG_NEW/integration/test_rag_ablate_api.py \
  tldw_Server_API/tests/RAG_NEW/integration/test_rag_agentic_api.py \
  tldw_Server_API/tests/RAG_NEW/integration/test_rag_batch_checkpoint_api.py \
  tldw_Server_API/tests/RAG_NEW/integration/test_rag_batch_resume_api.py \
  tldw_Server_API/tests/RAG_NEW/integration/test_rag_benchmarks_ablation.py \
  tldw_Server_API/tests/RAG_NEW/integration/test_rag_doc_researcher_api.py -v
```

Expected: PASS, or else document exactly which tests still rely on legacy assumptions and patch them in the same slice.

- [ ] **Step 4: Run Bandit on the touched shutdown scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/main.py \
  tldw_Server_API/app/services \
  tldw_Server_API/app/core/Security/drain_gate_middleware.py \
  tldw_Server_API/app/core/Utils/executor_registry.py \
  tldw_Server_API/app/core/MCP_unified/server.py \
  tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py \
  tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py \
  tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_websocket.py \
  -f json -o /tmp/bandit_shutdown_coordinator.json
```

Expected: No new findings in changed code. If findings appear, fix them before claiming completion.

- [ ] **Step 5: Commit the verification pass**

```bash
git add \
  tldw_Server_API/tests/Services/test_main_lifecycle_contract.py \
  tldw_Server_API/tests/CI/test_e2e_inprocess_client_contract.py \
  tldw_Server_API/tests/RAG_NEW/integration
git commit -m "test: verify shutdown coordinator lifecycle regressions"
```

## Exit Criteria

Do not mark this work complete until all of the following are true:

- readiness and drain state are app-scoped, not controlled by module-global `READINESS_STATE`
- `/ready` and `/health/ready` return `503` on shutdown-in-progress and other non-ready paths
- the HTTP drain gate is installed early enough to reject non-allowlisted work before expensive middleware/dependencies run
- work-start boundary checks exist for the covered long-lived or workload-starting flows
- shutdown runs through coordinator phases rather than the old large serial block in `main.py`
- duplicate shutdown ownership in `main.py` is removed or reduced to adapter registration only
- covered transport families expose coordinator-visible session ownership
- executor shutdown no longer hides a serial black box from the coordinator
- targeted regression tests and Bandit pass

## Execution Notes

- Activate the virtual environment before every Python or pytest command:

```bash
source .venv/bin/activate
```

- Prefer the smallest passing slice per task. Do not jump ahead to later phases until the current task’s tests pass.
- If one migration step reveals unexpected shutdown ordering edges, update `Docs/Design/2026-03-30-shutdown-dependency-inventory.md` before changing phase parallelism.
- If a transport family or worker cannot safely support the new drain contract yet, classify it explicitly as `cancel_only` or `best_effort`; do not imply resumability that the code does not have.
