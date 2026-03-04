from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_mcp_hub_tables_exist_after_authnz_migrations_sqlite(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    rows = await pool.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    names = {str(row["name"]) for row in rows}

    assert "mcp_acp_profiles" in names
    assert "mcp_external_servers" in names
    assert "mcp_external_server_secrets" in names

