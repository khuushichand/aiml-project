from __future__ import annotations

import os
import time
import pytest

from tldw_Server_API.app.services import admin_tool_catalog_service as svc
from tldw_Server_API.app.core.exceptions import ToolCatalogConflictError


def _setup_sqlite_env(tmp_name: str = "tool_catalog_service_test.db") -> None:
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key"
    os.environ["DATABASE_URL"] = f"sqlite:///./Databases/{tmp_name}"


@pytest.mark.asyncio
async def test_admin_tool_catalog_sqlite_roundtrip():
    _setup_sqlite_env(tmp_name=f"users_tool_catalog_{int(time.time())}.db")

    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool

    # Fresh pool to pick up env overrides and ensure migrations (including tool catalogs) run
    await reset_db_pool()
    pool = await get_db_pool()

    # Use a transaction shim for the service fns
    async with pool.transaction() as db:
        # Create a global-scope catalog (no org/team)
        created = await svc.create_tool_catalog(
            db,
            name="demo-catalog",
            description="unit test",
            org_id=None,
            team_id=None,
            is_active=True,
        )
        assert int(created["id"]) > 0
        assert created["name"] == "demo-catalog"
        assert created["description"] == "unit test"
        assert created["org_id"] is None
        assert created["team_id"] is None
        assert bool(created["is_active"]) is True

        cat_id = int(created["id"])

        # List catalogs: should include the one we just created
        rows = await svc.list_tool_catalogs(db, org_id=None, team_id=None, limit=10, offset=0)
        assert any(int(r["id"]) == cat_id for r in rows)

        # Add entries, ensure idempotency via unique(catalog_id, tool_name)
        e1 = await svc.add_tool_catalog_entry(db, cat_id, "media.search", None)
        assert e1["catalog_id"] == cat_id and e1["tool_name"] == "media.search"
        e1_repeat = await svc.add_tool_catalog_entry(db, cat_id, "media.search", None)
        assert e1_repeat["catalog_id"] == cat_id and e1_repeat["tool_name"] == "media.search"

        e2 = await svc.add_tool_catalog_entry(db, cat_id, "ingest_media", "ingestion")
        assert e2["catalog_id"] == cat_id and e2["tool_name"] == "ingest_media" and e2["module_id"] == "ingestion"

        # List entries
        entries = await svc.list_tool_catalog_entries(db, cat_id)
        names = {r["tool_name"] for r in entries}
        assert {"media.search", "ingest_media"}.issubset(names)

        # Delete single entry
        await svc.delete_tool_catalog_entry(db, cat_id, "media.search")
        entries2 = await svc.list_tool_catalog_entries(db, cat_id)
        names2 = {r["tool_name"] for r in entries2}
        assert "media.search" not in names2 and "ingest_media" in names2

        # Deleting catalog should cascade-delete entries via FK (SQLite PRAGMA foreign_keys=ON in transaction)
        await svc.delete_tool_catalog(db, cat_id)
        # Verify catalog no longer appears
        rows2 = await svc.list_tool_catalogs(db, org_id=None, team_id=None, limit=100, offset=0)
        assert all(int(r["id"]) != cat_id for r in rows2)


@pytest.mark.asyncio
async def test_admin_tool_catalog_sqlite_duplicate_guard():
    _setup_sqlite_env(tmp_name=f"users_tool_catalog_dupe_{int(time.time())}.db")

    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool

    await reset_db_pool()
    pool = await get_db_pool()

    async with pool.transaction() as db:
        _ = await svc.create_tool_catalog(db, name="uniquecat", description=None, org_id=None, team_id=None, is_active=True)
        with pytest.raises(ToolCatalogConflictError):
            await svc.create_tool_catalog(db, name="uniquecat", description=None, org_id=None, team_id=None, is_active=True)


@pytest.mark.asyncio
async def test_list_visible_tool_catalogs_sqlite_scope_filters():
    _setup_sqlite_env(tmp_name=f"users_tool_catalog_visible_{int(time.time())}.db")

    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool

    await reset_db_pool()
    pool = await get_db_pool()

    async with pool.transaction() as db:
        # Ensure org/team rows exist for FK-backed catalog scope checks.
        await db.execute(
            "INSERT OR IGNORE INTO organizations (id, name, slug, owner_user_id, is_active) VALUES (?, ?, ?, NULL, 1)",
            (701, "org-visible", "org-visible"),
        )
        await db.execute(
            "INSERT OR IGNORE INTO teams (id, org_id, name, slug, description, is_active) VALUES (?, ?, ?, ?, NULL, 1)",
            (801, 701, "team-visible", "team-visible"),
        )

        global_cat = await svc.create_tool_catalog(
            db,
            name="global-visible-cat",
            description=None,
            org_id=None,
            team_id=None,
            is_active=True,
        )
        org_cat = await svc.create_tool_catalog(
            db,
            name="org-visible-cat",
            description=None,
            org_id=701,
            team_id=None,
            is_active=True,
        )
        team_cat = await svc.create_tool_catalog(
            db,
            name="team-visible-cat",
            description=None,
            org_id=None,
            team_id=801,
            is_active=True,
        )

        visible_all = await svc.list_visible_tool_catalogs(
            db,
            scope_norm="all",
            admin_all=True,
            org_ids=set(),
            team_ids=set(),
        )
        visible_ids = {int(row["id"]) for row in visible_all}
        assert int(global_cat["id"]) in visible_ids
        assert int(org_cat["id"]) in visible_ids
        assert int(team_cat["id"]) in visible_ids

        visible_org = await svc.list_visible_tool_catalogs(
            db,
            scope_norm="org",
            admin_all=False,
            org_ids={701},
            team_ids=set(),
        )
        assert {int(row["id"]) for row in visible_org} == {int(org_cat["id"])}

        visible_team = await svc.list_visible_tool_catalogs(
            db,
            scope_norm="team",
            admin_all=False,
            org_ids=set(),
            team_ids={801},
        )
        assert {int(row["id"]) for row in visible_team} == {int(team_cat["id"])}
