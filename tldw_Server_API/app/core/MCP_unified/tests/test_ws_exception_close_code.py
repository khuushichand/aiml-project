import json
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_mcp_ws_top_level_exception_closes_1011(monkeypatch):
    """When a top-level exception occurs, the server should close with code 1011 and not emit non-JSON-RPC frames."""
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.MCP_unified import get_mcp_server
    import tldw_Server_API.app.core.MCP_unified.server as mcp_srv

    # Monkeypatch receive_json to raise a generic exception at first receive.
    original_receive = mcp_srv.WebSocketConnection.receive_json

    async def _boom(self):  # type: ignore[no-redef]
        raise RuntimeError("boom")

    monkeypatch.setattr(mcp_srv.WebSocketConnection, "receive_json", _boom)

    # Disable WS auth and IP filtering for the test
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("MCP_WS_AUTH_REQUIRED", "false")
    monkeypatch.setenv("MCP_ALLOWED_IPS", "")
    srv = get_mcp_server()
    srv.config.ws_auth_required = False
    try:
        srv.config.debug_mode = True
    except Exception:
        pass
    srv.config.allowed_client_ips = []

    # Ensure router is mounted for the test (policy-agnostic)
    try:
        from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import router as mcp_router
        from tldw_Server_API.app.core.config import API_V1_PREFIX
        app.include_router(mcp_router, prefix=f"{API_V1_PREFIX}/mcp")
    except Exception:
        pass

    with TestClient(app) as client:
        try:
            ws = client.websocket_connect("/api/v1/mcp/ws?client_id=errcase")
        except Exception:
            pytest.skip("MCP WebSocket endpoint not available in this build")
        with ws as ws:
            # Send a minimal JSON to trigger server receive path
            ws.send_text(json.dumps({"jsonrpc": "2.0", "method": "initialize", "id": 1}))
            # Expect immediate disconnect with 1011 and no JSON frame beforehand
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_text()
            assert getattr(exc.value, "code", None) == 1011

    # Restore original to avoid side effects (pytest monkeypatch auto-reverts, but explicit is fine)
    monkeypatch.setattr(mcp_srv.WebSocketConnection, "receive_json", original_receive)
