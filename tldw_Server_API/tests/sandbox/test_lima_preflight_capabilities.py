from __future__ import annotations

from tldw_Server_API.app.core.Sandbox.models import RuntimeType
from tldw_Server_API.app.core.Sandbox.runners.lima_runner import LimaRunner


def test_lima_preflight_returns_unavailable_when_limactl_missing(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "0")
    result = LimaRunner().preflight(network_policy="deny_all")

    assert result.runtime == RuntimeType.lima
    assert result.available is False
    assert "limactl_missing" in result.reasons
