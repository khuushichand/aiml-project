import os
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_single_user_bootstrap_creates_admin_user_and_primary_key(tmp_path):
    # Configure single-user SQLite AuthNZ
    db_path = tmp_path / "users.db"
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["SINGLE_USER_API_KEY"] = "test_single_user_primary_key_123"

    # Reset AuthNZ singletons and ensure core tables exist
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    # Run the single-user bootstrap helper twice to assert idempotency
    from tldw_Server_API.app.core.AuthNZ.initialize import bootstrap_single_user_profile

    ok_first = await bootstrap_single_user_profile()
    ok_second = await bootstrap_single_user_profile()
    assert ok_first is True
    assert ok_second is True

    # Verify the single-user admin row exists with the fixed ID
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    single_user_id = settings.SINGLE_USER_FIXED_ID

    user_rows = await pool.fetch(
        "SELECT id, username, role, is_active, is_verified FROM users WHERE id = ?",
        single_user_id,
    )
    assert len(user_rows) == 1
    user = user_rows[0]
    assert int(user["id"]) == single_user_id
    assert user["username"] == "single_user"
    assert user["role"] == "admin"
    assert int(user["is_active"]) == 1
    assert int(user["is_verified"]) == 1

    # Verify a non-virtual primary API key row exists for this user
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager

    manager = APIKeyManager()
    await manager.initialize()
    key_hash = manager.hash_api_key(settings.SINGLE_USER_API_KEY)

    rows = await pool.fetch(
        "SELECT user_id, key_hash, scope, status, is_virtual FROM api_keys WHERE key_hash = ?",
        key_hash,
    )
    assert len(rows) == 1
    row = rows[0]
    assert int(row["user_id"]) == single_user_id
    assert row["key_hash"] == key_hash
    assert row["scope"] == "admin"
    assert row["status"] == "active"
    # SQLite uses 0/1 for booleans
    assert int(row["is_virtual"]) == 0

