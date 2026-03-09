from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.sandbox_module import SandboxModule
from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunStatus, RuntimeType, Session, TrustLevel


class _FakeSandboxService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.specs: list[object] = []
        self.sessions: dict[str, Session] = {}
        self.session_owners: dict[str, str] = {}

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
        self.specs.append(spec)
        return RunStatus(
            id="run-test-1",
            phase=RunPhase.queued,
            spec_version=spec_version,
            runtime=spec.runtime or RuntimeType.docker,
            base_image=spec.base_image,
            started_at=datetime.now(timezone.utc),
        )

    def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(str(session_id))

    def get_session_owner(self, session_id: str) -> str | None:
        return self.session_owners.get(str(session_id))


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


@pytest.mark.asyncio
async def test_sandbox_run_rejects_unowned_session_id() -> None:
    module = SandboxModule(ModuleConfig(name="sandbox"))
    module._svc = _FakeSandboxService()
    module._svc.sessions["sess-1"] = Session(
        id="sess-1",
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        expires_at=None,
    )
    module._svc.session_owners["sess-1"] = "88"
    ctx = RequestContext(
        request_id="req-2",
        user_id="77",
        client_id="test-client",
        session_id=None,
        metadata={},
    )

    with pytest.raises(PermissionError):
        await module.execute_tool(
            "sandbox.run",
            {
                "session_id": "sess-1",
                "command": ["python", "-c", "print('ok')"],
            },
            context=ctx,
        )

    assert module._svc.user_ids == []


@pytest.mark.asyncio
async def test_sandbox_run_inherits_owned_session_defaults() -> None:
    module = SandboxModule(ModuleConfig(name="sandbox"))
    module._svc = _FakeSandboxService()
    module._svc.sessions["sess-2"] = Session(
        id="sess-2",
        runtime=RuntimeType.docker,
        base_image="python:3.12-slim",
        expires_at=None,
        cpu_limit=1.5,
        memory_mb=768,
        timeout_sec=77,
        network_policy="deny_all",
        env={"SESSION_TOKEN": "present"},
        labels={"team": "sandbox"},
        trust_level=TrustLevel.untrusted,
    )
    module._svc.session_owners["sess-2"] = "77"
    ctx = RequestContext(
        request_id="req-3",
        user_id="77",
        client_id="test-client",
        session_id=None,
        metadata={},
    )

    result = await module.execute_tool(
        "sandbox.run",
        {
            "session_id": "sess-2",
            "command": ["python", "-c", "print('ok')"],
        },
        context=ctx,
    )

    assert result["base_image"] == "python:3.12-slim"
    spec = module._svc.specs[-1]
    assert spec.runtime == RuntimeType.docker
    assert spec.base_image == "python:3.12-slim"
    assert spec.cpu == 1.5
    assert spec.memory_mb == 768
    assert spec.timeout_sec == 77
    assert spec.network_policy == "deny_all"
    assert spec.env == {"SESSION_TOKEN": "present"}
    assert spec.trust_level == TrustLevel.untrusted


@pytest.mark.asyncio
async def test_sandbox_run_allows_permission_based_admin_override() -> None:
    module = SandboxModule(ModuleConfig(name="sandbox"))
    module._svc = _FakeSandboxService()
    module._svc.sessions["sess-admin"] = Session(
        id="sess-admin",
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        expires_at=None,
    )
    module._svc.session_owners["sess-admin"] = "88"
    ctx = RequestContext(
        request_id="req-admin-1",
        user_id="77",
        client_id="test-client",
        session_id=None,
        metadata={"permissions": ["system.configure"]},
    )

    result = await module.execute_tool(
        "sandbox.run",
        {
            "session_id": "sess-admin",
            "command": ["python", "-c", "print('ok')"],
        },
        context=ctx,
    )

    assert result["id"] == "run-test-1"
    assert module._svc.user_ids == ["77"]
