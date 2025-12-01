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
