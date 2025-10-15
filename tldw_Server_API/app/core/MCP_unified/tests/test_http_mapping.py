import os
import base64
import json
import pytest

from fastapi.testclient import TestClient


def _setup_env():
    # Keep the app light for tests
    os.environ["TEST_MODE"] = "true"
    os.environ["DISABLE_HEAVY_STARTUP"] = "1"
    # Single-user mode with API key for simplicity
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "test-api-key-1234567890"
    os.environ["SINGLE_USER_FIXED_ID"] = "1"
    # Ensure MCP unified config has required secrets
    os.environ["MCP_JWT_SECRET"] = "x" * 64
    os.environ["MCP_API_KEY_SALT"] = "s" * 64


@pytest.fixture(scope="module")
def client():
    _setup_env()
    from fastapi import FastAPI
    from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import router as mcp_router
    app = FastAPI()
    app.include_router(mcp_router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c


def test_tools_list_unauth_forbidden_with_hint(client: TestClient):
    r = client.get("/api/v1/mcp/tools")
    assert r.status_code == 403
    body = r.json()
    # Endpoint maps -32001 to 403 with a hint under 'detail'
    assert isinstance(body, dict) and isinstance(body.get("detail"), dict)
    assert "hint" in body["detail"]


def test_tools_list_via_request_bearer_token_allowed(client: TestClient):
    # Use MCP JWT bearer for auth to avoid AuthNZ DB/RBAC complexity
    from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
    os.environ.setdefault("MCP_JWT_SECRET", "x" * 64)
    token = get_jwt_manager().create_access_token(subject="1")
    payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
    r = client.post("/api/v1/mcp/request", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict) and isinstance(body.get("result"), dict)
    assert "tools" in body["result"]


def test_initialize_request_sets_session_header(client: TestClient):
    payload = {"jsonrpc": "2.0", "method": "initialize", "params": {"clientInfo": {"name": "pytest"}}, "id": 1}
    # Provide a small safe_config via base64
    cfg = base64.b64encode(json.dumps({"snippet_length": 200}).encode("utf-8")).decode("utf-8")
    r = client.post(
        "/api/v1/mcp/request",
        json=payload,
        params={"config": cfg},
    )
    assert r.status_code == 200
    assert r.headers.get("mcp-session-id") is not None
    body = r.json()
    assert isinstance(body, dict) and body.get("result") is not None
    result = body["result"]
    assert result.get("serverInfo", {}).get("name") == "tldw-mcp-unified"


def test_resources_and_modules_mappings_unauth_forbidden(client: TestClient):
    # Unauthenticated should be forbidden for resources/modules
    r0 = client.get("/api/v1/mcp/resources")
    assert r0.status_code == 403

    r1 = client.get("/api/v1/mcp/modules")
    assert r1.status_code == 403


def test_tools_list_get_bearer_ok(client: TestClient):
    from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
    os.environ.setdefault("MCP_JWT_SECRET", "x" * 64)
    token = get_jwt_manager().create_access_token(subject="1")
    r = client.get("/api/v1/mcp/tools", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict) and "tools" in data


def test_modules_health_admin_bearer_ok(client: TestClient):
    # Use MCP JWT with admin role so it passes regardless of auth mode
    from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
    os.environ.setdefault("MCP_JWT_SECRET", "x" * 64)
    token = get_jwt_manager().create_access_token(subject="1", roles=["admin"])  # embed admin role
    r = client.get("/api/v1/mcp/modules/health", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict) and "health" in data
