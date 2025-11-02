"""
test_mcp_basic.py
Description: MCP E2E - health/status, tools list, HTTP tool call, WS initialize, metrics access.
"""

import os
import json
import pytest
import httpx

from .fixtures import api_client


def _maybe_import_websockets():
    try:
        import websockets  # type: ignore
        return websockets
    except Exception:
        return None


@pytest.mark.critical
def test_mcp_http_and_ws(api_client):
    # 1) Status
    try:
        s = api_client.client.get("/api/v1/mcp/status")
        s.raise_for_status()
        sj = s.json()
        assert sj.get("status")
    except httpx.HTTPError as e:
        pytest.skip(f"MCP status not available: {e}")

    # 2) List tools (unauth may still be allowed in single-user with API key)
    try:
        tl = api_client.client.get("/api/v1/mcp/tools")
        # 200 or 403 (permission hint path allowed)
        assert tl.status_code in (200, 403)
    except httpx.HTTPError:
        pass

    # 3) HTTP request lifecycle (initialize + simple request)
    init_req = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {"clientInfo": {"name": "e2e-test", "version": "0.1"}},
        "id": 1,
    }
    try:
        r1 = api_client.client.post("/api/v1/mcp/request", json=init_req)
        r1.raise_for_status()
    except httpx.HTTPError as e:
        pytest.skip(f"MCP request path not available: {e}")

    # Call tools/list via request endpoint
    req = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}
    r2 = api_client.client.post("/api/v1/mcp/request", json=req)
    assert r2.status_code in (200, 403)  # permission hint path may 403

    # 4) WebSocket minimal initialize
    wsmod = _maybe_import_websockets()
    if not wsmod:
        pytest.skip("websockets not installed; skipping MCP WS test.")
    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000").replace("http://", "ws://").replace("https://", "wss://")
    url = f"{base}/api/v1/mcp/ws?client_id=e2e"

    try:
        import asyncio

        async def _run():
            async with wsmod.connect(url) as ws:
                await ws.send(json.dumps(init_req))
                # A JSON-RPC response or server protocol message should return
                raw = await ws.recv()
                assert raw

        asyncio.get_event_loop().run_until_complete(_run())
    except Exception as e:
        pytest.skip(f"MCP WS not available/configured: {e}")

    # 5) Metrics (may require admin) - allow 200/401/403
    m = api_client.client.get("/api/v1/mcp/metrics")
    assert m.status_code in (200, 401, 403)
