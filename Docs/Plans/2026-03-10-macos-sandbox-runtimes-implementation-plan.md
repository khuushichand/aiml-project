# macOS Sandbox Runtimes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-class `vz_linux`, `vz_macos`, and `seatbelt` runtimes to the sandbox subsystem with fail-closed Apple-silicon macOS admission, a native-helper abstraction, APFS clone-backed VM template handling, and clear trust-level enforcement.

**Architecture:** Extend the existing capability-driven sandbox runtime model instead of overloading `lima`. Implement the work in layers: runtime enums and policy contracts first, then a macOS helper/image-store abstraction, then fake-backed `vz_linux` and `vz_macos` runners, then a restricted `seatbelt` runtime, and finally REST/MCP/ACP integration plus macOS-gated verification. Keep `untrusted` fail-closed until a VM runtime is fully available and verified.

**Tech Stack:** Python 3, FastAPI, pytest, existing sandbox policy/service/runtime modules, Apple `Virtualization.framework` via a small native helper, APFS clone-backed disk image handling, macOS-only opt-in integration tests.

---

### Task 1: Add Runtime Enums And Surface Contracts

**Files:**
- Modify: `tldw_Server_API/app/core/Sandbox/models.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/implementations/sandbox_module.py`
- Test: `tldw_Server_API/tests/sandbox/test_runtime_capabilities_policy.py`
- Test: `tldw_Server_API/tests/sandbox/test_runtimes_queue_fields.py`
- Create: `tldw_Server_API/tests/sandbox/test_macos_runtime_surface_contract.py`

**Step 1: Write the failing test**

```python
def test_runtime_schema_accepts_new_macos_runtimes() -> None:
    body = {
        "spec_version": "1.0",
        "runtime": "vz_linux",
        "base_image": "ubuntu-24.04",
        "command": ["echo", "ok"],
    }
    model = SandboxRunCreateRequest.model_validate(body)
    assert model.runtime == "vz_linux"


def test_mcp_tool_schema_lists_new_runtimes() -> None:
    module = SandboxModule(name="sandbox", config={})
    asyncio.run(module.on_initialize())
    tool = next(t for t in asyncio.run(module.get_tools()) if t["name"] == "sandbox.run")
    assert tool["inputSchema"]["properties"]["runtime"]["enum"] == [
        "docker",
        "firecracker",
        "lima",
        "vz_linux",
        "vz_macos",
        "seatbelt",
    ]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_runtime_surface_contract.py -v`

Expected: FAIL because the new runtime values are not yet defined in the models and schema layers.

**Step 3: Write minimal implementation**

```python
class RuntimeType(str, Enum):
    docker = "docker"
    firecracker = "firecracker"
    lima = "lima"
    vz_linux = "vz_linux"
    vz_macos = "vz_macos"
    seatbelt = "seatbelt"
```

Update the REST schema enums and MCP tool schema enum lists to match exactly.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_runtime_surface_contract.py tldw_Server_API/tests/sandbox/test_runtime_capabilities_policy.py -v`

Expected: PASS for the new runtime enum acceptance without regressing existing runtime parsing.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/models.py \
  tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py \
  tldw_Server_API/app/core/MCP_unified/modules/implementations/sandbox_module.py \
  tldw_Server_API/tests/sandbox/test_macos_runtime_surface_contract.py \
  tldw_Server_API/tests/sandbox/test_runtime_capabilities_policy.py
git commit -m "feat: add macOS sandbox runtime enums"
```

### Task 2: Enforce Trust-Level Admission And No-Fallback Rules

