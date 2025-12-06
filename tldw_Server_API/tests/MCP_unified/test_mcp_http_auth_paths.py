import os
from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient
from loguru import logger
import pytest

from tldw_Server_API.app.main import app
from tldw_Server_API.app.api.v1.endpoints import mcp_unified_endpoint as mcp_ep


# Disable HTTP security guard for these tests (IP allowlist/mTLS) to focus on auth behavior.
try:
    from tldw_Server_API.app.core.MCP_unified.security.request_guards import (  # type: ignore[attr-defined]
        enforce_http_security as _ehs,
    )

    app.dependency_overrides[_ehs] = lambda: None
except Exception as exc:  # pragma: no cover - defensive
    logger.debug(f"Unable to override enforce_http_security for MCP tests: {exc}")


client = TestClient(app)


class _DummyProtocol:
    async def process_request(self, payload, ctx):
        from tldw_Server_API.app.core.MCP_unified.protocol import MCPResponse

        if isinstance(payload, list):
            return [MCPResponse(result={"ok": True}, id=getattr(p, "id", None)) for p in payload]
        return MCPResponse(result={"ok": True}, id=getattr(payload, "id", None))


class _DummyServer:
    def __init__(self):
        self.initialized = True
        self.protocol = _DummyProtocol()
        self.last_metadata: Optional[Dict[str, Any]] = None

    async def initialize(self):
        self.initialized = True

    async def handle_http_request(
        self,
        request,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        from tldw_Server_API.app.core.MCP_unified.protocol import MCPResponse

        self.last_metadata = metadata or {}
        return MCPResponse(result={"ok": True}, id=getattr(request, "id", None))


def _install_dummy_server(monkeypatch) -> _DummyServer:
    server = _DummyServer()
    monkeypatch.setattr(mcp_ep, "get_mcp_server", lambda: server)
    return server


@pytest.mark.asyncio
async def test_mcp_http_requests_use_single_api_key_validation(monkeypatch):
    """
    Ensure /mcp/request and /mcp/request/batch validate a given API key exactly once
    per request and reuse the resolved metadata (org_id/team_id) without re-validating.
    """

    # Force multi-user API key path so get_current_user uses APIKeyManager instead of
    # the single-user shortcut.
    monkeypatch.setattr(mcp_ep, "is_single_user_mode", lambda: False)
    monkeypatch.setattr(mcp_ep, "is_single_user_profile_mode", lambda: False)

    calls: List[Dict[str, Any]] = []

    class _DummyApiManager:
        async def validate_api_key(self, key: str, ip_address: Optional[str] = None) -> Dict[str, Any]:
            calls.append({"key": key, "ip": ip_address})
            return {"user_id": "123", "org_id": 9, "team_id": 7}

    async def _fake_get_api_key_manager():
        return _DummyApiManager()

    monkeypatch.setattr(mcp_ep, "get_api_key_manager", _fake_get_api_key_manager)

    server = _install_dummy_server(monkeypatch)

    headers = {"X-API-KEY": "test-api-key-123", "X-Real-IP": "127.0.0.1"}

    # Single MCP HTTP request
    body = {"jsonrpc": "2.0", "method": "status", "id": 1}
    r1 = client.post("/api/v1/mcp/request", headers=headers, json=body)
    assert r1.status_code == 200, r1.text
    data1 = r1.json()
    assert isinstance(data1, dict)
    assert data1.get("result", {}).get("ok") is True

    # API key should have been validated exactly once
    assert len(calls) == 1
    assert calls[0]["key"] == "test-api-key-123"

    # org/team metadata from the key should be propagated to the MCP server
    assert server.last_metadata is not None
    assert server.last_metadata.get("org_id") == 9
    assert server.last_metadata.get("team_id") == 7
    assert "roles" in server.last_metadata  # derived from TokenData roles=["api_client"]

    # Batch MCP HTTP request
    batch_body = [
        {"jsonrpc": "2.0", "method": "status", "id": 2},
        {"jsonrpc": "2.0", "method": "status", "id": 3},
    ]
    r2 = client.post("/api/v1/mcp/request/batch", headers=headers, json=batch_body)
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert isinstance(data2, list)
    assert all(isinstance(item, dict) for item in data2)

    # API key should have been validated exactly once for the batch request as well
    assert len(calls) == 2
    assert calls[1]["key"] == "test-api-key-123"

    # org/team metadata should also be present for the batch path
    assert server.last_metadata is not None
    assert server.last_metadata.get("org_id") == 9
    assert server.last_metadata.get("team_id") == 7


@pytest.mark.asyncio
async def test_modules_health_uses_principal_metadata(monkeypatch):
    """
    Ensure /mcp/modules/health uses the principal returned by require_permissions(SYSTEM_LOGS)
    and forwards its roles/permissions into the MCP metadata.
    """
    from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
    from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_LOGS
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps

    server = _install_dummy_server(monkeypatch)

    calls: list[AuthPrincipal] = []

    principal = AuthPrincipal(
        kind="user",
        user_id=42,
        roles=["observer", "admin"],
        permissions=[SYSTEM_LOGS, "other.permission"],
        is_admin=False,
    )

    async def _fake_resolve_auth_principal(request) -> AuthPrincipal:  # type: ignore[override]
        calls.append(principal)
        return principal

    # Patch the core resolver used by get_auth_principal so that require_permissions
    # sees our synthetic principal.
    monkeypatch.setattr(auth_deps, "_resolve_auth_principal", _fake_resolve_auth_principal)

    r = client.get("/api/v1/mcp/modules/health")
    assert r.status_code == 200, r.text

    # Principal should have been resolved exactly once for this request.
    assert len(calls) == 1

    assert server.last_metadata is not None
    # Endpoint should pass through roles/permissions from the principal
    assert server.last_metadata.get("roles") == principal.roles
    assert server.last_metadata.get("permissions") == principal.permissions
    # Admin override flag should be set as documented
    assert server.last_metadata.get("admin_override") is True
