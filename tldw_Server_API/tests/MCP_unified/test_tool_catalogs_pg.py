import os
import pytest


@pytest.mark.pg_integration
def test_tool_catalogs_postgres_list_filter(monkeypatch):
    # Build Postgres DSN from CI env
    host = os.getenv("POSTGRES_TEST_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_TEST_PORT", "5432")
    db = os.getenv("POSTGRES_TEST_DB", "tldw_content")
    user = os.getenv("POSTGRES_TEST_USER", "tldw")
    pwd = os.getenv("POSTGRES_TEST_PASSWORD", "tldw")
    dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

    # Configure server for PG AuthNZ DB, but keep single_user mode for simple auth
    os.environ["DATABASE_URL"] = dsn
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["TEST_MODE"] = "true"
    os.environ.setdefault("SINGLE_USER_API_KEY", "CHANGE_ME_TO_SECURE_API_KEY")
    os.environ["MCP_ENABLE_MEDIA_MODULE"] = "true"

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.main import app

    client = TestClient(app)

    # Use configured test API key
    api_key = os.getenv("SINGLE_USER_TEST_API_KEY", "test-api-key-12345")
    headers = {"X-API-KEY": api_key}

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

