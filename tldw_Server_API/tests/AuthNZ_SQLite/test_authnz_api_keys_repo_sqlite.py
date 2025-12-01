import uuid

import pytest

pytest_plugins = ("tldw_Server_API.tests.AuthNZ.conftest",)


@pytest.mark.asyncio
async def test_authnz_api_keys_repo_fetch_key_limits_sqlite(isolated_test_environment):
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager

    _client, _db_name = isolated_test_environment
    pool = await get_db_pool()

    # Ensure core AuthNZ tables exist via UsersDB and APIKeyManager so we
    # reuse centralized schema logic.
    users_db = UsersDB(pool)
    await users_db.initialize()
    created_user = await users_db.create_user(
        username="vk_repo_user",
        email="vk_repo_user@example.com",
        password_hash="hash",
        role="user",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
        uuid_value=uuid.uuid4(),
    )
    user_id = int(created_user["id"])

    mgr = APIKeyManager(pool)
    await mgr.initialize()
    vk = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk_repo_key",
        budget_day_tokens=123,
        budget_month_usd=4.56,
    )
    key_id = int(vk["id"])

    repo = AuthnzApiKeysRepo(db_pool=pool)
    row = await repo.fetch_key_limits(key_id)

    assert row is not None
    assert int(row["id"]) == key_id
    assert bool(row.get("is_virtual")) is True
    assert int(row.get("llm_budget_day_tokens") or 0) == 123
    assert pytest.approx(float(row.get("llm_budget_month_usd") or 0.0), rel=1e-6) == 4.56


@pytest.mark.asyncio
async def test_authnz_api_keys_repo_rotation_and_revoke_sqlite(isolated_test_environment):
    """AuthnzApiKeysRepo mark_rotated / revoke_api_key_for_user should work on SQLite."""
    from datetime import datetime

    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager, APIKeyStatus

    _client, _db_name = isolated_test_environment
    pool = await get_db_pool()

    # Ensure user and tables exist
    users_db = UsersDB(pool)
    await users_db.initialize()
    created_user = await users_db.create_user(
        username="repo_rot_user",
        email="repo_rot_user@example.com",
        password_hash="hash",
        role="user",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
        uuid_value=uuid.uuid4(),
    )
    user_id = int(created_user["id"])

    mgr = APIKeyManager(pool)
    await mgr.initialize()

    # Create two API keys for rotation tests
    first = await mgr.create_api_key(user_id=user_id, name="first")
    second = await mgr.create_api_key(user_id=user_id, name="second")
    first_id = int(first["id"])
    second_id = int(second["id"])

    repo = AuthnzApiKeysRepo(db_pool=pool)

    # mark_rotated: first -> second
    await repo.mark_rotated(
        old_key_id=first_id,
        new_key_id=second_id,
        rotated_status=APIKeyStatus.ROTATED.value,
        reason="Rotation test",
        revoked_at=datetime.utcnow(),
    )

    row_first = await pool.fetchrow(
        "SELECT status, rotated_to, revoke_reason FROM api_keys WHERE id = ?",
        first_id,
    )
    row_second = await pool.fetchrow(
        "SELECT rotated_from FROM api_keys WHERE id = ?",
        second_id,
    )
    assert row_first is not None
    assert row_second is not None
    assert row_first["status"] == APIKeyStatus.ROTATED.value
    assert int(row_first["rotated_to"]) == second_id
    assert row_first["revoke_reason"] == "Rotation test"
    assert int(row_second["rotated_from"]) == first_id

    # revoke_api_key_for_user: revoke second key
    revoked = await repo.revoke_api_key_for_user(
        key_id=second_id,
        user_id=user_id,
        revoked_status=APIKeyStatus.REVOKED.value,
        active_status=APIKeyStatus.ACTIVE.value,
        reason="Unit revoke",
        revoked_at=datetime.utcnow(),
    )
    assert revoked is True

    row_second_after = await pool.fetchrow(
        "SELECT status, revoked_by, revoke_reason FROM api_keys WHERE id = ?",
        second_id,
    )
    assert row_second_after is not None
    assert row_second_after["status"] == APIKeyStatus.REVOKED.value
    assert int(row_second_after["revoked_by"]) == user_id
    assert row_second_after["revoke_reason"] == "Unit revoke"
