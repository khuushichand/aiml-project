import pytest
from fastapi.testclient import TestClient


def test_mcp_ws_invalid_json_returns_jsonrpc_parse_error(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.MCP_unified import get_mcp_server

    # Disable WS auth and IP filtering for the test
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("MCP_WS_AUTH_REQUIRED", "false")
    monkeypatch.setenv("MCP_ALLOWED_IPS", "")
    srv = get_mcp_server()
    srv.config.ws_auth_required = False
    try:
        srv.config.debug_mode = True
    except Exception:
        _ = None
    srv.config.allowed_client_ips = []

    # Ensure router is mounted for the test (policy-agnostic)
    try:
        from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import router as mcp_router
        from tldw_Server_API.app.core.config import API_V1_PREFIX
        app.include_router(mcp_router, prefix=f"{API_V1_PREFIX}/mcp")
    except Exception:
        _ = None

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect("/api/v1/mcp/ws?client_id=parseerr")
        except Exception:
            pytest.skip("MCP WebSocket endpoint not available in this build")
        with ws as ws:
            # Send an invalid JSON text frame; server should respond with a JSON-RPC parse error
            ws.send_text("not-json")
            msg = ws.receive_json()
            assert isinstance(msg, dict)
            assert msg.get("jsonrpc") == "2.0"
            assert isinstance(msg.get("error"), dict)
            assert msg["error"].get("code") == -32700
            assert "Parse error" in (msg["error"].get("message") or "")
