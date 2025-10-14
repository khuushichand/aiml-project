"""
Ensure no Pydantic deprecation warnings are emitted on WS send.
"""

import os
import warnings
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


client = TestClient(app)


def test_ws_no_pydantic_deprecation_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        with client.websocket_connect("/api/v1/mcp/ws?client_id=warnchk") as ws:
            ws.send_json({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"clientInfo": {"name": "WarnChk"}},
                "id": 1,
            })
            _ = ws.receive_json()

    texts = [str(x.message) for x in w]
    assert not any("The `dict` method is deprecated" in t for t in texts)


_RUN_MCP = os.getenv("RUN_MCP_TESTS", "").lower() in ("1", "true", "yes")
pytestmark = [] if _RUN_MCP else [__import__("pytest").mark.skip(reason="MCP tests disabled by default; set RUN_MCP_TESTS=1 to enable")]

