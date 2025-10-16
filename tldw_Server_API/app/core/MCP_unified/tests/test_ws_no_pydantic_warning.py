"""Ensure no Pydantic deprecation warnings are emitted on WS send."""

import warnings

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.MCP_unified import get_mcp_server
from tldw_Server_API.app.main import app


@pytest.fixture
def ws_client(monkeypatch):
    monkeypatch.setenv("MCP_WS_AUTH_REQUIRED", "false")
    monkeypatch.setenv("MCP_ALLOWED_IPS", "")
    client = TestClient(app)
    server = get_mcp_server()
    server.config.ws_auth_required = False
    server.config.allowed_client_ips = []
    server.config.blocked_client_ips = []
    try:
        yield client
    finally:
        client.close()


def test_ws_no_pydantic_deprecation_warning(ws_client):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        with ws_client.websocket_connect("/api/v1/mcp/ws?client_id=warnchk") as ws:
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {"clientInfo": {"name": "WarnChk"}},
                    "id": 1,
                }
            )
            _ = ws.receive_json()

    texts = [str(x.message) for x in w]
    assert not any("The `dict` method is deprecated" in t for t in texts)
