from pathlib import Path
import sqlite3

import pytest

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.settings import Settings
from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB, DuplicateUserError


@pytest.mark.asyncio
async def test_users_db_returns_boolean_flags_under_sqlite(tmp_path: Path):
    db_file = tmp_path / "users.db"
    if db_file.exists():
        db_file.unlink()

    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                metadata TEXT,
                is_active INTEGER DEFAULT 1,
                is_superuser INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                email_verified INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                storage_quota_mb INTEGER DEFAULT 5120,
                storage_used_mb INTEGER DEFAULT 0
            )
            """
        )

    settings = Settings(
        AUTH_MODE="single_user",
        DATABASE_URL=f"sqlite:///{db_file}",
    )

    pool = DatabasePool(settings)
    try:
        users_db = UsersDB(db_pool=pool)
        await users_db.initialize()

        created = await users_db.create_user(
            username="flagcheck",
            email="flag@example.com",
            password_hash="hashed-password",
            is_active=True,
            is_superuser=False,
        )

        assert created["uuid"]
        assert isinstance(created["uuid"], str)

        for field in ("is_active", "is_superuser", "email_verified"):
            assert isinstance(created[field], bool), f"{field} should be boolean on create"

        fetched = await users_db.get_user_by_username("flagcheck")
        assert fetched and fetched["uuid"]
        for field in ("is_active", "is_superuser", "email_verified"):
            assert isinstance(fetched[field], bool), f"{field} should be boolean via get_user_by_username"

        listed = await users_db.list_users()
        assert listed, "Expected at least one user from list_users"
        for field in ("is_active", "is_superuser", "email_verified"):
            assert isinstance(listed[0][field], bool), f"{field} should be boolean in list_users results"
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_create_user_duplicate_race_surfaces_duplicate_error(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "users_race.db"
    settings = Settings(
        AUTH_MODE="single_user",
        DATABASE_URL=f"sqlite:///{db_file}",
    )

    pool = DatabasePool(settings)
    try:
        users_db = UsersDB(db_pool=pool)
        await users_db.initialize()

        async def _return_none(self, *args, **kwargs):  # noqa: ARG001
            return None

        monkeypatch.setattr(UsersDB, "get_user_by_username", _return_none)
        monkeypatch.setattr(UsersDB, "get_user_by_email", _return_none)

        await users_db.create_user(
            username="race",
            email="race@example.com",
            password_hash="pw",
        )

        with pytest.raises(DuplicateUserError):
            await users_db.create_user(
                username="race",
                email="race@example.com",
                password_hash="pw",
            )
    finally:
        await pool.close()
