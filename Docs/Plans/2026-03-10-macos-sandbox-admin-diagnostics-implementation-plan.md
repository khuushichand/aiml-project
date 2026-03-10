# macOS Sandbox Admin Diagnostics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an admin-only macOS sandbox diagnostics endpoint backed by a shared probe layer, while keeping `/api/v1/sandbox/runtimes` summarized and aligned with the same readiness logic.

**Architecture:** Add a new `macos_diagnostics.py` probe module in the sandbox core to compute host/helper/template/runtime readiness from existing config and env signals. Derive the runtime subsection from the same runner preflight path already used by admission and feature discovery, then layer on extra operator metadata such as optional helper/template source details. Expose that payload through `SandboxService` and a new admin route while keeping `/api/v1/sandbox/runtimes` shallow.

**Tech Stack:** FastAPI, Pydantic, pytest, existing sandbox runtime preflight code, Loguru, Bandit

**Environment note:** Before any `python` or `pytest` command in this plan, activate the project virtual environment. In a linked worktree, use the shared repo virtualenv from the main checkout rather than assuming the worktree has its own `.venv`.

---

### Task 1: Build the Shared macOS Diagnostics Probe Layer

**Files:**
- Create: `tldw_Server_API/app/core/Sandbox/macos_diagnostics.py`
- Check: `tldw_Server_API/app/core/Sandbox/runners/vz_common.py`
- Check: `tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py`
- Check: `tldw_Server_API/app/core/Sandbox/macos_virtualization/helper_client.py`
- Check: `tldw_Server_API/app/core/Sandbox/image_store.py`
- Test: `tldw_Server_API/tests/sandbox/test_macos_diagnostics.py`

**Step 1: Write the failing probe tests**

Create `tldw_Server_API/tests/sandbox/test_macos_diagnostics.py` with focused unit tests for host, helper, template, and derived runtime status behavior:

```python
from tldw_Server_API.app.core.Sandbox.macos_diagnostics import collect_macos_diagnostics


def test_collect_macos_diagnostics_reports_missing_helper_and_templates(monkeypatch) -> None:
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.macos_diagnostics.sys.platform", "darwin")
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.macos_diagnostics.platform.machine", lambda: "arm64")
    monkeypatch.delenv("TLDW_SANDBOX_MACOS_HELPER_PATH", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_MACOS_HELPER_READY", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_LINUX_TEMPLATE_SOURCE", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_LINUX_TEMPLATE_READY", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY", raising=False)

    data = collect_macos_diagnostics()

    assert data["host"]["supported"] is True
    assert data["helper"]["configured"] is False
    assert data["helper"]["path"] is None
    assert data["helper"]["ready"] is False
    assert data["templates"]["vz_linux"]["configured"] is False
    assert data["templates"]["vz_linux"]["source"] is None
    assert data["templates"]["vz_linux"]["ready"] is False
    assert "macos_helper_missing" in data["runtimes"]["vz_linux"]["reasons"]
    assert data["runtimes"]["vz_linux"]["execution_mode"] == "none"


def test_collect_macos_diagnostics_separates_policy_from_host_readiness(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_AVAILABLE", "1")
    monkeypatch.delenv("TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED", raising=False)

    data = collect_macos_diagnostics()

    assert data["runtimes"]["seatbelt"]["supported_trust_levels"] == ["trusted"]
    assert data["runtimes"]["seatbelt"]["available"] in (True, False)


def test_collect_macos_diagnostics_uses_optional_operator_metadata_env(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_MACOS_HELPER_PATH", "/tmp/macos-helper")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_LINUX_TEMPLATE_SOURCE", "/tmp/vz-linux.img")

    data = collect_macos_diagnostics()

    assert data["helper"]["path"] == "/tmp/macos-helper"
    assert data["templates"]["vz_linux"]["source"] == "/tmp/vz-linux.img"
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest tldw_Server_API/tests/sandbox/test_macos_diagnostics.py -q
```

Expected: FAIL because `macos_diagnostics.py` does not exist yet.

**Step 3: Write the minimal diagnostics implementation**

Implement a side-effect-free probe module that returns one top-level payload with `host`, `helper`, `templates`, and `runtimes`.

Start with simple helpers like:

