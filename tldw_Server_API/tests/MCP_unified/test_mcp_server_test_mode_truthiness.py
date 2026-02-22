from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.MCP_unified.server import MCPServer


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_register_default_modules_auto_enables_media_with_test_mode_y(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_MODE", "y")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")
    monkeypatch.delenv("MCP_ENABLE_MEDIA_MODULE", raising=False)
    monkeypatch.setenv("MCP_ENABLE_SANDBOX_MODULE", "0")
    monkeypatch.setenv("MCP_MODULES_CONFIG", "/tmp/tldw-does-not-exist.yaml")
    monkeypatch.delenv("MCP_MODULES", raising=False)

    import importlib

    fake_module = SimpleNamespace(MediaModule=type("MediaModule", (), {}))
    monkeypatch.setattr(importlib, "import_module", lambda path: fake_module)

    server = MCPServer()
    registered: list[str] = []

    async def _fake_register_module(module_id: str, cls, cfg) -> None:
        registered.append(module_id)

    monkeypatch.setattr(server.module_registry, "register_module", _fake_register_module)

    await server._register_default_modules()

    assert "media" in registered
