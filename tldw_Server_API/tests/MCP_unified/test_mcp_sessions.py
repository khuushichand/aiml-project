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


@pytest.mark.asyncio
async def test_mcp_websocket_session_context_binding_enforced():
    server = MCPServer()

    session = await server._get_or_create_session(
        "ws-sess-1",
        user_id="user-1",
        workspace_id="workspace-one",
        cwd="src/app",
    )

    assert session.workspace_id == "workspace-one"
    assert session.cwd == "src/app"

    rebound = await server._get_or_create_session(
        "ws-sess-1",
        user_id="user-1",
        workspace_id="workspace-one",
        cwd="src/app",
    )
    assert rebound is session

    with pytest.raises(PermissionError):
        await server._get_or_create_session(
            "ws-sess-1",
            user_id="user-1",
            workspace_id="workspace-two",
            cwd="src/app",
        )

    with pytest.raises(PermissionError):
        await server._get_or_create_session(
            "ws-sess-1",
            user_id="user-1",
            workspace_id="workspace-one",
            cwd="src/other",
        )


@pytest.mark.asyncio
async def test_mcp_websocket_session_can_bind_workspace_context_after_creation():
    server = MCPServer()

    session = await server._get_or_create_session("ws-sess-2", user_id="user-1")

    assert session.workspace_id is None
    assert session.cwd is None

    rebound = await server._get_or_create_session(
        "ws-sess-2",
        user_id="user-1",
        workspace_id="workspace-one",
        cwd="src/app",
    )

    assert rebound.workspace_id == "workspace-one"
    assert rebound.cwd == "src/app"

    with pytest.raises(PermissionError):
        await server._get_or_create_session("ws-sess-2", user_id="user-1")
