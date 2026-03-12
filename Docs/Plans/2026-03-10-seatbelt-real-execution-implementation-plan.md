# Seatbelt Real Execution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace fake macOS `seatbelt` execution with a real trusted-workflow subprocess path that stages inline files, uses a generated seatbelt profile, captures logs/artifacts, and cleans up correctly without overstating isolation guarantees.

**Architecture:** Implement real host execution inside `SeatbeltRunner`, backed by a small `seatbelt_policy.py` helper for profile rendering and environment staging. Keep the runtime contract honest by treating `sandbox-exec` as compatibility-gated, keeping best-effort network deny out of strict-enforcement claims, and storing runner control files outside the writable workspace.

**Tech Stack:** Python, FastAPI sandbox runtime layer, `subprocess`, macOS `sandbox-exec`, pytest, existing sandbox orchestrator/service/artifact flows

---

### Task 1: Add Seatbelt Policy And Environment Helpers

**Files:**
- Create: `tldw_Server_API/app/core/Sandbox/runners/seatbelt_policy.py`
- Test: `tldw_Server_API/tests/sandbox/test_seatbelt_policy.py`
- Check: `tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py`

**Step 1: Write the failing tests**

Create `tldw_Server_API/tests/sandbox/test_seatbelt_policy.py` with focused unit tests for:

- control dir paths are not emitted as writable workspace paths
- rendered profile includes workspace and temp roots only
- best-effort network deny markers appear only for `deny_all`
- environment builder starts from a curated base and does not inherit arbitrary host env

Example test skeleton:

```python
from tldw_Server_API.app.core.Sandbox.runners.seatbelt_policy import (
    build_seatbelt_env,
    render_seatbelt_profile,
)


def test_render_seatbelt_profile_limits_writes_to_workspace_and_temp() -> None:
    profile = render_seatbelt_profile(
        command_path="/bin/echo",
        workspace_path="/tmp/workspace",
        home_path="/tmp/home",
        temp_path="/tmp/temp",
        network_policy="deny_all",
    )

    assert "/tmp/workspace" in profile
    assert "/tmp/home" in profile
    assert "/tmp/temp" in profile
    assert "/bin/echo" in profile


def test_build_seatbelt_env_does_not_inherit_unexpected_host_env(monkeypatch) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "should-not-leak")

    env = build_seatbelt_env(
        workspace_path="/tmp/workspace",
        home_path="/tmp/home",
        temp_path="/tmp/temp",
        spec_env={"LANG": "C"},
    )

    assert env["HOME"] == "/tmp/home"
    assert env["TMPDIR"] == "/tmp/temp"
    assert env["PWD"] == "/tmp/workspace"
    assert env["LANG"] == "C"
    assert "AWS_SECRET_ACCESS_KEY" not in env
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_policy.py -q
```

Expected: FAIL because `seatbelt_policy.py` does not exist yet.

**Step 3: Write the minimal helper implementation**

Create `tldw_Server_API/app/core/Sandbox/runners/seatbelt_policy.py` with:

- `render_seatbelt_profile(...) -> str`
- `build_seatbelt_env(...) -> dict[str, str]`
- `resolve_command_argv(command: list[str], env_path: str) -> list[str]`

Requirements:

