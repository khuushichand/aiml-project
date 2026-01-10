import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import auth as auth_mod
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


@pytest.mark.asyncio
async def test_http_registration_forbidden_in_local_single_user_profile(monkeypatch, tmp_path):
    """
    HTTP-level guard: /api/v1/auth/register must return 403 and not create
    additional users when PROFILE=local-single-user and AUTH_MODE=single_user.
    """
    db_path = tmp_path / "users.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("PROFILE", "local-single-user")
    reset_settings()

    # Build a small app with only the auth router mounted.
    app = FastAPI()
    app.include_router(auth_mod.router, prefix="/api/v1")

    # Stub registration_service so we can assert it is not invoked.
    class _FakeRegistrationService:
        def __init__(self):
                     self.called = False

        async def register_user(self, *args, **kwargs):
            self.called = True
            raise AssertionError("register_user should not be called in local-single-user profile")

    fake_service = _FakeRegistrationService()

    async def _fake_get_registration_service_dep():
        return fake_service

    app.dependency_overrides[auth_deps.get_registration_service_dep] = _fake_get_registration_service_dep

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": "extra", "email": "extra@example.com", "password": "Extra@Pass#2024!"},
        )

    assert resp.status_code == 403
    detail = resp.json().get("detail", "")
    assert "not allowed in local-single-user profile" in detail.lower()
    assert fake_service.called is False