```python
def probe_host() -> dict[str, object]:
    facts = vz_host_facts()
    reasons: list[str] = []
    if facts["os"] != "darwin":
        reasons.append("macos_required")
    if not facts["apple_silicon"]:
        reasons.append("apple_silicon_required")
    return {
        **facts,
        "macos_version": platform.mac_ver()[0] or None,
        "supported": not reasons,
        "reasons": reasons,
    }


def collect_macos_diagnostics() -> dict[str, object]:
    host = probe_host()
    helper = probe_helper()
    templates = probe_templates()
    runtime_preflights = collect_runtime_preflights(network_policy="deny_all")
    runtimes = probe_runtime_statuses(
        runtime_preflights=runtime_preflights,
        host=host,
        helper=helper,
        templates=templates,
    )
    return {
        "host": host,
        "helper": helper,
        "templates": templates,
        "runtimes": runtimes,
    }
```

Add a minimal diagnostics-only metadata contract for operator detail:

- `TLDW_SANDBOX_MACOS_HELPER_PATH`
- `TLDW_SANDBOX_VZ_LINUX_TEMPLATE_SOURCE`
- `TLDW_SANDBOX_VZ_MACOS_TEMPLATE_SOURCE`

These keys should be optional. When they are absent, the diagnostics payload should return `path=None` / `source=None` rather than inventing fake filesystem locations.

Keep this slice read-only:

- do not start the helper
- do not create templates or clones
- do not boot VMs

**Step 4: Run the probe tests again**

Run:

```bash
python -m pytest tldw_Server_API/tests/sandbox/test_macos_diagnostics.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/macos_diagnostics.py tldw_Server_API/tests/sandbox/test_macos_diagnostics.py
git commit -m "feat: add macOS sandbox diagnostics probes"
```

### Task 2: Add Service Accessors and Typed Admin Response Models

**Files:**
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py`
- Check: `tldw_Server_API/app/core/Sandbox/runtime_capabilities.py`
- Test: `tldw_Server_API/tests/sandbox/test_macos_diagnostics.py`

**Step 1: Extend the failing tests for service and schema coverage**

Add tests that prove the service exposes diagnostics and the admin schema accepts the payload:

```python
from tldw_Server_API.app.api.v1.schemas.sandbox_schemas import SandboxAdminMacOSDiagnosticsResponse
from tldw_Server_API.app.core.Sandbox.service import SandboxService


def test_service_macos_diagnostics_returns_probe_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Sandbox.service.collect_macos_diagnostics",
        lambda: {"host": {}, "helper": {}, "templates": {}, "runtimes": {}},
    )
    svc = SandboxService()
    assert svc.macos_diagnostics() == {"host": {}, "helper": {}, "templates": {}, "runtimes": {}}


def test_admin_schema_accepts_macos_diagnostics_payload() -> None:
    payload = {
        "host": {"os": "darwin", "arch": "arm64", "apple_silicon": True, "macos_version": "15.0", "supported": True, "reasons": []},
        "helper": {"configured": True, "path": "/tmp/helper", "exists": True, "executable": True, "ready": True, "transport": "fake", "reasons": []},
        "templates": {"vz_linux": {"configured": True, "ready": True, "source": "/tmp/vz-linux.img", "reasons": []}},
        "runtimes": {"vz_linux": {"available": True, "supported_trust_levels": ["trusted", "standard", "untrusted"], "reasons": [], "execution_mode": "fake", "remediation": None}},
    }
    model = SandboxAdminMacOSDiagnosticsResponse.model_validate(payload)
    assert model.host.supported is True
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest tldw_Server_API/tests/sandbox/test_macos_diagnostics.py -q
```

Expected: FAIL because the service accessor and admin response models do not exist yet.

**Step 3: Add the service method and Pydantic models**

In `service.py`, add a small pass-through:

```python
from .macos_diagnostics import collect_macos_diagnostics


def macos_diagnostics(self) -> dict[str, object]:
    return collect_macos_diagnostics()
```

In `sandbox_schemas.py`, add explicit admin models for:

- host status
- helper status
- template status
- runtime diagnostics entry
- top-level admin response

Keep these separate from `SandboxRuntimeInfo`. The admin model is richer and should not silently widen the public discovery schema.

**Step 4: Run the tests again**

Run:

```bash
python -m pytest tldw_Server_API/tests/sandbox/test_macos_diagnostics.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/service.py tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py tldw_Server_API/tests/sandbox/test_macos_diagnostics.py
git commit -m "feat: add macOS sandbox diagnostics service contract"
```

### Task 3: Add the Admin Diagnostics Endpoint and RBAC Coverage

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/sandbox.py`
- Create: `tldw_Server_API/tests/sandbox/test_admin_macos_diagnostics.py`
- Modify: `tldw_Server_API/tests/sandbox/test_admin_rbac.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_sandbox_admin_permissions_claims.py`

