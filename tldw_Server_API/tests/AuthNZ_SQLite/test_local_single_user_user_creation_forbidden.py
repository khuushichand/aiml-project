import os

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


@pytest.mark.asyncio
async def test_create_user_forbidden_in_local_single_user_profile(monkeypatch, tmp_path):
    """
    In the local-single-user profile, creating additional users beyond the
    bootstrapped admin must be rejected at the repository/service layer.
    """
    # Configure SQLite AuthNZ DB and local-single-user profile.
    db_path = tmp_path / "users.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("PROFILE", "local-single-user")
    # Ensure we pick up the new settings/env for this test.
    reset_settings()

    repo = await AuthnzUsersRepo.from_pool()

    # Attempt to create a user should fail with DatabaseError.
    with pytest.raises(Exception) as excinfo:
        await repo.create_user(
            username="extra_user",
            email="extra@example.com",
            password_hash="fake-hash",
        )

    assert "forbidden in local-single-user profile" in str(excinfo.value)