- no implicit shell wrapping
- command resolution uses argv and a controlled `PATH`
- workspace/temp dirs are explicit inputs
- `deny_all` renders best-effort network deny directives
- allowlist raises or is rejected by caller

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_policy.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/runners/seatbelt_policy.py tldw_Server_API/tests/sandbox/test_seatbelt_policy.py
git commit -m "feat: add seatbelt policy rendering helpers"
```

### Task 2: Tighten Seatbelt Preflight And Discovery Semantics

**Files:**
- Modify: `tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py`
- Modify: `tldw_Server_API/app/core/Sandbox/service.py`
- Modify: `tldw_Server_API/app/core/Sandbox/README.md`
- Modify: `Docs/Sandbox/macos-runtime-operator-notes.md`
- Test: `tldw_Server_API/tests/sandbox/test_seatbelt_runner.py`
- Test: `tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py`

**Step 1: Write the failing preflight/discovery tests**

Extend `test_seatbelt_runner.py` and `test_feature_discovery_flags.py` to cover:

- `sandbox_exec_missing` when the launcher binary is unavailable
- `strict_allowlist_not_supported` still returned for allowlist
- seatbelt can be `available=True` while `strict_deny_all_supported` remains `False`
- runtime notes say network deny is best-effort, not strict

Example test shape:

```python
def test_seatbelt_preflight_reports_missing_launcher(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_AVAILABLE", "1")
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.runners.seatbelt_runner._sandbox_exec_exists", lambda: False)

    result = SeatbeltRunner().preflight(network_policy="deny_all")

    assert result.available is False
    assert "sandbox_exec_missing" in result.reasons
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_runner.py tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py -q
```

Expected: FAIL on the new expectations.

**Step 3: Implement the preflight/discovery changes**

In `seatbelt_runner.py`:

- add launcher existence check (for `/usr/bin/sandbox-exec`)
- return concrete reasons instead of `seatbelt_real_execution_not_implemented`
- keep `enforcement_ready["deny_all"] = False` in the best-effort model

In `service.py` / docs:

- keep public discovery honest via notes and readiness flags
- do not advertise strict deny-all support for seatbelt

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_runner.py tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py tldw_Server_API/app/core/Sandbox/service.py tldw_Server_API/app/core/Sandbox/README.md Docs/Sandbox/macos-runtime-operator-notes.md tldw_Server_API/tests/sandbox/test_seatbelt_runner.py tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py
git commit -m "feat: tighten seatbelt runtime readiness contract"
```

### Task 3: Implement Real Seatbelt Subprocess Execution

**Files:**
- Modify: `tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py`
- Test: `tldw_Server_API/tests/sandbox/test_seatbelt_runner.py`
- Check: `tldw_Server_API/app/core/Sandbox/runners/lima_runner.py`

**Step 1: Write the failing execution tests**

Add unit/integration-style tests for:

- trusted run launches a subprocess with `sandbox-exec`
- inline files are written into the workspace before launch
- stdout/stderr are captured into run status/log flow
- `RunStatus.artifacts` is populated from matched workspace files

Example test shape:

```python
def test_seatbelt_start_run_executes_real_subprocess(monkeypatch, tmp_path) -> None:
    runner = SeatbeltRunner()
    spec = RunSpec(
        session_id=None,
        runtime=RuntimeType.seatbelt,
        base_image="host-local",
        command=["/bin/sh", "-c", "printf hi > out.txt"],
        capture_patterns=["out.txt"],
        trust_level=TrustLevel.trusted,
    )

    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_AVAILABLE", "1")
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.runners.seatbelt_runner._sandbox_exec_exists", lambda: True)

    status = runner.start_run("run-1", spec, str(tmp_path))

    assert status.phase == RunPhase.completed
    assert status.artifacts is not None
    assert status.artifacts["out.txt"] == b"hi"
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_runner.py -q
```

Expected: FAIL because real execution is not implemented yet.

**Step 3: Implement the minimal real execution path**

In `seatbelt_runner.py`:

- stage inline files into the session workspace
- create runner-managed control dir via `tempfile.mkdtemp(...)`
- create isolated `HOME` and temp dirs
- render the seatbelt profile file into the control dir
- resolve the command argv using the curated `PATH`
- launch with `subprocess.Popen(...)` and no shell
- capture output, wait with timeout, and collect artifacts by matching `capture_patterns` against the workspace

Keep fake execution behind `TLDW_SANDBOX_SEATBELT_FAKE_EXEC=1` for tests/CI scaffolding.

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_runner.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py tldw_Server_API/tests/sandbox/test_seatbelt_runner.py
git commit -m "feat: add real seatbelt subprocess execution"
```

### Task 4: Add Cancellation, Timeout, And Cleanup Guarantees

**Files:**
- Modify: `tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py`
- Test: `tldw_Server_API/tests/sandbox/test_runner_cancel_and_timeouts.py`
- Test: `tldw_Server_API/tests/sandbox/test_seatbelt_runner.py`

**Step 1: Write the failing cleanup tests**

Add tests for:

- `cancel_run()` kills the active process group for a seatbelt run
- timeout returns `RunPhase.timed_out`
- control dir and temp dirs are removed in success, failure, timeout, and cancel paths

Example:

```python
def test_seatbelt_cancel_run_kills_active_process_group(monkeypatch, tmp_path) -> None:
    # Launch a controllable fake Popen or short-lived subprocess fixture and assert
    # cancel_run() looks up the tracked PID/process group and terminates it.
    ...
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_runner_cancel_and_timeouts.py tldw_Server_API/tests/sandbox/test_seatbelt_runner.py -q
```

Expected: FAIL on the new seatbelt cleanup assertions.

**Step 3: Implement PID tracking and teardown**

Add runner-level tracking for:

- active subprocess PID/process group by `run_id`
- control dir path by `run_id`
- isolated temp dir paths by `run_id`

Implement:

- `cancel_run()` using process-group termination on macOS
- `finally` cleanup for runner-owned dirs
- timeout handling that maps to `RunPhase.timed_out`

**Step 4: Run the tests to verify they pass**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_runner_cancel_and_timeouts.py tldw_Server_API/tests/sandbox/test_seatbelt_runner.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py tldw_Server_API/tests/sandbox/test_runner_cancel_and_timeouts.py tldw_Server_API/tests/sandbox/test_seatbelt_runner.py
git commit -m "feat: add seatbelt cancellation and cleanup"
```

### Task 5: Add Host-Gated Proof And Final Verification

**Files:**
- Modify: `tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py`
- Modify: `Docs/Sandbox/macos-runtime-operator-notes.md`
- Modify: `tldw_Server_API/app/core/Sandbox/README.md`

**Step 1: Write the host-gated smoke test**

Extend the macOS-host-gated sandbox smoke file with a seatbelt test:

```python
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS host only")
def test_seatbelt_real_execution_smoke_on_real_host() -> None:
    runner = SeatbeltRunner()
    spec = RunSpec(
        session_id=None,
        runtime=RuntimeType.seatbelt,
        base_image="host-local",
        command=["/usr/bin/true"],
        trust_level=TrustLevel.trusted,
    )

    status = runner.start_run("smoke-seatbelt", spec, tempfile.mkdtemp(prefix="seatbelt-smoke-"))

    assert status.phase in {RunPhase.completed, RunPhase.failed, RunPhase.timed_out}
```

Gate it carefully if the host lacks `sandbox-exec` support or the real execution flag is disabled.

**Step 2: Update the docs**

Document:

- real `seatbelt` execution is now available for trusted workflows
- `sandbox-exec` is compatibility-gated and deprecated
- network deny is best-effort only
- control dirs live outside the writable workspace
- `untrusted` still requires VM runtimes

**Step 3: Run the full targeted verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/sandbox/test_seatbelt_policy.py tldw_Server_API/tests/sandbox/test_seatbelt_runner.py tldw_Server_API/tests/sandbox/test_runner_cancel_and_timeouts.py tldw_Server_API/tests/sandbox/test_macos_diagnostics.py tldw_Server_API/tests/sandbox/test_admin_macos_diagnostics.py tldw_Server_API/tests/sandbox/test_admin_rbac.py tldw_Server_API/tests/sandbox/test_feature_discovery_flags.py tldw_Server_API/tests/AuthNZ_Unit/test_sandbox_admin_permissions_claims.py tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py -q
```

Expected: PASS

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Sandbox/runners/seatbelt_policy.py tldw_Server_API/app/core/Sandbox/runners/seatbelt_runner.py tldw_Server_API/app/core/Sandbox/service.py tldw_Server_API/app/core/Sandbox/README.md tldw_Server_API/app/core/Sandbox/macos_diagnostics.py tldw_Server_API/app/api/v1/endpoints/sandbox.py tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py -f json -o /tmp/bandit_seatbelt_real_execution.json
```

Expected: `0` new findings in touched implementation files.

**Step 4: Commit**

```bash
git add tldw_Server_API/tests/sandbox/test_vz_runtime_macos_host_gated.py Docs/Sandbox/macos-runtime-operator-notes.md tldw_Server_API/app/core/Sandbox/README.md
git commit -m "docs: finalize real seatbelt execution rollout notes"
```

## Final Review Checklist

- `seatbelt` remains forbidden for `untrusted`
- `standard` remains opt-in only
- `sandbox-exec` is checked explicitly in preflight
- runner-owned control files live outside the writable workspace
- env curation prevents accidental host secret inheritance
- best-effort network deny is not presented as strict deny-all support
- cancellation and timeout clean up process groups and temp dirs
- targeted pytest coverage passes
- Bandit reports no new findings in touched implementation files
