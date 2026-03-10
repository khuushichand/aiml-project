from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.sandbox_module import SandboxModule
from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunStatus, RuntimeType


class _FakeSandboxService:
    def __init__(self) -> None:
        self.runtimes: list[RuntimeType | None] = []

    def start_run_scaffold(
        self,
        *,
        user_id: str,
        spec,  # noqa: ANN001 - minimal test stub
        spec_version: str,
        idem_key: str | None,
        raw_body,  # noqa: ANN001 - minimal test stub
        explicit_fields=None,  # noqa: ANN001 - minimal test stub
    ) -> RunStatus:
        self.runtimes.append(spec.runtime)
        return RunStatus(
            id="run-lima-1",
            phase=RunPhase.queued,
            spec_version=spec_version,
            runtime=spec.runtime or RuntimeType.docker,
            base_image=spec.base_image,
            started_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_sandbox_module_accepts_lima_runtime() -> None:
    module = SandboxModule(ModuleConfig(name="sandbox"))
    module._svc = _FakeSandboxService()
    ctx = RequestContext(
        request_id="req-lima-1",
        user_id="5",
        client_id="test-client",
        session_id=None,
        metadata={},
    )

    result = await module.execute_tool(
        "sandbox.run",
        {"runtime": "lima", "base_image": "ubuntu:24.04", "command": ["echo", "ok"]},
        context=ctx,
    )

    assert module._svc.runtimes == [RuntimeType.lima]
    assert result["runtime"] == "lima"
