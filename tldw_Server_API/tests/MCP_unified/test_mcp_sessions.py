import pytest
from fastapi import HTTPException

from tldw_Server_API.app.core.MCP_unified.server import MCPServer
from tldw_Server_API.app.core.MCP_unified.protocol import MCPRequest, MCPResponse


class _NoopProtocol:
    async def process_request(self, request, context):
        return MCPResponse(result={"ok": True}, id=getattr(request, "id", None))


@pytest.mark.asyncio
async def test_mcp_session_binding_enforced():
    server = MCPServer()
    server.protocol = _NoopProtocol()

    req = MCPRequest(method="initialize", id="init-1")

    resp1 = await server.handle_http_request(req, user_id="user-1", metadata={"session_id": "sess-1"})
    assert resp1.result == {"ok": True}

    resp2 = await server.handle_http_request(req, user_id="user-1", metadata={"session_id": "sess-1"})
    assert resp2.result == {"ok": True}

    with pytest.raises(HTTPException) as exc:
        await server.handle_http_request(req, user_id="user-2", metadata={"session_id": "sess-1"})
    assert exc.value.status_code == 403
