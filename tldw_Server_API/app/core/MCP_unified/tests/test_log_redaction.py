import pytest
from loguru import logger

from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, MCPRequest, RequestContext
from tldw_Server_API.app.core.MCP_unified.server import MCPServer


@pytest.mark.asyncio
async def test_protocol_error_log_redacts_tokens():
    proto = MCPProtocol()
    # Replace a handler to force an exception which includes secrets
    async def boom(params, context):
        raise Exception("Authorization: Bearer secret.token token=mysecret refresh_token=abc")
    proto.handlers["ping"] = boom

    captured = []
    sink_id = logger.add(lambda m: captured.append(m.record.get("message", "")), level="DEBUG")
    try:
        req = MCPRequest(method="ping", id="redact1")
        ctx = RequestContext(request_id="r", user_id="u", client_id="c")
        await proto.process_request(req, ctx)
    except Exception:
        # process_request swallows and returns MCPResponse; shouldn't raise
        pass
    finally:
        logger.remove(sink_id)

    # Ensure masked in logs
    text = "\n".join(str(x) for x in captured)
    assert "Bearer ****" in text
    assert "token=****" in text
    assert "refresh_token=****" in text
    assert "mysecret" not in text and "secret.token" not in text and "abc" not in text


class FakeWebSocket:
    def __init__(self, headers: dict, client_host: str = "127.0.0.1"):
        from types import SimpleNamespace
        self.headers = headers
        self.client = SimpleNamespace(host=client_host)
        self.accepted = False
        self.closed = False
        self.close_args = None
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = True
        self.close_args = (code, reason)

    async def send_json(self, data):
        self.sent.append(data)

    async def receive_json(self):
        # Force disconnect immediately after accept if needed
        from fastapi import WebSocketDisconnect
        raise WebSocketDisconnect()


@pytest.mark.asyncio
async def test_server_ws_auth_debug_log_redacts_tokens(monkeypatch):
    server = MCPServer()
    server.config.ws_allowed_origins = ["*"]
    server.config.ws_auth_required = True

    # Monkeypatch MCP JWT verification to raise an error including tokens
    def bad_verify(token: str):
        raise Exception(f"MCP JWT auth failed: Bearer {token} token=mytok refresh_token=abc")
    server.jwt_manager.verify_token = bad_verify  # type: ignore

    # Provide a Bearer header to trigger both AuthNZ failure and MCP JWT fallback
    ws = FakeWebSocket(headers={
        "origin": "https://any.com",
        "Authorization": "Bearer supersecrettoken",
    })

    captured = []
    sink_id = logger.add(lambda m: captured.append(m.record.get("message", "")), level="DEBUG")
    try:
        await server.handle_websocket(ws, client_id="c1")
    finally:
        logger.remove(sink_id)

    text = "\n".join(str(x) for x in captured)
    # Expect debug log line with masked tokens
    assert "MCP JWT auth failed" in text
    assert "Bearer ****" in text
    assert "token=****" in text and "refresh_token=****" in text
    assert "supersecrettoken" not in text and "mytok" not in text and "abc" not in text
