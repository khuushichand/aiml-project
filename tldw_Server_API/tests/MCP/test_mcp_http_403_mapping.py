import json
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


client = TestClient(app)


def test_mcp_tools_list_unauth_returns_403_hint():
    r = client.get("/api/v1/mcp/tools")
    assert r.status_code == 403, r.text
    data = r.json()
    assert "detail" in data
    detail = data["detail"]
    assert isinstance(detail, dict)
    assert detail.get("message") in ("Insufficient permissions",)
    assert "hint" in detail


def test_mcp_request_tools_list_unauth_returns_403_hint():
    payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": "t1"}
    r = client.post("/api/v1/mcp/request", json=payload)
    assert r.status_code == 403, r.text
    data = r.json()
    assert "detail" in data
    detail = data["detail"]
    assert isinstance(detail, dict)
    assert detail.get("message") in ("Insufficient permissions",)
    assert "hint" in detail