**Step 1: Write the failing endpoint and authorization tests**

Create `tldw_Server_API/tests/sandbox/test_admin_macos_diagnostics.py`:

```python
def test_admin_macos_diagnostics_returns_structured_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        sandbox_mod._service,
        "macos_diagnostics",
        lambda: {
            "host": {"os": "darwin", "arch": "arm64", "apple_silicon": True, "macos_version": "15.0", "supported": True, "reasons": []},
            "helper": {"configured": False, "path": None, "exists": False, "executable": False, "ready": False, "transport": None, "reasons": ["macos_helper_missing"]},
            "templates": {},
            "runtimes": {},
        },
        raising=False,
    )
    with TestClient(_build_app_with_overrides(_make_principal(roles=[ROLE_ADMIN], is_admin=True))) as client:
        resp = client.get("/api/v1/sandbox/admin/macos-diagnostics")
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"host", "helper", "templates", "runtimes"}
```

Extend `test_admin_rbac.py` and `test_sandbox_admin_permissions_claims.py` to include:

```python
"/api/v1/sandbox/admin/macos-diagnostics"
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest \
  tldw_Server_API/tests/sandbox/test_admin_macos_diagnostics.py \
  tldw_Server_API/tests/sandbox/test_admin_rbac.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_sandbox_admin_permissions_claims.py -q
```

Expected: FAIL with 404 or missing response model wiring.

**Step 3: Implement the route**

Add a new admin route in `sandbox.py` using the same auth pattern as the existing admin endpoints:

```python
@router.get(
    "/admin/macos-diagnostics",
    response_model=SandboxAdminMacOSDiagnosticsResponse,
    summary="Admin: macOS sandbox diagnostics",
)
async def admin_macos_diagnostics(
    principal: AuthPrincipal = Depends(auth_deps.require_roles("admin")),
    current_user: User = Depends(get_request_user),
) -> SandboxAdminMacOSDiagnosticsResponse:
    return SandboxAdminMacOSDiagnosticsResponse.model_validate(_service.macos_diagnostics())
```

Do not bypass the shared service or return raw untyped dicts from the route.

**Step 4: Run the endpoint and RBAC tests again**

Run:

```bash
python -m pytest \
  tldw_Server_API/tests/sandbox/test_admin_macos_diagnostics.py \
  tldw_Server_API/tests/sandbox/test_admin_rbac.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_sandbox_admin_permissions_claims.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/sandbox.py tldw_Server_API/tests/sandbox/test_admin_macos_diagnostics.py tldw_Server_API/tests/sandbox/test_admin_rbac.py tldw_Server_API/tests/AuthNZ_Unit/test_sandbox_admin_permissions_claims.py
git commit -m "feat: add sandbox admin macOS diagnostics endpoint"
```

### Task 4: Keep `/sandbox/runtimes` Summarized and Aligned With Shared Preflight Inputs

