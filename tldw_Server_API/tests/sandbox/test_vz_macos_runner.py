from __future__ import annotations

import tldw_Server_API.app.core.Sandbox.runners.vz_common as vz_common
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunSpec, RuntimeType
from tldw_Server_API.app.core.Sandbox.runners.vz_macos_runner import VZMacOSRunner


def test_vz_macos_preflight_requires_template_and_helper(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_MACOS_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_MACOS_HELPER_READY", "0")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY", "0")

    result = VZMacOSRunner().preflight(network_policy="deny_all")

    assert result.available is False
    assert "macos_helper_missing" in result.reasons
    assert "macos_template_missing" in result.reasons


def test_vz_macos_fake_run_completes(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_VZ_MACOS_FAKE_EXEC", "1")

    runner = VZMacOSRunner()
    status = runner.start_run(
        run_id="run-456",
        spec=RunSpec(
            session_id=None,
            runtime=RuntimeType.vz_macos,
            base_image="macos-15",
            command=["echo", "ok"],
            network_policy="deny_all",
        ),
    )

    assert status.phase == RunPhase.completed
    assert status.exit_code == 0


def test_vz_macos_preflight_requires_execution_readiness(monkeypatch) -> None:
    monkeypatch.setattr(vz_common.sys, "platform", "darwin")
    monkeypatch.setattr(vz_common.platform, "machine", lambda: "arm64")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_MACOS_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_MACOS_HELPER_READY", "1")
    monkeypatch.setenv("TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY", "1")
    monkeypatch.delenv("TLDW_SANDBOX_VZ_MACOS_FAKE_EXEC", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_VZ_MACOS_EXEC_READY", raising=False)

    result = VZMacOSRunner().preflight(network_policy="deny_all")

    assert result.available is False
    assert "real_execution_not_implemented" in result.reasons
