from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_list_inventory_loads_registry_off_event_loop(monkeypatch) -> None:
    from tldw_Server_API.app.services import mcp_hub_external_legacy_inventory as legacy_inventory

    class _FakeServer:
        def __init__(self) -> None:
            self.id = "docs"
            self.name = "Docs"
            self.enabled = True
            self.transport = SimpleNamespace(value="websocket")

        def model_dump(self) -> dict[str, object]:
            return {
                "id": self.id,
                "name": self.name,
                "enabled": self.enabled,
                "transport": self.transport.value,
                "websocket": {"url": "wss://docs.example/ws"},
            }

    calls: list[tuple[object, tuple[object, ...]]] = []

    async def _fake_to_thread(func, *args):
        calls.append((func, args))
        return SimpleNamespace(servers=[_FakeServer()])

    monkeypatch.setattr(legacy_inventory.asyncio, "to_thread", _fake_to_thread)

    service = legacy_inventory.McpHubExternalLegacyInventoryService(config_path="/tmp/external.yaml")

    rows = await service.list_inventory()

    assert calls == [(legacy_inventory.load_external_server_registry, ("/tmp/external.yaml",))]
    assert rows == [
        {
            "id": "docs",
            "name": "Docs",
            "enabled": True,
            "transport": "websocket",
            "config": {"websocket": {"url": "wss://docs.example/ws"}},
            "legacy_source_ref": "yaml:docs",
        }
    ]
