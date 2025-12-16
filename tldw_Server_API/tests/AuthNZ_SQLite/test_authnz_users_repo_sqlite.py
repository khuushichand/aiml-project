import os
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_authnz_users_repo_fetch_by_id_sqlite(tmp_path, monkeypatch):
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB

    db_path = tmp_path / "users_repo.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()

    # Use the existing UsersDB abstraction to create a user so the schema
    # details remain centralized.
    users_db = UsersDB(pool)
    await users_db.initialize()
    created = await users_db.create_user(
        username="repo_user",
        email="repo_user@example.com",
        password_hash="hash",
        role="user",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
    )
    user_id = int(created["id"])

    repo = AuthnzUsersRepo(db_pool=pool)
    row = await repo.get_user_by_id(int(user_id))
    assert row is not None
    assert row["username"] == "repo_user"
    assert row["email"] == "repo_user@example.com"
    assert bool(row.get("is_active", True)) is True
