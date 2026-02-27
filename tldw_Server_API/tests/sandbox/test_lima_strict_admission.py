from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Sandbox.models import RunSpec, RuntimeType
from tldw_Server_API.app.core.Sandbox.policy import SandboxPolicy
from tldw_Server_API.app.core.Sandbox.service import SandboxService


def test_lima_allowlist_rejected_when_strict_not_ready(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_ENFORCER_ALLOWLIST_READY", "0")

    svc = SandboxService()
    spec = RunSpec(
        session_id=None,
        runtime=RuntimeType.lima,
        base_image="ubuntu:24.04",
        command=["echo", "ok"],
        network_policy="allowlist",
    )

    with pytest.raises(SandboxPolicy.PolicyUnsupported):
        svc.start_run_scaffold(
            user_id="1",
            spec=spec,
            spec_version="1.0",
            idem_key=None,
            raw_body={},
        )
