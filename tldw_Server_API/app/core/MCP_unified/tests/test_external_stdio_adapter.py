from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import (
    ACPMessage,
    ACPResponseError,
)
from tldw_Server_API.app.core.MCP_unified.external_servers.config_schema import (
    ExternalMCPServerConfig,
    ExternalStdioConfig,
    ExternalTimeoutConfig,
    ExternalTransportType,
)
from tldw_Server_API.app.core.MCP_unified.external_servers.transports.stdio_adapter import (
    StdioExternalMCPAdapter,
)


class _FakeStdioClient:
    def __init__(
        self,
        *,
        responses: dict[str, Any] | None = None,
        errors: dict[str, Exception] | None = None,
        delays: dict[str, float] | None = None,
    ) -> None:
        self.responses = dict(responses or {})
        self.errors = dict(errors or {})
        self.delays = dict(delays or {})
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.start_calls = 0
        self.close_calls = 0
        self.is_running = False
        self._next_id = 1

    async def start(self) -> None:
        self.start_calls += 1
        self.is_running = True

    async def close(self) -> None:
        self.close_calls += 1
        self.is_running = False

    async def call(self, method: str, params: dict[str, Any] | None = None) -> ACPMessage:
        payload = dict(params or {})
        self.calls.append((method, payload))

        delay = float(self.delays.get(method, 0.0))
        if delay > 0:
            await asyncio.sleep(delay)

        if method in self.errors:
            raise self.errors[method]

        response = self.responses.get(method, {})
        if isinstance(response, dict) and ("result" in response or "error" in response):
            result = response.get("result")
            error = response.get("error")
        else:
            result = response
            error = None

        message = ACPMessage(jsonrpc="2.0", id=self._next_id, result=result, error=error)
        self._next_id += 1
        return message


def _server_config(*, request_seconds: float = 0.2) -> ExternalMCPServerConfig:
    return ExternalMCPServerConfig(
        id="docs",
        name="Docs",
        transport=ExternalTransportType.STDIO,
        stdio=ExternalStdioConfig(command="node", args=["stub.js"]),
        timeouts=ExternalTimeoutConfig(connect_seconds=1.0, request_seconds=request_seconds),
    )


@pytest.mark.asyncio
async def test_stdio_adapter_connect_initializes_and_reports_health() -> None:
    cfg = _server_config()
    client = _FakeStdioClient(responses={"initialize": {"serverInfo": {"name": "stub"}}})
    adapter = StdioExternalMCPAdapter(cfg, client_factory=lambda _cfg: client)

    try:
        await adapter.connect()
        await adapter.connect()  # idempotent re-connect should be a no-op

        health = await adapter.health_check()
        assert health["configured"] is True
        assert health["connected"] is True
        assert health["initialized"] is True
        assert client.start_calls == 1
        assert [method for method, _ in client.calls] == ["initialize"]
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_stdio_adapter_list_tools_normalizes_response() -> None:
    cfg = _server_config()
    client = _FakeStdioClient(
        responses={
            "initialize": {"serverInfo": {"name": "stub"}},
            "tools/list": {
                "tools": [
                    {
                        "name": "docs.search",
                        "description": "Search docs",
                        "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
                        "metadata": {"scope": "read"},
                    },
                    {"name": "docs.defaulted", "description": 7, "inputSchema": "bad", "metadata": []},
                    {"name": 42, "description": "invalid"},
                ]
            },
        }
    )
    adapter = StdioExternalMCPAdapter(cfg, client_factory=lambda _cfg: client)

    try:
        tools = await adapter.list_tools()
        assert len(tools) == 2

        assert tools[0].name == "docs.search"
        assert tools[0].description == "Search docs"
        assert tools[0].input_schema["type"] == "object"
        assert tools[0].metadata["scope"] == "read"

        assert tools[1].name == "docs.defaulted"
        assert tools[1].description == ""
        assert tools[1].input_schema == {"type": "object"}
        assert tools[1].metadata == {}
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_stdio_adapter_call_tool_maps_acp_response_error() -> None:
    cfg = _server_config()
    client = _FakeStdioClient(
        responses={"initialize": {"serverInfo": {"name": "stub"}}},
        errors={"tools/call": ACPResponseError("upstream failed")},
    )
    adapter = StdioExternalMCPAdapter(cfg, client_factory=lambda _cfg: client)

    try:
        result = await adapter.call_tool("docs.search", {"q": "x"})
        assert result.is_error is True
        assert isinstance(result.content, list)
        assert result.content[0]["type"] == "text"
        assert result.content[0]["text"] == "upstream failed"
        assert result.metadata["server_id"] == "docs"
        assert result.metadata["tool_name"] == "docs.search"
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_stdio_adapter_request_timeout_has_method_context() -> None:
    cfg = _server_config(request_seconds=0.1)
    client = _FakeStdioClient(
        responses={"initialize": {"serverInfo": {"name": "stub"}}},
        delays={"tools/list": 0.25},
    )
    adapter = StdioExternalMCPAdapter(cfg, client_factory=lambda _cfg: client)

    try:
        with pytest.raises(TimeoutError, match="tools/list"):
            await adapter.list_tools()
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_stdio_adapter_connect_failure_closes_client() -> None:
    cfg = _server_config()
    client = _FakeStdioClient(errors={"initialize": ACPResponseError("init failed")})
    adapter = StdioExternalMCPAdapter(cfg, client_factory=lambda _cfg: client)

    with pytest.raises(ACPResponseError, match="init failed"):
        await adapter.connect()

    health = await adapter.health_check()
    assert health["connected"] is False
    assert health["initialized"] is False
    assert client.close_calls == 1
