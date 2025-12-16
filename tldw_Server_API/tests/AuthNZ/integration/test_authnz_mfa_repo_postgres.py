from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.mfa_repo import AuthnzMfaRepo
from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_mfa_repo_basic_postgres(test_db_pool):
    """AuthnzMfaRepo should update and read MFA fields on Postgres."""
    pool = test_db_pool

    # Create a user via UsersDB abstraction to mirror production code paths
    users_db = UsersDB(pool)
    await users_db.initialize()
    created_user = await users_db.create_user(
        username="pg-mfa-user",
        email="pg-mfa-user@example.com",
        password_hash="hashed-password",
        role="user",
        is_active=True,
        is_superuser=False,
    )
    user_id = int(created_user["id"])
    assert user_id is not None

    repo = AuthnzMfaRepo(pool)
    now = datetime.now(timezone.utc)

    await repo.set_mfa_config(
        user_id=int(user_id),
        encrypted_secret="enc-secret-pg",
        backup_codes_json='["codeA","codeB"]',
        updated_at=now,
    )

    encrypted = await repo.get_encrypted_totp_secret(int(user_id))
    assert encrypted == "enc-secret-pg"

    status_row = await repo.get_mfa_status_row(int(user_id))
    assert status_row is not None
    assert bool(status_row.get("two_factor_enabled"))
    assert bool(status_row.get("has_secret"))
    assert bool(status_row.get("has_backup_codes"))

    raw_backup = await repo.get_backup_codes_json(int(user_id))
    assert raw_backup == '["codeA","codeB"]'

    await repo.update_backup_codes_json(
        user_id=int(user_id),
        backup_codes_json='["codeB"]',
    )
    raw_backup_after = await repo.get_backup_codes_json(int(user_id))
    assert raw_backup_after == '["codeB"]'

    await repo.clear_mfa_config(user_id=int(user_id), updated_at=now)

    encrypted_after = await repo.get_encrypted_totp_secret(int(user_id))
    assert encrypted_after is None

    status_after = await repo.get_mfa_status_row(int(user_id))
    assert status_after is not None
    assert not bool(status_after.get("two_factor_enabled"))
    assert not bool(status_after.get("has_secret"))
    assert not bool(status_after.get("has_backup_codes"))
