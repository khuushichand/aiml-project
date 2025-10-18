"""
HTTP batch endpoint tests for MCP Unified.
"""

import os
import pytest
import os as _os

_os.environ.setdefault("TEST_MODE", "true")
_os.environ.setdefault("ENABLE_TRACING", "false")
_os.environ.setdefault("OTEL_METRICS_EXPORTER", "console")
_os.environ.setdefault("MCP_WS_AUTH_REQUIRED", "false")
_os.environ.setdefault("MCP_ALLOWED_IPS", "")

from fastapi.testclient import TestClient
from tldw_Server_API.app.main import app


client = TestClient(app)


def test_http_batch_initialize_and_ping():
    payload = [
        {"jsonrpc": "2.0", "method": "initialize", "params": {"clientInfo": {"name": "HTTP Batch"}}, "id": 1},
        {"jsonrpc": "2.0", "method": "ping", "id": 2},
    ]
    resp = client.post("/api/v1/mcp/request/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    ids = sorted(item.get("id") for item in data)
    assert ids == [1, 2]
    for item in data:
        assert item.get("jsonrpc") == "2.0"
        assert item.get("error") is None
