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
        self.explicit_fields: list[set[str] | None] = []

    def start_run_scaffold(
        self,
        *,
        user_id: str,
        spec,  # noqa: ANN001 - minimal test stub
        spec_version: str,
        idem_key: str | None,
        raw_body,  # noqa: ANN001 - minimal test stub
        explicit_fields: set[str] | None = None,
    ) -> RunStatus:
        self.explicit_fields.append(set(explicit_fields) if explicit_fields is not None else None)
        if spec.session_id and explicit_fields is not None:
            session = self.get_session(spec.session_id)
            if session is not None:
                if "runtime" not in explicit_fields and session.runtime is not None:
                    spec.runtime = session.runtime
                if "base_image" not in explicit_fields and session.base_image:
                    spec.base_image = session.base_image
                if "env" not in explicit_fields:
                    spec.env = dict(session.env or {})
                if "timeout_sec" not in explicit_fields and session.timeout_sec is not None:
                    spec.timeout_sec = int(session.timeout_sec)
                if "cpu" not in explicit_fields and session.cpu_limit is not None:
                    spec.cpu = float(session.cpu_limit)
                if "memory_mb" not in explicit_fields and session.memory_mb is not None:
                    spec.memory_mb = int(session.memory_mb)
                if "network_policy" not in explicit_fields and session.network_policy:
                    spec.network_policy = str(session.network_policy)
                if "trust_level" not in explicit_fields and session.trust_level is not None:
                    spec.trust_level = session.trust_level
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


@pytest.mark.asyncio
async def test_sandbox_run_refreshes_session_defaults_after_prelock_work(monkeypatch) -> None:
    module = SandboxModule(ModuleConfig(name="sandbox"))
    module._svc = _FakeSandboxService()
    module._svc.sessions["sess-refresh"] = Session(
        id="sess-refresh",
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        expires_at=None,
        timeout_sec=30,
        env={"SESSION_TOKEN": "old"},
        trust_level=TrustLevel.standard,
    )
    module._svc.session_owners["sess-refresh"] = "77"
    refreshed_session = Session(
        id="sess-refresh",
        runtime=RuntimeType.docker,
        base_image="python:3.12-slim",
        expires_at=None,
        timeout_sec=77,
        env={"SESSION_TOKEN": "new"},
        trust_level=TrustLevel.trusted,
    )
    ctx = RequestContext(
        request_id="req-refresh",
        user_id="77",
        client_id="test-client",
        session_id=None,
        metadata={},
    )

    original_decode_inline_files = module._decode_inline_files

    def _switch_session_then_decode(files):
        module._svc.sessions["sess-refresh"] = refreshed_session
        return original_decode_inline_files(files)

    monkeypatch.setattr(module, "_decode_inline_files", _switch_session_then_decode)

    result = await module.execute_tool(
        "sandbox.run",
        {
            "session_id": "sess-refresh",
            "command": ["python", "-c", "print('ok')"],
        },
        context=ctx,
    )

    spec = module._svc.specs[-1]
    assert result["base_image"] == "python:3.12-slim"
    assert spec.base_image == "python:3.12-slim"
    assert spec.timeout_sec == 77
    assert spec.env == {"SESSION_TOKEN": "new"}
    assert spec.trust_level == TrustLevel.trusted