**Files:**
- Modify: `tldw_Server_API/app/core/Sandbox/policy.py`
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/app/core/Sandbox/runtime_capabilities.py`
- Test: `tldw_Server_API/tests/sandbox/test_runtime_capabilities_policy.py`
- Create: `tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py`

**Step 1: Write the failing test**

```python
def test_seatbelt_rejected_for_untrusted_runs(monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "0")
    svc = SandboxService()
    spec = RunSpec(
        session_id=None,
        runtime=RuntimeType.seatbelt,
        base_image=None,
        command=["echo", "ok"],
        trust_level=TrustLevel.untrusted,
    )

    with pytest.raises(SandboxPolicy.PolicyUnsupported) as exc:
        svc.start_run_scaffold(user_id="1", spec=spec, spec_version="1.0", idem_key=None, raw_body={})

    assert exc.value.runtime == RuntimeType.seatbelt
    assert "trust_level_requires_vm_runtime" in exc.value.reasons
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py::test_seatbelt_rejected_for_untrusted_runs -v`

Expected: FAIL because the current policy layer does not encode runtime-specific trust gating.

**Step 3: Write minimal implementation**

```python
if spec.runtime == RuntimeType.seatbelt and trust == TrustLevel.untrusted:
    raise SandboxPolicy.PolicyUnsupported(
        RuntimeType.seatbelt,
        requirement="untrusted_requires_vm_runtime",
        reasons=["trust_level_requires_vm_runtime"],
    )
```

Extend preflight payloads so `RuntimePreflightResult` includes trust support metadata and use it during authoritative admission.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py tldw_Server_API/tests/sandbox/test_lima_no_fallback.py -v`

Expected: PASS with no fallback suggestions for unsupported runtime selections.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/policy.py \
  tldw_Server_API/app/core/Sandbox/service.py \
  tldw_Server_API/app/core/Sandbox/runtime_capabilities.py \
  tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py
