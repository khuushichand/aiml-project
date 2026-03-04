from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ("tldw_Server_API.tests.AuthNZ.conftest",)


@pytest.mark.asyncio
async def test_repo_can_crud_acp_profile(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()

    created = await repo.create_acp_profile(
        name="default-dev",
        owner_scope_type="org",
        owner_scope_id=42,
        profile_json='{"sandbox":"strict"}',
        actor_id=1,
    )
    assert created["name"] == "default-dev"

    fetched = await repo.get_acp_profile(int(created["id"]))
    assert fetched is not None
    assert fetched["name"] == "default-dev"
    assert fetched["owner_scope_type"] == "org"
    assert int(fetched["owner_scope_id"]) == 42

    listed = await repo.list_acp_profiles(owner_scope_type="org", owner_scope_id=42)
    assert len(listed) == 1
    assert listed[0]["name"] == "default-dev"

    updated = await repo.update_acp_profile(
        int(created["id"]),
        name="default-prod",
        profile_json='{"sandbox":"relaxed"}',
        is_active=False,
        actor_id=2,
    )
    assert updated is not None
    assert updated["name"] == "default-prod"
    assert updated["is_active"] is False

    deleted = await repo.delete_acp_profile(int(created["id"]))
    assert deleted is True
    missing = await repo.get_acp_profile(int(created["id"]))
    assert missing is None


@pytest.mark.asyncio
async def test_repo_external_server_secret_is_stored_separately(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()

    await repo.upsert_external_server(
        server_id="docs",
        name="Docs",
        transport="stdio",
        config_json='{"cmd":"npx"}',
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        actor_id=1,
    )
    await repo.upsert_external_secret(
        server_id="docs",
        encrypted_blob='{"ciphertext":"abc"}',
        key_hint="cdef",
        actor_id=1,
    )

    row = await repo.get_external_server("docs")
    assert row is not None
    assert row["id"] == "docs"
    assert row["secret_configured"] is True
    assert "encrypted_blob" not in row

    secret = await repo.get_external_secret("docs")
    assert secret is not None
    assert secret["server_id"] == "docs"
    assert secret["encrypted_blob"] == '{"ciphertext":"abc"}'
