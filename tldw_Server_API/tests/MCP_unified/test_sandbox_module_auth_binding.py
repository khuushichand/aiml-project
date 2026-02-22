from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.sandbox_module import SandboxModule
from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunStatus, RuntimeType


class _FakeSandboxService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []

    def start_run_scaffold(
        self,
        *,
        user_id: str,
        spec,  # noqa: ANN001 - minimal test stub
        spec_version: str,
        idem_key: str | None,
        raw_body,  # noqa: ANN001 - minimal test stub
    ) -> RunStatus:
        self.user_ids.append(str(user_id))
        return RunStatus(
            id="run-test-1",
            phase=RunPhase.queued,
            spec_version=spec_version,
            runtime=spec.runtime or RuntimeType.docker,
            base_image=spec.base_image,
            started_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_sandbox_run_requires_authenticated_context() -> None:
    module = SandboxModule(ModuleConfig(name="sandbox"))
    module._svc = _FakeSandboxService()

    with pytest.raises(PermissionError):
        await module.execute_tool(
            "sandbox.run",
            {
                "base_image": "python:3.11-slim",
                "command": ["python", "-c", "print('ok')"],
            },
            context=None,
        )

    assert module._svc.user_ids == []


@pytest.mark.asyncio
async def test_sandbox_run_binds_authenticated_context_user_id() -> None:
    module = SandboxModule(ModuleConfig(name="sandbox"))
    module._svc = _FakeSandboxService()
    ctx = RequestContext(
        request_id="req-1",
        user_id="77",
        client_id="test-client",
        session_id=None,
        metadata={},
    )

    result = await module.execute_tool(
        "sandbox.run",
        {
            "base_image": "python:3.11-slim",
            "command": ["python", "-c", "print('ok')"],
        },
        context=ctx,
    )

    assert module._svc.user_ids == ["77"]
    assert result["id"] == "run-test-1"