git commit -m "feat: enforce macOS runtime trust admission"
```

### Task 3: Add The Native Helper Contract And Fake Helper Client

**Files:**
- Create: `tldw_Server_API/app/core/Sandbox/macos_virtualization/__init__.py`
- Create: `tldw_Server_API/app/core/Sandbox/macos_virtualization/helper_client.py`
- Create: `tldw_Server_API/app/core/Sandbox/macos_virtualization/models.py`
- Create: `tldw_Server_API/tests/sandbox/test_macos_helper_client.py`
- Create: `apps/macos_virtualization_helper/README.md`

**Step 1: Write the failing test**

```python
def test_helper_client_uses_fake_transport_in_test_mode(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    client = MacOSVirtualizationHelperClient()
    reply = client.create_vm({"runtime": "vz_linux", "vm_name": "run-123"})
    assert reply.vm_id == "run-123"
    assert reply.state == "created"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_helper_client.py -v`

Expected: FAIL because the helper client and response models do not exist.

**Step 3: Write minimal implementation**

```python
@dataclass
class HelperVMReply:
    vm_id: str
    state: str
    details: dict[str, Any] = field(default_factory=dict)


class MacOSVirtualizationHelperClient:
    def create_vm(self, request: dict[str, Any]) -> HelperVMReply:
        if is_truthy(os.getenv("TEST_MODE")):
            return HelperVMReply(vm_id=str(request["vm_name"]), state="created")
        raise RuntimeError("macos_virtualization_helper_unavailable")
```

Document the intended real helper protocol in `apps/macos_virtualization_helper/README.md` without implementing the full native binary yet.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_helper_client.py -v`

Expected: PASS with a fake transport contract that later real helper code can satisfy.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/macos_virtualization \
  tldw_Server_API/tests/sandbox/test_macos_helper_client.py \
  apps/macos_virtualization_helper/README.md
git commit -m "feat: add macOS virtualization helper contract"
```

### Task 4: Build The VM Template Store And APFS Clone Manifest Layer

**Files:**
- Create: `tldw_Server_API/app/core/Sandbox/image_store.py`
- Create: `tldw_Server_API/tests/sandbox/test_macos_image_store.py`
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/app/core/Sandbox/runtime_capabilities.py`

**Step 1: Write the failing test**

```python
def test_image_store_returns_run_clone_manifest_for_template(tmp_path: Path) -> None:
    store = SandboxImageStore(root_path=tmp_path)
    template_id = store.register_template(
        runtime="vz_linux",
        template_name="ubuntu-24.04",
        disk_paths=["/templates/ubuntu-24.04.img"],
    )

    manifest = store.prepare_run_clone(template_id=template_id, run_id="run-123")
    assert manifest.template_id == template_id
    assert manifest.run_id == "run-123"
    assert manifest.clone_items[0].source_path.endswith(".img")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_image_store.py -v`

Expected: FAIL because no image store or manifest abstraction exists.

**Step 3: Write minimal implementation**

```python
@dataclass
class CloneItem:
    source_path: str
    target_path: str
    mode: str  # clone | generate


@dataclass
class RunCloneManifest:
    template_id: str
    run_id: str
    clone_items: list[CloneItem]
```

Implement a fake clone path first in tests; keep the interface explicit so APFS-specific cloning can be added later without changing runner contracts.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_image_store.py -v`

Expected: PASS with deterministic manifest generation and no platform-specific side effects in unit tests.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/image_store.py \
  tldw_Server_API/app/core/Sandbox/service.py \
  tldw_Server_API/app/core/Sandbox/runtime_capabilities.py \
  tldw_Server_API/tests/sandbox/test_macos_image_store.py
git commit -m "feat: add sandbox VM image store contract"
```

### Task 5: Implement `vz_linux` Runner Scaffolding

**Files:**
- Create: `tldw_Server_API/app/core/Sandbox/runners/vz_common.py`
- Create: `tldw_Server_API/app/core/Sandbox/runners/vz_linux_runner.py`
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/app/core/Sandbox/runtime_capabilities.py`
- Create: `tldw_Server_API/tests/sandbox/test_vz_linux_runner.py`
- Modify: `tldw_Server_API/tests/sandbox/test_runtime_unavailable.py`

**Step 1: Write the failing test**

```python
def test_vz_linux_fake_run_completes(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_VZ_LINUX_FAKE_EXEC", "1")
    runner = VZLinuxRunner()
    status = runner.start_run(
        run_id="run-123",
        spec=RunSpec(
            session_id=None,
            runtime=RuntimeType.vz_linux,
            base_image="ubuntu-24.04",
            command=["echo", "ok"],
            network_policy="deny_all",
        ),
    )
    assert status.phase == RunPhase.completed
    assert status.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_vz_linux_runner.py -v`

Expected: FAIL because `VZLinuxRunner` is not wired into the service or runtime capability paths.

**Step 3: Write minimal implementation**

```python
class VZLinuxRunner:
    def preflight(self, network_policy: str | None = None) -> RuntimePreflightResult:
        return RuntimePreflightResult(
            runtime=RuntimeType.vz_linux,
            available=_host_is_supported() and _helper_ready() and _template_ready("vz_linux"),
            reasons=_collect_reasons("vz_linux"),
        )
```

Add fake execution matching the existing runner scaffold style, then wire service dispatch so `RuntimeType.vz_linux` resolves to this runner and performs an execution-time preflight before start.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_vz_linux_runner.py tldw_Server_API/tests/sandbox/test_runtime_unavailable.py -v`

Expected: PASS with explicit failure reasons when helper/template readiness is missing.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/runners/vz_common.py \
  tldw_Server_API/app/core/Sandbox/runners/vz_linux_runner.py \
  tldw_Server_API/app/core/Sandbox/service.py \
  tldw_Server_API/app/core/Sandbox/runtime_capabilities.py \
  tldw_Server_API/tests/sandbox/test_vz_linux_runner.py \
  tldw_Server_API/tests/sandbox/test_runtime_unavailable.py
git commit -m "feat: add vz_linux sandbox runner scaffold"
```

### Task 6: Implement `vz_macos` Runner Scaffolding

**Files:**
- Create: `tldw_Server_API/app/core/Sandbox/runners/vz_macos_runner.py`
- Modify: `tldw_Server_API/app/core/Sandbox/runners/vz_common.py`
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/app/core/Sandbox/runtime_capabilities.py`
- Create: `tldw_Server_API/tests/sandbox/test_vz_macos_runner.py`

**Step 1: Write the failing test**

```python
def test_vz_macos_preflight_requires_template_and_helper(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_MACOS_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_MACOS_HELPER_READY", "0")
    result = VZMacOSRunner().preflight(network_policy="deny_all")
    assert result.available is False
    assert "macos_helper_missing" in result.reasons
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_vz_macos_runner.py -v`

Expected: FAIL because `vz_macos` support does not yet exist and macOS-specific readiness reasons are not modeled.

**Step 3: Write minimal implementation**

```python
class VZMacOSRunner(VZBaseRunner):
    runtime_type = RuntimeType.vz_macos

    def preflight(self, network_policy: str | None = None) -> RuntimePreflightResult:
        reasons = []
        if not _helper_ready():
            reasons.append("macos_helper_missing")
        if not _template_ready("vz_macos"):
            reasons.append("macos_template_missing")
        return RuntimePreflightResult(
            runtime=self.runtime_type,
            available=not reasons,
            reasons=reasons,
        )
```

Keep actual command execution fake-backed first. The important work in this task is the stricter readiness contract and separate runtime identity.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_vz_macos_runner.py tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py -v`

Expected: PASS with explicit failure reasons and no silent reuse of the Linux VM path.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/runners/vz_macos_runner.py \
  tldw_Server_API/app/core/Sandbox/runners/vz_common.py \
  tldw_Server_API/app/core/Sandbox/service.py \
  tldw_Server_API/app/core/Sandbox/runtime_capabilities.py \
  tldw_Server_API/tests/sandbox/test_vz_macos_runner.py
git commit -m "feat: add vz_macos sandbox runner scaffold"
```

### Task 7: Implement `seatbelt` Runner With Conservative Trust Gating

**Files:**
- Create: `tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py`
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/app/core/Sandbox/runtime_capabilities.py`
- Create: `tldw_Server_API/tests/sandbox/test_seatbelt_runner.py`
- Modify: `tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py`

**Step 1: Write the failing test**

```python
def test_seatbelt_standard_mode_requires_explicit_enable(monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "0")
    monkeypatch.delenv("TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED", raising=False)
    svc = SandboxService()
    spec = RunSpec(
        session_id=None,
        runtime=RuntimeType.seatbelt,
        base_image=None,
        command=["echo", "ok"],
        trust_level=TrustLevel.standard,
    )

    with pytest.raises(SandboxPolicy.PolicyUnsupported):
        svc.start_run_scaffold(user_id="1", spec=spec, spec_version="1.0", idem_key=None, raw_body={})
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_runner.py tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py -v`

Expected: FAIL because the runtime and its trust gates do not yet exist.

**Step 3: Write minimal implementation**

```python
if trust == TrustLevel.standard and not _truthy(os.getenv("TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED")):
    raise SandboxPolicy.PolicyUnsupported(
        RuntimeType.seatbelt,
        requirement="standard_not_enabled",
        reasons=["seatbelt_standard_disabled"],
    )
```

Implement fake execution only at first. Keep the launch contract explicit: generated profile path, workspace root, env allowlist, timeout, and process tree capture.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_runner.py tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py -v`

Expected: PASS with `trusted` working, `standard` opt-in only, and `untrusted` rejected.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py \
  tldw_Server_API/app/core/Sandbox/service.py \
  tldw_Server_API/app/core/Sandbox/runtime_capabilities.py \
  tldw_Server_API/tests/sandbox/test_seatbelt_runner.py \
  tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py
git commit -m "feat: add seatbelt sandbox runner scaffold"
```

### Task 8: Integrate REST, ACP, Runtimes Discovery, And Admin Surfaces

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/sandbox.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py`
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/implementations/sandbox_module.py`
- Test: `tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py`
- Test: `tldw_Server_API/tests/sandbox/test_runtime_unavailable.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py`

**Step 1: Write the failing test**

```python
def test_runtimes_discovery_includes_macos_runtime_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    response = client.get("/api/v1/sandbox/runtimes")
    assert response.status_code == 200
    runtimes = {item["name"]: item for item in response.json()["runtimes"]}
    assert "vz_linux" in runtimes
    assert "vz_macos" in runtimes
    assert "seatbelt" in runtimes
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py -v`

Expected: FAIL because the new runtimes are not yet exposed uniformly across surfaces.

**Step 3: Write minimal implementation**

```python
runtime_items.append({
    "runtime": "vz_linux",
    "available": preflight.available,
    "reasons": preflight.reasons,
    "trust_levels": ["trusted", "standard", "untrusted"],
})
```

Mirror the same runtime names and fail-closed errors in REST, MCP, ACP, and discovery endpoints.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py tldw_Server_API/tests/sandbox/test_runtime_unavailable.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py -v`

Expected: PASS with consistent runtime exposure and no silent fallback behavior.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/sandbox.py \
  tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py \
  tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py \
  tldw_Server_API/app/core/MCP_unified/modules/implementations/sandbox_module.py \
  tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py \
  tldw_Server_API/tests/sandbox/test_runtime_unavailable.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py
git commit -m "feat: expose macOS sandbox runtimes across surfaces"
```

### Task 9: Add macOS-Gated Verification, Security Checks, And Documentation

**Files:**
- Modify: `tldw_Server_API/app/core/Sandbox/README.md`
- Create: `tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py`
- Create: `Docs/Sandbox/macos-runtime-operator-notes.md`

**Step 1: Write the failing test**

```python
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS host only")
def test_vz_linux_preflight_smoke_on_real_host() -> None:
    result = VZLinuxRunner().preflight(network_policy="deny_all")
    assert "host" in result.host
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py -v`

Expected: FAIL on configured Apple silicon hosts until the smoke path and helper readiness wiring are present, or SKIP on non-macOS hosts.

**Step 3: Write minimal implementation**

```python
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS host only")
def test_vz_linux_preflight_smoke_on_real_host() -> None:
    result = VZLinuxRunner().preflight(network_policy="deny_all")
    assert isinstance(result.available, bool)
```

Document:

- required macOS version and Apple silicon assumption
- helper installation path
- template preparation flow
- which runtimes are safe for which trust levels
- current limitations for `allowlist` and warm sessions

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py -v`

Expected: PASS or SKIP deterministically, with operator notes aligned to the actual shipped behavior.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/README.md \
  tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py \
  Docs/Sandbox/macos-runtime-operator-notes.md
git commit -m "docs: add macOS sandbox runtime operator guidance"
```

## Verification Checklist

- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_runtime_surface_contract.py -v`
- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_runtime_admission.py -v`
- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_helper_client.py -v`
- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_macos_image_store.py -v`
- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_vz_linux_runner.py -v`
- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_vz_macos_runner.py -v`
- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_runner.py -v`
- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_runtime_unavailable.py tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py -v`
- Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sandbox_runner_client.py -v`
- Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Sandbox tldw_Server_API/app/api/v1/endpoints/sandbox.py -f json -o /tmp/bandit_macos_sandbox_runtimes.json`

## Notes For The Implementer

- Do not try to ship real `vz_macos` command execution before the helper, template store, and host prerequisites are explicit.
- Keep the first real VM implementation on `vz_linux` and reuse the same abstractions for `vz_macos`.
- Do not allow silent fallback from `vz_linux`, `vz_macos`, or `seatbelt` to `docker`, `firecracker`, or `lima`.
- Keep `seatbelt` conservative. It should not become a convenient loophole around the `untrusted` VM requirement.
