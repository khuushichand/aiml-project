from __future__ import annotations

from tldw_Server_API.app.core.Sandbox.models import RuntimeType
from tldw_Server_API.app.core.Sandbox.runners.lima_runner import LimaRunner


def test_lima_preflight_returns_unavailable_when_limactl_missing(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "0")
    result = LimaRunner().preflight(network_policy="deny_all")

    assert result.runtime == RuntimeType.lima
    assert result.available is False
    assert "limactl_missing" in result.reasons


def test_lima_preflight_wsl_fails_closed_with_permission_reason(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "1")
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.delenv("TLDW_SANDBOX_LIMA_ENFORCER_DENY_ALL_READY", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_LIMA_ENFORCER_ALLOWLIST_READY", raising=False)
    monkeypatch.delenv("TLDW_SANDBOX_LIMA_ENFORCER_PERMISSION_DENIED", raising=False)

    result = LimaRunner().preflight(network_policy="deny_all")

    assert result.runtime == RuntimeType.lima
    assert result.available is False
    assert result.host.get("variant") == "wsl"
    assert "permission_denied_host_enforcement" in result.reasons


def test_lima_preflight_permission_override_returns_permission_reason(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_ENFORCER_PERMISSION_DENIED", "1")

    result = LimaRunner().preflight(network_policy="allowlist")

    assert result.runtime == RuntimeType.lima
    assert result.available is False
    assert result.enforcement_ready == {"deny_all": False, "allowlist": False}
    assert "permission_denied_host_enforcement" in result.reasons
