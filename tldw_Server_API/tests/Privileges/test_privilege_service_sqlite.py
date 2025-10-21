from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.PrivilegeMaps.service import PrivilegeMapService


async def _fetch_id(pool, query: str, value: str) -> int:
    result = await pool.fetchval(query, (value,))
    assert result is not None, f"Expected ID for query {query} with value {value}"
    return int(result)


@pytest.mark.asyncio
async def test_privilege_service_honors_authnz_role_mappings(tmp_path, monkeypatch):
    db_path = tmp_path / "authnz.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-priv-service-123456")
    monkeypatch.setenv("TEST_MODE", "true")

    # Reset global singletons so we pick up the test configuration.
    reset_settings()
    await reset_db_pool()

    # Ensure migrations run so privilege_snapshots and RBAC tables exist ahead of service usage.
    ensure_authnz_tables(Path(db_path))

    pool = await get_db_pool()

    # Seed roles, permissions, users, and memberships.
    async with pool.transaction() as conn:
        for role_name, is_system in [
            ("admin", 1),
            ("media_manager", 0),
            ("analyst", 0),
            ("viewer", 0),
            ("researcher", 0),
        ]:
            await conn.execute(
                "INSERT OR IGNORE INTO roles (name, description, is_system) VALUES (?, ?, ?)",
                (role_name, f"{role_name} role", is_system),
            )

        for perm_name in [
            "rag.search",
            "media.catalog.view",
            "feature_flag:media_ingest_beta",
        ]:
            await conn.execute(
                "INSERT OR IGNORE INTO permissions (name, description, category) VALUES (?, ?, ?)",
                (perm_name, f"{perm_name} permission", "test"),
            )

        for username, email, primary_role in [
            ("admin-user", "admin@example.com", "admin"),
            ("media-manager", "media@example.com", "media_manager"),
            ("analyst-user", "analyst@example.com", "analyst"),
            ("researcher-user", "researcher@example.com", "researcher"),
        ]:
            await conn.execute(
                """
                INSERT INTO users (username, email, password_hash, is_active, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, email, "hashed", 1, primary_role),
            )

    admin_id = await _fetch_id(pool, "SELECT id FROM users WHERE username = ?", "admin-user")
    media_manager_id = await _fetch_id(pool, "SELECT id FROM users WHERE username = ?", "media-manager")
    analyst_id = await _fetch_id(pool, "SELECT id FROM users WHERE username = ?", "analyst-user")
    researcher_id = await _fetch_id(pool, "SELECT id FROM users WHERE username = ?", "researcher-user")

    role_ids = {}
    for role_name in ["admin", "media_manager", "analyst", "viewer", "researcher"]:
        role_ids[role_name] = await _fetch_id(pool, "SELECT id FROM roles WHERE name = ?", role_name)

    permission_ids = {}
    for perm_name in ["rag.search", "media.catalog.view", "feature_flag:media_ingest_beta"]:
        permission_ids[perm_name] = await _fetch_id(pool, "SELECT id FROM permissions WHERE name = ?", perm_name)

    async with pool.transaction() as conn:
        # Assign primary roles explicitly via mapping table.
        await conn.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (admin_id, role_ids["admin"]),
        )
        await conn.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (media_manager_id, role_ids["media_manager"]),
        )
        await conn.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (analyst_id, role_ids["analyst"]),
        )
        await conn.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (researcher_id, role_ids["researcher"]),
        )

        # researcher gains rag.search through RBAC role permissions
        await conn.execute(
            "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
            (role_ids["researcher"], permission_ids["rag.search"]),
        )

        # Direct user override: researcher gets media ingest beta flag despite role not being allowed.
        await conn.execute(
            """
            INSERT OR REPLACE INTO user_permissions (user_id, permission_id, granted)
            VALUES (?, ?, 1)
            """,
            (researcher_id, permission_ids["feature_flag:media_ingest_beta"]),
        )

    # Create basic organization/team structure for membership lookups.
    async with pool.transaction() as conn:
        await conn.execute(
            "INSERT INTO organizations (name, slug, owner_user_id) VALUES (?, ?, ?)",
            ("Acme Corp", "acme-corp", admin_id),
        )

    org_id = await _fetch_id(pool, "SELECT id FROM organizations WHERE slug = ?", "acme-corp")

    async with pool.transaction() as conn:
        for user_id in [admin_id, media_manager_id, analyst_id, researcher_id]:
            await conn.execute(
                """
                INSERT OR IGNORE INTO org_members (org_id, user_id, role, status)
                VALUES (?, ?, ?, ?)
                """,
                (org_id, user_id, "member", "active"),
            )

        await conn.execute(
            """
            INSERT INTO teams (org_id, name, slug, is_active)
            VALUES (?, ?, ?, 1)
            """,
            (org_id, "Ingest Ops", "ingest-ops",),
        )

    team_id = await _fetch_id(pool, "SELECT id FROM teams WHERE slug = ?", "ingest-ops")

    async with pool.transaction() as conn:
        for user_id in [media_manager_id, researcher_id]:
            await conn.execute(
                """
                INSERT OR REPLACE INTO team_members (team_id, user_id, role, status)
                VALUES (?, ?, ?, ?)
                """,
                (team_id, user_id, "member", "active"),
            )

    service = PrivilegeMapService()

    users = await service._fetch_users()
    user_map = {user["username"]: user for user in users}

    all_scopes = {scope.id for scope in service.catalog.scopes}
    assert set(user_map["admin-user"]["allowed_scopes"]) == all_scopes
    assert "media_ingest_beta" in user_map["admin-user"]["feature_flags"]

    assert "media.ingest" in user_map["media-manager"]["allowed_scopes"]
    # media_manager gains feature flag through catalog allowed_roles
    assert "media_ingest_beta" in user_map["media-manager"]["feature_flags"]

    assert "rag.search" in user_map["researcher-user"]["allowed_scopes"]
    # Direct permission enables feature flag even though role is not whitelisted
    assert "media_ingest_beta" in user_map["researcher-user"]["feature_flags"]

    summary = await service.get_org_summary(group_by="role", include_trends=False, since=None)
    bucket_map = {bucket["key"]: bucket for bucket in summary["buckets"]}
    assert bucket_map["researcher"]["scopes"] >= 1
    assert bucket_map["media_manager"]["scopes"] >= 1

    team_detail = await service.get_team_detail(
        team_id=str(team_id),
        page=1,
        page_size=50,
        resource=None,
        dependency=None,
        role_filter=None,
    )
    ingest_rows = [
        row
        for row in team_detail["items"]
        if row["user_name"] == "media-manager" and row["privilege_scope_id"] == "media.ingest"
    ]
    assert ingest_rows and ingest_rows[0]["status"] == "allowed"

    await reset_db_pool()
    reset_settings()
