from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tldw_Server_API.app.core.MCP_unified.external_servers.config_schema import (
    parse_external_server_registry,
)
from tldw_Server_API.app.core.MCP_unified.external_servers.manager import ExternalServerManager
from tldw_Server_API.app.core.MCP_unified.external_servers.transports.base import (
    ExternalMCPTransportAdapter,
    ExternalToolCallResult,
    ExternalToolDefinition,
)
from tldw_Server_API.app.core.MCP_unified.external_servers import manager as manager_mod


class _FakeAdapter(ExternalMCPTransportAdapter):
    def __init__(self, server_id: str, tools: list[ExternalToolDefinition]) -> None:
        super().__init__(server_id)
        self.connected = False
        self.tools = tools
        self.fail_list = False
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.next_call_exception: Exception | None = None
        self.next_call_is_error = False

    @property
    def transport_name(self) -> str:
        return "fake"

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.connected = False

    async def health_check(self) -> dict[str, bool]:
        return {"configured": True, "connected": self.connected}

    async def list_tools(self) -> list[ExternalToolDefinition]:
        if self.fail_list:
            raise RuntimeError("discovery failed")
        return list(self.tools)

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context=None,
    ) -> ExternalToolCallResult:
        del context
        self.calls.append((tool_name, dict(arguments)))
        if self.next_call_exception is not None:
            exc = self.next_call_exception
            self.next_call_exception = None
            raise exc
        if self.next_call_is_error:
            self.next_call_is_error = False
            return ExternalToolCallResult(
                content=[{"type": "text", "text": "upstream failed"}],
                is_error=True,
                metadata={"adapter": "fake"},
            )
        return ExternalToolCallResult(
            content={"ok": True, "tool": tool_name, "args": dict(arguments)},
            is_error=False,
            metadata={"adapter": "fake"},
        )


def _registry_payload(*, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "servers": [
            {
                "id": "docs",
                "name": "Docs",
                "transport": "websocket",
                "websocket": {"url": "wss://example.test/ws"},
                "policy": policy or {},
            }
        ]
    }


def _patch_loader_and_adapter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: dict[str, Any],
    adapter: _FakeAdapter,
) -> None:
    cfg = parse_external_server_registry(payload)
    monkeypatch.setattr(manager_mod, "load_external_server_registry", lambda _path=None: cfg)
    monkeypatch.setattr(manager_mod, "build_transport_adapter", lambda _server: adapter)


def test_parse_virtual_tool_name_routing_contract() -> None:
    server_id, tool_name = ExternalServerManager.parse_virtual_tool_name("ext.docs.docs.search")
    assert server_id == "docs"
    assert tool_name == "docs.search"

    with pytest.raises(ValueError, match="must start with 'ext.'"):
        ExternalServerManager.parse_virtual_tool_name("docs.search")
    with pytest.raises(ValueError, match="must match 'ext.<server_id>.<tool_name>'"):
        ExternalServerManager.parse_virtual_tool_name("ext.docs")


