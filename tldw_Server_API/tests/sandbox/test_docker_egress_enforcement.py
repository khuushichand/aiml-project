from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List

import pytest

from tldw_Server_API.app.core.Sandbox.runners.docker_runner import DockerRunner
from tldw_Server_API.app.core.Sandbox.models import RunSpec, RuntimeType


@pytest.mark.unit
def test_docker_runner_uses_network_none_when_allowlist_enforced_non_granular(monkeypatch):
     # Make docker appear available and ensure execution path is taken
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_AVAILABLE", "1")
    # Build a spec with allowlist policy
    spec = RunSpec(
        session_id=None,
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        command=["python", "-c", "print('ok')"],
        timeout_sec=5,
        network_policy="allowlist",
    )
    # Enforce allowlist but disable granular; expect --network none
    monkeypatch.setenv("SANDBOX_EGRESS_ENFORCEMENT", "true")
    monkeypatch.setenv("SANDBOX_EGRESS_GRANULAR_ENFORCEMENT", "false")

    recorded_cmds: List[List[str]] = []

    class _Called(Exception):
        pass

    def fake_check_output(cmd, text=False, timeout=None):  # type: ignore[no-redef]
        nonlocal recorded_cmds
        recorded_cmds.append(list(cmd))
        # Simulate failure after capture so we don't need the rest of the flow
        raise _Called()

    monkeypatch.setattr("subprocess.check_output", fake_check_output)
    runner = DockerRunner()
    with pytest.raises(_Called):
        runner.start_run(run_id="rid1234567890", spec=spec)
    # Assert the docker create command contains '--network', 'none'
    create = next((c for c in recorded_cmds if c[:2] == ["docker", "create"]), [])
    assert create, f"docker create not issued; got: {recorded_cmds}"
    # Find '--network' flag
    if "--network" in create:
        idx = create.index("--network")
        assert create[idx + 1] == "none"
    else:
        pytest.fail(f"--network not present in docker create: {create}")


@pytest.mark.unit
def test_docker_runner_creates_dedicated_network_when_granular_enabled(monkeypatch):
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_AVAILABLE", "1")
    spec = RunSpec(
        session_id=None,
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        command=["python", "-c", "print('ok')"],
        timeout_sec=5,
        network_policy="allowlist",
    )
    monkeypatch.setenv("SANDBOX_EGRESS_ENFORCEMENT", "true")
    monkeypatch.setenv("SANDBOX_EGRESS_GRANULAR_ENFORCEMENT", "true")

    recorded_cmds: List[List[str]] = []

    class _Called(Exception):
        pass

    def fake_run(args, check=False, timeout=None):  # docker network create/remove
        recorded_cmds.append(list(args))
        return 0

    def fake_check_output(cmd, text=False, timeout=None):

        recorded_cmds.append(list(cmd))
        raise _Called()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("subprocess.check_output", fake_check_output)
    runner = DockerRunner()
    with pytest.raises(_Called):
        runner.start_run(run_id="abcd1234efgh", spec=spec)
    create = next((c for c in recorded_cmds if c[:2] == ["docker", "create"]), [])
    assert create, f"docker create not issued; got: {recorded_cmds}"
    assert "--network" in create
    idx = create.index("--network")
    net_name = create[idx + 1]
    assert net_name.startswith("tldw_sbx_")


@pytest.mark.integration
def test_apply_iptables_rules_on_supported_hosts(monkeypatch):
     # Only run when explicitly allowed
    if os.getenv("SANDBOX_TEST_ALLOW_IPTABLES_MUTATION") not in {"1", "true", "on", "yes"}:
        pytest.skip("iptables mutation not enabled")
    if shutil.which("iptables") is None:
        pytest.skip("iptables not available on host")
    # Ensure DOCKER-USER chain exists; if not, skip to avoid altering host firewall unexpectedly
    import subprocess
    try:
        subprocess.check_output(["iptables", "-S", "DOCKER-USER"])  # may fail if chain missing
    except Exception:
        pytest.skip("DOCKER-USER chain not present; skipping")

    from tldw_Server_API.app.core.Sandbox.network_policy import apply_egress_rules_atomic, delete_rules_by_label
    label = "tldw-test-egress-allowlist"
    rules = apply_egress_rules_atomic("172.18.0.2", ["1.1.1.1/32"], label=label)
    try:
        # Minimal assertion: rules list is non-empty
        assert isinstance(rules, list) and rules
    finally:
        # Cleanup
        delete_rules_by_label(label)
