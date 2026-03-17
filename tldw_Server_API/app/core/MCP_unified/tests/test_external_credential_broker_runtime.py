from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.MCP_unified.external_servers.config_schema import (
    parse_external_server_registry,
)
from tldw_Server_API.app.core.MCP_unified.external_servers.manager import (
    ExternalServerManager,
)
from tldw_Server_API.app.core.MCP_unified.external_servers.transports.base import (
    BrokeredExternalCredential,
    ExternalMCPTransportAdapter,
    ExternalToolCallResult,
    ExternalToolDefinition,
)
from tldw_Server_API.app.core.MCP_unified.external_servers import manager as manager_mod


class _BrokerAwareAdapter(ExternalMCPTransportAdapter):
    def __init__(self, server_id: str) -> None:
        super().__init__(server_id=server_id)
        self.seen_runtime_auth: BrokeredExternalCredential | None = None
        self.seen_context: Any = None

    @property
    def transport_name(self) -> str:
        return "websocket"

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health_check(self) -> dict[str, bool]:
        return {"configured": True, "connected": True, "initialized": True}

    async def list_tools(self) -> list[ExternalToolDefinition]:
        return [
            ExternalToolDefinition(
                name="repo.search",
                description="Search repositories",
                input_schema={"type": "object"},
                metadata={"category": "read"},
            )
        ]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: Any = None,
        runtime_auth: BrokeredExternalCredential | None = None,
    ) -> ExternalToolCallResult:
        del tool_name, arguments
        self.seen_runtime_auth = runtime_auth
        self.seen_context = context
        return ExternalToolCallResult(
            content=[{"type": "text", "text": "ok"}],
            is_error=False,
            metadata={"adapter": "broker-aware"},
        )


@pytest.mark.asyncio
async def test_external_tool_call_uses_ephemeral_brokered_credential(monkeypatch) -> None:
    cfg = parse_external_server_registry(
        {
            "servers": [
                {
                    "id": "github",
                    "name": "GitHub",
                    "transport": "websocket",
                    "websocket": {"url": "wss://github.example/ws"},
                    "policy": {"allow_tool_patterns": ["repo.*"]},
                }
            ]
        }
    )

    adapter = _BrokerAwareAdapter(server_id="github")

    async def _broker(**kwargs) -> BrokeredExternalCredential:
        assert kwargs["server_id"] == "github"
        assert kwargs["tool_name"] == "repo.search"
        return BrokeredExternalCredential(
            headers={"Authorization": "Bearer ephemeral-token"},
            metadata={"credential_mode": "brokered_ephemeral"},
        )

    monkeypatch.setattr(manager_mod, "build_transport_adapter", lambda _server: adapter)

    manager = (
        ExternalServerManager()
        .with_server_loader(lambda: list(cfg.servers))
        .with_credential_broker(_broker)
    )
    try:
        await manager.initialize()
        result = await manager.execute_virtual_tool(
            "ext.github.repo.search",
            {"query": "repo:test"},
            context={"request_id": "r1"},
        )
    finally:
        await manager.shutdown()

    assert adapter.seen_runtime_auth is not None
    assert adapter.seen_runtime_auth.headers == {"Authorization": "Bearer ephemeral-token"}
    assert result["metadata"]["credential_mode"] == "brokered_ephemeral"
    assert result["metadata"]["credential_injection"]["headers"] == ["Authorization"]
