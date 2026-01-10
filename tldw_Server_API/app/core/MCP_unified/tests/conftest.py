"""Local test config for MCP WS tests.

- Provides lightweight stubs to avoid optional LLM import issues.
- Adds a reusable auth-disabled WebSocket TestClient fixture for MCP.
"""
from __future__ import annotations

try:
    from tldw_Server_API.app.core.LLM_Calls import local_chat_calls as _llm_local  # type: ignore
    if not hasattr(_llm_local, "legacy_chat_with_custom_openai_2"):
        def _stub(*args, **kwargs):  # pragma: no cover - simple stub
            return None
        setattr(_llm_local, "legacy_chat_with_custom_openai_2", _stub)
except Exception:
    pass

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mcp_ws_client(monkeypatch):
    """Reusable MCP WS client with auth disabled and relaxed IP checks.

    - Forces TEST_MODE to simplify route gating and startup
    - Disables MCP WS auth and IP allowlist for local tests
    """
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("MCP_WS_AUTH_REQUIRED", "false")
    # Accept both empty and JSON list for env-based list parsing
    monkeypatch.setenv("MCP_ALLOWED_IPS", "")

    # Import app and configure server instance
    from tldw_Server_API.app.main import app  # late import to pick up env
    try:
        from tldw_Server_API.app.core.MCP_unified import get_mcp_server
        server = get_mcp_server()
        server.config.ws_auth_required = False
        server.config.allowed_client_ips = []
        server.config.blocked_client_ips = []
    except Exception:
        # If server not yet initialized in tests, proceed; WS paths may init lazily
        pass

    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def ws_client(monkeypatch):
    """Alias for mcp_ws_client to match common fixture name across tests."""
    yield from mcp_ws_client(monkeypatch)  # type: ignore[misc]
