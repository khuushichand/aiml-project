import os
import asyncio
import pytest

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _admin_headers


@pytest.mark.pg_integration
def test_tool_catalogs_postgres_list_filter(monkeypatch, isolated_test_environment):
    monkeypatch.setenv("MCP_ENABLE_MEDIA_MODULE", "true")
    monkeypatch.setenv("TEST_MODE", "true")

    # Ensure MCP config/server pick up fresh env toggles (media module)
    from tldw_Server_API.app.core.MCP_unified.config import get_config
    get_config.cache_clear()
    from tldw_Server_API.app.core.MCP_unified.server import reset_mcp_server
    asyncio.run(reset_mcp_server())

    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    # Create a unique catalog name and add an entry
    cat_name = f"pg-cat-{os.getpid()}"
    r_create = client.post(
        "/api/v1/admin/mcp/tool_catalogs",
        headers=headers,
        json={"name": cat_name, "description": "pg demo", "is_active": True},
    )
    assert r_create.status_code in (200, 201, 409), r_create.text

    # Get catalog id
    if r_create.status_code == 201:
        catalog_id = r_create.json()["id"]
    else:
        r_list = client.get("/api/v1/admin/mcp/tool_catalogs", headers=headers, params={"limit": 100})
        assert r_list.status_code == 200
        catalog_id = next(c["id"] for c in r_list.json() if c["name"] == cat_name)

    # Add media.search tool entry
    r_add = client.post(
        f"/api/v1/admin/mcp/tool_catalogs/{catalog_id}/entries",
        headers=headers,
        json={"tool_name": "media.search"},
    )
    assert r_add.status_code in (200, 201), r_add.text

    # List tools filtered by catalog
    r_tools = client.get("/api/v1/mcp/tools", headers=headers, params={"catalog": cat_name})
    assert r_tools.status_code == 200, r_tools.text
    data = r_tools.json()
    assert "tools" in data and isinstance(data["tools"], list)
    names = {t.get("name") for t in data["tools"]}
    assert "media.search" in names
    # Ensure a write tool not in catalog isn't shown
    assert "ingest_media" not in names