**Files:**
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py`
- Check: `tldw_Server_API/tests/sandbox/test_lima_feature_discovery_capabilities.py`

**Step 1: Write the failing alignment and summary-contract tests**

Add a new test to `test_feature_discovery_flags.py`:

```python
def test_runtimes_discovery_keeps_macos_diagnostics_summarized(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("SANDBOX_STORE_BACKEND", "memory")
    monkeypatch.setenv("TLDW_SANDBOX_MACOS_HELPER_READY", "1")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_LINUX_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_LINUX_TEMPLATE_READY", "1")
    clear_config_cache()

    with TestClient(app) as client:
        data = client.get("/api/v1/sandbox/runtimes").json()
        vz_linux = next(item for item in data["runtimes"] if item["name"] == "vz_linux")

    assert "helper" not in vz_linux
    assert "templates" not in vz_linux
    assert "supported_trust_levels" in vz_linux
    assert isinstance(vz_linux.get("host"), dict)
```

Also add a test that the admin diagnostics runtime subsection stays aligned with the same preflight facts used by feature discovery:

```python
def test_macos_diagnostics_runtime_reasons_align_with_feature_discovery(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("SANDBOX_STORE_BACKEND", "memory")
    monkeypatch.setenv("TLDW_SANDBOX_MACOS_HELPER_READY", "0")
    clear_config_cache()

    svc = SandboxService()
    diagnostics = svc.macos_diagnostics()
    discovery = {item["name"]: item for item in svc.feature_discovery()}

    assert diagnostics["runtimes"]["vz_linux"]["reasons"] == discovery["vz_linux"]["reasons"]
    assert diagnostics["runtimes"]["vz_macos"]["reasons"] == discovery["vz_macos"]["reasons"]
    assert diagnostics["runtimes"]["seatbelt"]["supported_trust_levels"] == discovery["seatbelt"]["supported_trust_levels"]
```

**Step 2: Run the discovery tests to verify they fail**

Run:

```bash
python -m pytest tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py -q
```

Expected: FAIL if the new diagnostics runtime section is derived from a parallel logic path instead of the same preflight inputs.

**Step 3: Refactor only as needed to keep both views aligned**

Keep Docker, Firecracker, and Lima behavior intact. The important requirement is that macOS runtime diagnostics and `/sandbox/runtimes` must reflect the same underlying preflight reasons and supported trust levels. If `feature_discovery()` already uses the shared preflight path, do not add an unnecessary second abstraction just to satisfy the task wording.

Preserve the public summary boundary:

- keep `available`, `reasons`, `supported_trust_levels`, `host`, and current capability booleans
- do not expose `helper`, `templates`, or admin remediation detail in `/sandbox/runtimes`

**Step 4: Run the discovery tests again**

Run:

```bash
python -m pytest tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/service.py tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py
git commit -m "feat: reuse macOS diagnostics in runtime discovery"
```

### Task 5: Add Host-Gated Proof, Update Operator Docs, and Run Final Verification

**Files:**
- Modify: `tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py`
- Modify: `Docs/Sandbox/macos-runtime-operator-notes.md`
- Modify: `tldw_Server_API/app/core/Sandbox/README.md`
- Check: `Docs/Plans/2026-03-10-macos-sandbox-admin-diagnostics-design.md`

**Step 1: Add the host-gated diagnostics smoke test**

Extend `test_vz_runtime_macos_host_gated.py` with a diagnostics smoke test:

```python
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS host only")
def test_collect_macos_diagnostics_smoke_on_real_host() -> None:
    data = collect_macos_diagnostics()
    assert "host" in data
    assert "helper" in data
    assert "templates" in data
    assert "runtimes" in data
    assert isinstance(data["host"].get("macos_version"), (str, type(None)))
```

**Step 2: Run the smoke test**

Run:

```bash
python -m pytest tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py -q
```

Expected: PASS once the diagnostics contract is in place. Treat this as host-gated verification rather than a forced red phase.

**Step 3: Finish the last implementation bits and update the docs**

If the smoke test exposes any missing version/platform fields, fix them in `macos_diagnostics.py`.

Then update the operator docs so they mention:

- the new admin endpoint: `/api/v1/sandbox/admin/macos-diagnostics`
- the difference between admin diagnostics and `/api/v1/sandbox/runtimes`
- the current env-driven readiness signals and fake-exec limits

Keep the docs aligned with the current scaffolded state. Do not imply real guest execution exists yet.

**Step 4: Run the full targeted verification and Bandit**

Run:

```bash
python -m pytest \
  tldw_Server_API/tests/sandbox/test_macos_diagnostics.py \
  tldw_Server_API/tests/sandbox/test_admin_macos_diagnostics.py \
  tldw_Server_API/tests/sandbox/test_admin_rbac.py \
  tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_sandbox_admin_permissions_claims.py \
  tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py -q
```

Expected: PASS.

Run:

```bash
python -m bandit -r \
  tldw_Server_API/app/core/Sandbox/macos_diagnostics.py \
  tldw_Server_API/app/core/Sandbox/service.py \
  tldw_Server_API/app/api/v1/endpoints/sandbox.py \
  tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py \
  -f json -o /tmp/bandit_macos_admin_diagnostics.json
```

Expected: `0` new findings in touched code.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py Docs/Sandbox/macos-runtime-operator-notes.md tldw_Server_API/app/core/Sandbox/README.md
git commit -m "docs: add macOS sandbox diagnostics operator guidance"
```

## Final review checklist

- The admin endpoint is admin-only and typed with dedicated Pydantic models.
- `/api/v1/sandbox/runtimes` stays summarized.
- Host/setup failures are distinguishable from policy restrictions.
- The probe layer is read-only in this slice.
- Targeted pytest coverage passes.
- Bandit reports no new findings in touched code.
