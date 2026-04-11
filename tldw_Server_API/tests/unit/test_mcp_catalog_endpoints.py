"""Tests for the MCP catalog API endpoints (list and connection test)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import (
    MCPConnectionTestRequest,
    list_mcp_catalog,
    check_mcp_connection,
)
import tldw_Server_API.app.core.MCP_unified.catalog_loader as _catalog_mod
from tldw_Server_API.app.core.MCP_unified.catalog_loader import load_mcp_catalog

pytestmark = pytest.mark.unit

# Path to the real catalog YAML shipped with the project.
_CATALOG_YAML = (
    Path(__file__).resolve().parents[2]
    / "Config_Files"
    / "mcp_server_catalog.yaml"
)


@pytest.fixture(autouse=True)
def _load_real_catalog():
    """Load the real catalog YAML before each test and clear after."""
    _catalog_mod._CATALOG_CACHE = []
    load_mcp_catalog(_CATALOG_YAML)
    yield
    _catalog_mod._CATALOG_CACHE = []


# -- list_mcp_catalog --------------------------------------------------------


@pytest.mark.asyncio
async def test_list_catalog():
    """Calling with no filter should return all catalog entries."""
    result = await list_mcp_catalog()

    assert isinstance(result, list)
    assert len(result) >= 1
    keys = {e.key for e in result}
    # The real YAML should contain at least these well-known entries.
    assert "github" in keys
    assert "arxiv" in keys


@pytest.mark.asyncio
async def test_list_catalog_with_archetype_filter():
    """Filtering by archetype_key should narrow the returned entries."""
    all_entries = await list_mcp_catalog()

    filtered = await list_mcp_catalog(archetype_key="research_assistant")

    assert isinstance(filtered, list)
    assert len(filtered) >= 1
    # Filtered set must be a subset of the full catalog.
    assert len(filtered) <= len(all_entries)
    # Every returned entry must list the requested archetype.
    for entry in filtered:
        assert "research_assistant" in entry.suggested_for


@pytest.mark.asyncio
async def test_list_catalog_unknown_archetype_returns_empty():
    """An archetype key that no entry maps to should yield an empty list."""
    result = await list_mcp_catalog(archetype_key="nonexistent_archetype_xyz")

    assert result == []


# -- test_mcp_connection -----------------------------------------------------


@pytest.mark.asyncio
async def test_connection_unreachable():
    """Connecting to a port that is almost certainly closed should fail gracefully."""
    req = MCPConnectionTestRequest(url="http://127.0.0.1:1")

    resp = await check_mcp_connection(req)

    assert resp.reachable is False
    assert resp.error is not None
    assert isinstance(resp.error, str)
    assert resp.tools_discovered == []
