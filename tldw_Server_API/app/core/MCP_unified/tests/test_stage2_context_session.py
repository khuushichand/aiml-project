"""
Stage 2 plumbing tests: RequestContext db_paths and safe config parsing.
Tests are skipped by default; enable with RUN_MCP_TESTS=1.
"""

import os
import pytest

_os = os
_os.environ.setdefault("RUN_MCP_TESTS", "0")

from typing import Dict, Any

from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
from tldw_Server_API.app.core.MCP_unified.server import MCPServer


_RUN_MCP = os.getenv("RUN_MCP_TESTS", "").lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(not _RUN_MCP, reason="MCP tests disabled by default; set RUN_MCP_TESTS=1 to enable")


def test_request_context_db_paths_derivation():
    ctx = RequestContext(request_id="rx1", user_id="1", client_id="test")
    # Ensure expected keys exist when user_id parses to int
    assert isinstance(ctx.db_paths, dict)
    for key in ("media", "chacha", "prompts", "audit", "evaluations"):
        assert key in ctx.db_paths
        assert isinstance(ctx.db_paths[key], str)


def test_safe_config_merge_allowlist_and_clamp():
    srv = MCPServer()
    base: Dict[str, Any] = {"snippet_length": 300, "chars_per_token": 4}
    incoming: Dict[str, Any] = {
        "snippet_length": 9999,  # should clamp
        "chars_per_token": 0,    # should clamp to >=1
        "aliasMode": True,
        "compactShape": False,
        "order_by": "recent",
        "maxSessionUris": 999999,
        "ignored": "x",
    }
    merged = srv._merge_safe_config(base, incoming)
    assert merged["snippet_length"] <= 2000
    assert merged["chars_per_token"] >= 1
    assert merged["aliasMode"] is True
    assert merged["compactShape"] is False
    assert merged["order_by"] == "recent"
    assert merged["maxSessionUris"] <= 5000
    assert "ignored" not in merged

