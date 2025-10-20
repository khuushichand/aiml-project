import os
import asyncio
import pytest

from types import SimpleNamespace

from tldw_Server_API.app.core.MCP_unified.server import MCPServer
from tldw_Server_API.app.core.MCP_unified.config import get_config
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
from tldw_Server_API.app.core.MCP_unified.auth.rate_limiter import DistributedRateLimiter
from tldw_Server_API.app.core.MCP_unified.auth.authnz_rbac import AuthNZRBAC, Resource, Action
from fastapi import WebSocketDisconnect


class FakeWebSocket:
    def __init__(self, headers: dict, client_host: str = "127.0.0.1"):
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
        # Simulate client disconnect immediately after accepting
        raise WebSocketDisconnect()


@pytest.mark.asyncio
async def test_ws_origin_denied(monkeypatch):
    # Configure allowed origins to a different host than provided header
    os.environ["MCP_WS_ALLOWED_ORIGINS"] = "https://allowed.com"
    # Reset config cache
    try:
        get_config.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    server = MCPServer()
    # Ensure config picked up in case env cache didn't propagate
    server.config.ws_allowed_origins = ["https://allowed.com"]
    ws = FakeWebSocket(headers={"origin": "https://other.com"})

    await server.handle_websocket(ws, client_id="c1")
    assert ws.closed is True
    assert ws.accepted is False
    assert ws.close_args[0] == 1008
    assert "Origin not allowed" in (ws.close_args[1] or "")


@pytest.mark.asyncio
async def test_ws_query_auth_disabled_requires_auth(monkeypatch):
    # Allow any origin for this test and require auth
    os.environ["MCP_WS_ALLOWED_ORIGINS"] = "*"
    os.environ["MCP_WS_AUTH_REQUIRED"] = "1"
    os.environ["MCP_WS_ALLOW_QUERY_AUTH"] = "0"  # default, explicit here
    try:
        get_config.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    server = MCPServer()
    server.config.ws_allowed_origins = ["*"]
    server.config.ws_auth_required = True
    ws = FakeWebSocket(headers={"origin": "https://any.com"})

    # Provide tokens only via query args (which should be ignored)
    await server.handle_websocket(ws, client_id="c2", auth_token="ignored", api_key="ignored")
    assert ws.closed is True
    assert ws.accepted is False
    # Expect authentication required close when query tokens ignored
    assert ws.close_args[0] == 1008
    assert "Authentication required" in (ws.close_args[1] or "")


@pytest.mark.asyncio
async def test_ws_header_bearer_auth_accepts(monkeypatch):
    # Allow any origin and allow auth via header
    os.environ["MCP_WS_ALLOWED_ORIGINS"] = "*"
    os.environ["MCP_WS_AUTH_REQUIRED"] = "1"
    os.environ["MCP_WS_ALLOW_QUERY_AUTH"] = "0"
    os.environ["MCP_JWT_SECRET"] = "x" * 64  # strong secret
    try:
        get_config.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    # Create a token using the same JWT manager used by server
    _ = get_config()  # ensure config instantiated with env
    jwtm = get_jwt_manager()
    token = jwtm.create_access_token(subject="user1")

    server = MCPServer()
    server.config.ws_allowed_origins = ["*"]
    server.config.ws_auth_required = True
    ws = FakeWebSocket(headers={
        "origin": "https://any.com",
        "Authorization": f"Bearer {token}",
    })

    await server.handle_websocket(ws, client_id="c3")
    # Should have accepted, then disconnected immediately via FakeWebSocket.receive_json
    assert ws.accepted is True
    # It may or may not close explicitly in this path; but must not be closed with auth errors
    if ws.closed:
        # If closed, it should not be due to auth failures
        assert ws.close_args[0] != 1008


def test_redis_limiter_fallback_without_redis():
    # When redis client is None, fallback limiter should engage
    limiter = DistributedRateLimiter(rate=2, window=60, redis_client=None)

    async def run():
        allowed = []
        for _ in range(3):
            ok, _ra = await limiter.is_allowed("k1")
            allowed.append(ok)
        return allowed

    allowed = asyncio.get_event_loop().run_until_complete(run())
    # Token bucket fallback grants an initial free pass + burst tokens.
    # With rate=2, first three requests are allowed, the 4th is blocked.
    assert allowed[0] is True and allowed[1] is True and allowed[2] is True
    # Next call should block
    async def run_next():
        return await limiter.is_allowed("k1")
    ok4, _ = asyncio.get_event_loop().run_until_complete(run_next())
    assert ok4 is False


class _FakeRedis:
    def script_load(self, script):
        return "sha"

    async def evalsha(self, *args, **kwargs):
        raise RuntimeError("redis down")

    async def delete(self, *args, **kwargs):
        return 1

    async def zremrangebyscore(self, *args, **kwargs):
        return 0

    async def zcard(self, *args, **kwargs):
        return 0


def test_redis_limiter_fallback_on_error():
    limiter = DistributedRateLimiter(rate=1, window=60, redis_client=_FakeRedis())

    async def run():
        r1 = await limiter.is_allowed("k2")
        r2 = await limiter.is_allowed("k2")
        return r1, r2

    r1, r2 = asyncio.get_event_loop().run_until_complete(run())
    # With rate=1, initial free pass + 1 token → two allowed, third blocks
    assert r1[0] is True
    assert r2[0] is True
    r3 = asyncio.get_event_loop().run_until_complete(limiter.is_allowed("k2"))
    assert r3[0] is False


@pytest.mark.asyncio
async def test_distributed_limiter_uses_stub_when_unavailable(monkeypatch):
    # Use an unreachable Redis URL; factory should fallback to the in-process stub
    limiter = DistributedRateLimiter(rate=2, window=60, redis_url="redis://127.0.0.1:6399")

    allowed1, _ = await limiter.is_allowed("fallback-key")
    allowed2, _ = await limiter.is_allowed("fallback-key")
    allowed3, _ = await limiter.is_allowed("fallback-key")

    assert allowed1 is True
    assert allowed2 is True
    assert allowed3 is False


@pytest.mark.asyncio
async def test_rbac_denies_unmapped_permissions(monkeypatch):
    policy = AuthNZRBAC(db_pool=None)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.MCP_unified.auth.authnz_rbac._map_to_permission",
        lambda *args, **kwargs: None,
    )
    allowed = await policy.check_permission("1", Resource.MEDIA, Action.CREATE)
    assert allowed is False
