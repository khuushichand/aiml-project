# Main Bootstrap and Router Modularization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce blast radius and regression risk by decomposing `app/main.py` into explicit router-registration and lifecycle modules while preserving API surface.

**Architecture:** Keep `main.py` as a thin composition root. Move router registration into dedicated registry functions grouped by domain and move startup/shutdown wiring into lifecycle helpers. Preserve behavior via characterization tests before extraction.

**Tech Stack:** FastAPI, pytest, pytest-asyncio, Loguru, existing endpoint modules.

---

### Task 1: Characterize Current App Wiring
**Status:** Complete

**Files:**
- Create: `tldw_Server_API/tests/Services/test_main_router_contract.py`
- Create: `tldw_Server_API/tests/Services/test_main_lifecycle_contract.py`
- Reference: `tldw_Server_API/app/main.py`

**Step 1: Write the failing tests**

```python
def test_router_contract_includes_expected_prefixes(app):
    paths = {route.path for route in app.routes}
    assert "/api/v1/chat/completions" in paths
    assert "/api/v1/media/process" in paths


def test_startup_shutdown_contract_runs_without_exception(app):
    # Use FastAPI lifespan context to assert startup/shutdown succeeds.
    assert app is not None
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_main_router_contract.py -v`
Expected: FAIL because test scaffolding/fixtures are incomplete.

**Step 3: Write minimal implementation**

```python
# Add app fixture imports and minimal route/lifespan assertions.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_main_router_contract.py tldw_Server_API/tests/Services/test_main_lifecycle_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Services/test_main_router_contract.py tldw_Server_API/tests/Services/test_main_lifecycle_contract.py
git commit -m "test(main): lock router and lifecycle contracts before extraction"
```

### Task 2: Extract Router Registry
**Status:** Complete

**Files:**
- Create: `tldw_Server_API/app/api/v1/router_registry.py`
- Create: `tldw_Server_API/app/api/v1/router_groups/core.py`
- Create: `tldw_Server_API/app/api/v1/router_groups/content.py`
- Create: `tldw_Server_API/app/api/v1/router_groups/admin.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Services/test_main_router_contract.py`

**Step 1: Write the failing test**

```python
def test_router_registry_idempotent_registration(app_factory):
    app = app_factory()
    register_all_routers(app)
    register_all_routers(app)
    assert len({r.path for r in app.routes}) == len(app.routes)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_main_router_contract.py::test_router_registry_idempotent_registration -v`
Expected: FAIL with import error for `register_all_routers`.

**Step 3: Write minimal implementation**

```python
# router_registry.py

def register_all_routers(app):
    register_core_routers(app)
    register_content_routers(app)
    register_admin_routers(app)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_main_router_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/router_registry.py tldw_Server_API/app/api/v1/router_groups/core.py tldw_Server_API/app/api/v1/router_groups/content.py tldw_Server_API/app/api/v1/router_groups/admin.py tldw_Server_API/app/main.py tldw_Server_API/tests/Services/test_main_router_contract.py
git commit -m "refactor(main): extract api router registry"
```

### Task 3: Extract Startup/Shutdown Lifecycle
**Status:** Complete

**Files:**
- Create: `tldw_Server_API/app/services/app_lifecycle.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Services/test_main_lifecycle_contract.py`

**Step 1: Write the failing test**

```python
def test_lifecycle_hooks_called_in_order(monkeypatch):
    calls = []
    # monkeypatch startup/shutdown hook functions to append to calls
    assert calls == ["startup", "shutdown"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_main_lifecycle_contract.py::test_lifecycle_hooks_called_in_order -v`
Expected: FAIL because hooks are still inlined in `main.py`.

**Step 3: Write minimal implementation**

```python
# app_lifecycle.py

def register_lifecycle(app):
    @app.on_event("startup")
    async def _startup():
        ...

    @app.on_event("shutdown")
    async def _shutdown():
        ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_main_lifecycle_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/app_lifecycle.py tldw_Server_API/app/main.py tldw_Server_API/tests/Services/test_main_lifecycle_contract.py
git commit -m "refactor(main): extract app lifecycle wiring"
```

### Task 4: Verify No API Surface Regression
**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Services/test_main_router_contract.py`
- Run-only: existing smoke tests and endpoint contract tests

**Step 1: Write the failing test**

```python
def test_openapi_contains_critical_tags(client):
    spec = client.get("/openapi.json").json()
    tags = {t["name"] for t in spec.get("tags", [])}
    assert "chat" in tags
    assert "audio" in tags
    assert "rag-unified" in tags
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_main_router_contract.py::test_openapi_contains_critical_tags -v`
Expected: FAIL if tag registration drifted during extraction.

**Step 3: Write minimal implementation**

```python
# Ensure registry preserves existing prefixes/tags and conditional routes.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_main_router_contract.py tldw_Server_API/tests/Services/test_main_lifecycle_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Services/test_main_router_contract.py tldw_Server_API/app/main.py
git commit -m "test(main): enforce openapi and route registration parity"
```
