import os
import asyncio
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables


client = TestClient(app)


def _run(coro):
    return asyncio.run(coro)


def test_tools_execute_unauth_401():
    payload = {"tool_name": "echo", "arguments": {"message": "hi"}}
    r = client.post("/api/v1/mcp/tools/execute", json=payload)
    assert r.status_code == 401, r.text


def test_tools_execute_with_bearer_token_no_permission_403():
    # Use MCP JWT (auto-seeded secret) to authenticate
    mgr = get_jwt_manager()
    token = mgr.create_access_token(subject="42", username="tester")

    payload = {"tool_name": "echo", "arguments": {"message": "hi"}}
    r = client.post(
        "/api/v1/mcp/tools/execute",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
    data = r.json()
    assert "detail" in data and isinstance(data["detail"], dict)
    hint = data["detail"].get("hint", "")
    # Should recommend assigning tools.execute:<tool> or wildcard
    assert "tools.execute:echo" in hint or "tools.execute:*" in hint


def test_tools_execute_with_api_key_and_role_permission_allows_200(tmp_path):
    # Point AuthNZ DB to a fresh SQLite file
    db_file = tmp_path / "mcp_allow.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    os.environ["AUTH_MODE"] = "single_user"
    # Reset settings and DB pool to pick up new config
    _run(reset_db_pool())
    reset_settings()

    # Run AuthNZ migrations (creates RBAC tables and expands api_keys schema)
    ensure_authnz_tables(Path(db_file))
    # Insert a user directly (compatible with base SQLite schema)
    pool = _run(get_db_pool())
    async def _insert_user():
        async with pool.transaction() as conn:
            if hasattr(conn, 'fetchval'):
                uid = await conn.fetchval(
                    "INSERT INTO users (username, email, password_hash, is_active, role, is_verified) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                    "permit_user", "permit@test.local", "dummyhash", True, "user", True
                )
                return uid
            else:
                cur = await conn.execute(
                    "INSERT INTO users (username, email, password_hash, is_active, role, is_verified) VALUES (?,?,?,?,?,?)",
                    ("permit_user", "permit@test.local", "dummyhash", 1, "user", 1)
                )
                uid = cur.lastrowid
                await conn.commit()
                return uid
    user_id = _run(_insert_user())
    api_mgr = _run(get_api_key_manager())
    key_data = _run(api_mgr.create_api_key(user_id=user_id, name="permit-key"))
    api_key = key_data["key"]

    # Insert wildcard tools permission, role, and assign to user
    pool = _run(get_db_pool())

    async def _seed():
        async with pool.transaction() as conn:
            # Create RBAC core tables if they don't exist
            if not hasattr(conn, 'fetchval'):
                await conn.execute("CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, is_system INTEGER DEFAULT 0)")
                await conn.execute("CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, category TEXT)")
                await conn.execute("CREATE TABLE IF NOT EXISTS role_permissions (role_id INTEGER NOT NULL, permission_id INTEGER NOT NULL, PRIMARY KEY(role_id, permission_id))")
                await conn.execute("CREATE TABLE IF NOT EXISTS user_roles (user_id INTEGER NOT NULL, role_id INTEGER NOT NULL, PRIMARY KEY(user_id, role_id))")
            # Create permission if missing
            if hasattr(conn, 'fetchval'):
                pid = await conn.fetchval(
                    "INSERT INTO permissions (name, description, category) VALUES ($1,$2,$3) ON CONFLICT (name) DO NOTHING RETURNING id",
                    "tools.execute:*", "Wildcard tool execution", "tools"
                )
                if not pid:
                    pid = await conn.fetchval("SELECT id FROM permissions WHERE name = $1", "tools.execute:*")
                rid = await conn.fetchval(
                    "INSERT INTO roles (name, description, is_system) VALUES ($1,$2,$3) RETURNING id",
                    "tool_role", "Role for tool exec", False
                )
                await conn.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES ($1,$2) ON CONFLICT DO NOTHING", rid, pid)
                await conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES ($1,$2) ON CONFLICT DO NOTHING", user_id, rid)
            else:
                # SQLite
                cur = await conn.execute("SELECT id FROM permissions WHERE name = ?", ("tools.execute:*",))
                row = await cur.fetchone()
                if row:
                    pid = row[0]
                else:
                    cur = await conn.execute(
                        "INSERT INTO permissions (name, description, category) VALUES (?,?,?)",
                        ("tools.execute:*", "Wildcard tool execution", "tools")
                    )
                    pid = cur.lastrowid
                cur = await conn.execute(
                    "INSERT INTO roles (name, description, is_system) VALUES (?,?,?)",
                    ("tool_role", "Role for tool exec", 0)
                )
                rid = cur.lastrowid
                await conn.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?,?)", (rid, pid))
                await conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?,?)", (user_id, rid))
                await conn.commit()

    _run(_seed())

    # Call tools/execute with API key
    payload = {"tool_name": "echo", "arguments": {"message": "hello"}}
    r = client.post(
        "/api/v1/mcp/tools/execute",
        json=payload,
        headers={"X-API-KEY": api_key},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"] == "hello"
