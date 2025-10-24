import os
import pytest
from datetime import datetime, timedelta

from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_refresh_endpoint_blacklists_old_refresh(isolated_test_environment, monkeypatch):
    """Ensure /auth/refresh blacklists the prior refresh token on rotation."""
    client, _db_name = isolated_test_environment

    # Multi-user mode for JWTs
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_SECRET_KEY", "X" * 40)

    # Register and login
    r = client.post(
        "/api/v1/auth/register",
        json={
            "username": "rluser",
            "email": "rluser@example.com",
            "password": "Str0ngP@ssw0rd!",
        },
    )
    assert r.status_code == 200

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "rluser", "password": "Str0ngP@ssw0rd!"},
    )
    assert login.status_code == 200
    first_refresh = login.json()["refresh_token"]

    # Extract JTI of the first refresh
    svc = JWTService()
    old_jti = svc.extract_jti(first_refresh)
    assert old_jti

    # Rotate via endpoint
    rr = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rr.status_code == 200

    # Old refresh JTI should be blacklisted after rotation
    bl = get_token_blacklist()
    assert await bl.is_blacklisted(old_jti) is True
