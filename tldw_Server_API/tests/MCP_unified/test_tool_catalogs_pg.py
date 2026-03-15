import os
import asyncio
import pytest

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _admin_headers


def _has_postgres_dependencies() -> bool:
    """Return True when both Postgres test drivers are importable."""
    try:
        import asyncpg  # noqa: F401
    except Exception:
        return False
    try:
        import psycopg  # noqa: F401
    except Exception:
        return False
    return True


pytestmark = [
    pytest.mark.pg_integration,
    pytest.mark.skipif(
        not _has_postgres_dependencies(),
        reason="Postgres dependencies missing (install asyncpg and psycopg[binary])",
    ),
]


def _pg_auth_diag_context() -> str:
    """Return compact diagnostics for Postgres auth triage in assertion messages."""
    auth_mode = os.getenv("AUTH_MODE", "<unset>")
    db_url = os.getenv("DATABASE_URL", "<unset>")
    try:
        from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import (
            PSYCOPG2_AVAILABLE,
        )
    except Exception:
        psycopg_available = "unknown"
    else:
        psycopg_available = str(bool(PSYCOPG2_AVAILABLE))
    return (
        f"AUTH_MODE={auth_mode}; "
        f"DATABASE_URL={db_url}; "
        f"PSYCOPG2_AVAILABLE={psycopg_available}"
    )


@pytest.mark.pg_integration
def test_tool_catalogs_postgres_auth_credential_path_diagnostics(monkeypatch, isolated_test_environment):
    """Diagnostic coverage for Postgres credential validation vs MCP path behavior.

    This test is intentionally focused on triage:
    1) Valid admin JWT must pass an admin preflight endpoint.
    2) Invalid JWT must be rejected with a credential error shape.
    3) Valid admin JWT must not receive 401 on MCP tools listing.
    """
    monkeypatch.setenv("MCP_ENABLE_MEDIA_MODULE", "true")
    monkeypatch.setenv("TEST_MODE", "true")

    from tldw_Server_API.app.core.MCP_unified.config import get_config
    get_config.cache_clear()
    from tldw_Server_API.app.core.MCP_unified.server import reset_mcp_server
    asyncio.run(reset_mcp_server())

    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)
    diag = _pg_auth_diag_context()

    # Preflight: credential path should be healthy for a valid admin JWT.
    r_roles = client.get("/api/v1/admin/roles", headers=headers)
    assert r_roles.status_code == 200, (
        "Postgres credential preflight failed before MCP request. "
        f"{diag}; status={r_roles.status_code}; body={r_roles.text}"
    )

    # Invalid JWT should fail with expected credential semantics.
    bad_headers = {"Authorization": "Bearer not.a.jwt"}
    r_bad = client.get("/api/v1/admin/roles", headers=bad_headers)
    assert r_bad.status_code == 401, (
        "Invalid JWT was not rejected with HTTP 401. "
        f"{diag}; status={r_bad.status_code}; body={r_bad.text}"
    )
    assert (
        "Could not validate credentials" in r_bad.text
        or "Authentication required" in r_bad.text
    ), (
        "Unexpected credential failure payload for invalid JWT. "
        f"{diag}; status={r_bad.status_code}; body={r_bad.text}"
    )

    # MCP list endpoint should not return 401 when the same valid JWT succeeds on preflight.
    r_tools = client.get("/api/v1/mcp/tools", headers=headers)
    assert r_tools.status_code != 401, (
        "MCP tools endpoint returned 401 despite successful auth preflight. "
        f"This points to MCP auth path divergence vs core AuthNZ credential validation. "
        f"{diag}; status={r_tools.status_code}; body={r_tools.text}"
    )


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
    assert r_create.status_code in (200, 201, 409), (
        f"{r_create.text} | {_pg_auth_diag_context()}"
    )

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
    assert r_add.status_code in (200, 201), f"{r_add.text} | {_pg_auth_diag_context()}"

    # List tools filtered by catalog
    r_tools = client.get("/api/v1/mcp/tools", headers=headers, params={"catalog": cat_name})
    assert r_tools.status_code == 200, f"{r_tools.text} | {_pg_auth_diag_context()}"
    data = r_tools.json()
    assert "tools" in data and isinstance(data["tools"], list)
    names = {t.get("name") for t in data["tools"]}
    assert "media.search" in names
    # Ensure a write tool not in catalog isn't shown
    assert "ingest_media" not in names