@pytest.mark.asyncio
async def test_discovery_filters_tools_and_unknown_virtual_tool_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    adapter = _FakeAdapter(
        server_id="docs",
        tools=[
            ExternalToolDefinition(name="docs.search", description="Search"),
            ExternalToolDefinition(name="docs.delete", description="Delete"),
        ],
    )
    _patch_loader_and_adapter(
        monkeypatch,
        payload=_registry_payload(
            policy={
                "allow_tool_patterns": ["docs.*"],
                "deny_tool_patterns": ["docs.delete"],
                "allow_writes": True,
                "require_write_confirmation": False,
            }
        ),
        adapter=adapter,
    )

    unused_config = tmp_path / "unused.yaml"
    unused_config.write_text("servers: []\n", encoding="utf-8")
    manager = ExternalServerManager(config_path=str(unused_config))
    try:
        await manager.initialize()
        virtual_names = [tool.virtual_name for tool in manager.list_virtual_tools()]
        assert virtual_names == ["ext.docs.docs.search"]

        with pytest.raises(ValueError, match="Unknown external virtual tool"):
            await manager.execute_virtual_tool("ext.docs.docs.delete", {})
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_write_tool_blocked_when_allow_writes_false(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _FakeAdapter(
        server_id="docs",
        tools=[
            ExternalToolDefinition(
                name="docs.update",
                description="Update",
                metadata={"category": "management"},
            )
        ],
    )
    _patch_loader_and_adapter(
        monkeypatch,
        payload=_registry_payload(
            policy={
                "allow_tool_patterns": ["docs.*"],
                "allow_writes": False,
                "require_write_confirmation": True,
            }
        ),
        adapter=adapter,
    )

    manager = ExternalServerManager()
    try:
        await manager.initialize()
        with pytest.raises(PermissionError, match="write tool"):
            await manager.execute_virtual_tool("ext.docs.docs.update", {})
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_write_tool_requires_confirmation_and_strips_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _FakeAdapter(
        server_id="docs",
        tools=[
            ExternalToolDefinition(
                name="docs.update",
                description="Update",
                metadata={"category": "management"},
            )
        ],
    )
    _patch_loader_and_adapter(
        monkeypatch,
        payload=_registry_payload(
            policy={
                "allow_tool_patterns": ["docs.*"],
                "allow_writes": True,
                "require_write_confirmation": True,
            }
        ),
        adapter=adapter,
    )

    manager = ExternalServerManager()
    try:
        await manager.initialize()
        with pytest.raises(PermissionError, match="Write confirmation required"):
            await manager.execute_virtual_tool("ext.docs.docs.update", {"title": "x"})

        result = await manager.execute_virtual_tool(
            "ext.docs.docs.update",
            {"title": "x", "__confirm_write": True},
        )
        assert result["is_error"] is False
        assert adapter.calls[-1][0] == "docs.update"
        assert "__confirm_write" not in adapter.calls[-1][1]
        assert adapter.calls[-1][1]["title"] == "x"
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_refresh_partial_failure_clears_server_tools_and_reports_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _FakeAdapter(
        server_id="docs",
        tools=[ExternalToolDefinition(name="docs.search", description="Search")],
    )
    _patch_loader_and_adapter(monkeypatch, payload=_registry_payload(), adapter=adapter)

    manager = ExternalServerManager()
    try:
        await manager.initialize()
        assert [tool.virtual_name for tool in manager.list_virtual_tools()] == ["ext.docs.docs.search"]

        adapter.fail_list = True
        refresh = await manager.refresh_discovery(server_id="docs")
        assert refresh["errors"].get("docs") == "discovery failed"
        assert manager.list_virtual_tools() == []

        servers = await manager.list_servers()
        assert len(servers) == 1
        row = servers[0]
        assert row["id"] == "docs"
        assert row["discovery_ok"] is False
        assert row["status"] == "degraded"
        assert row["tool_count"] == 0
        assert row["last_error"] == "discovery failed"
        telemetry = row["telemetry"]
        assert telemetry["connect_attempts"] == 1
        assert telemetry["connect_successes"] == 1
        assert telemetry["discovery_attempts"] == 2
        assert telemetry["discovery_successes"] == 1
        assert telemetry["discovery_failures"] == 1
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_telemetry_tracks_call_outcomes_and_policy_denials(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _FakeAdapter(
        server_id="docs",
        tools=[
            ExternalToolDefinition(name="docs.search", description="Search"),
            ExternalToolDefinition(
                name="docs.update",
                description="Update",
                metadata={"category": "management"},
            ),
        ],
    )
    _patch_loader_and_adapter(
        monkeypatch,
        payload=_registry_payload(
            policy={
                "allow_tool_patterns": ["docs.*"],
                "allow_writes": True,
                "require_write_confirmation": True,
            }
        ),
        adapter=adapter,
    )

    manager = ExternalServerManager()
    try:
        await manager.initialize()

        ok = await manager.execute_virtual_tool("ext.docs.docs.search", {"q": "x"})
        assert ok["is_error"] is False

        adapter.next_call_is_error = True
        upstream_err = await manager.execute_virtual_tool("ext.docs.docs.search", {"q": "y"})
        assert upstream_err["is_error"] is True

        adapter.next_call_exception = TimeoutError("upstream timeout")
        with pytest.raises(TimeoutError, match="upstream timeout"):
            await manager.execute_virtual_tool("ext.docs.docs.search", {"q": "z"})

        with pytest.raises(PermissionError, match="Write confirmation required"):
            await manager.execute_virtual_tool("ext.docs.docs.update", {"title": "no-confirm"})

        servers = await manager.list_servers()
        assert len(servers) == 1
        telemetry = servers[0]["telemetry"]
        assert telemetry["connect_attempts"] == 1
        assert telemetry["connect_successes"] == 1
        assert telemetry["connect_failures"] == 0
        assert telemetry["discovery_attempts"] == 1
        assert telemetry["discovery_successes"] == 1
        assert telemetry["discovery_failures"] == 0
        assert telemetry["call_attempts"] == 3
        assert telemetry["call_successes"] == 2
        assert telemetry["call_failures"] == 1
        assert telemetry["call_timeouts"] == 1
        assert telemetry["call_upstream_errors"] == 1
        assert telemetry["policy_denials"] == 1
        assert telemetry["last_discovered_tool_count"] == 2
        assert telemetry["last_call_latency_ms"] is not None
        assert telemetry["avg_call_latency_ms"] is not None
        assert telemetry["last_error"] is not None
    finally:
        await manager.shutdown()
