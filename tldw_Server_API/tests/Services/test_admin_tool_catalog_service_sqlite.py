from __future__ import annotations

import os
import time
import pytest

from tldw_Server_API.app.services import admin_tool_catalog_service as svc


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
        with pytest.raises(ValueError):
            await svc.create_tool_catalog(db, name="uniquecat", description=None, org_id=None, team_id=None, is_active=True)
