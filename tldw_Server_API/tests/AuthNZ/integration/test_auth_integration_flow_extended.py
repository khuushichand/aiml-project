import types
import sys
import importlib
import json

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_reset_password_integration_success(monkeypatch):
    """End-to-end reset-password via dependency overrides of JWT and DB.

    - Uses the real JWTService to mint/verify a reset token
    - Overrides DB transaction to accept queries
    - Forces Postgres code path in the endpoint for simpler branches
    - Overrides password service to accept and hash new password
    """
    # Ensure MFA import path is stubbed prior to auth import
    class _StubMFA:
        def generate_secret(self) -> str:
            return "IGNORED"

    mfa_stub_mod = types.ModuleType("mfa_service")
    setattr(mfa_stub_mod, "get_mfa_service", lambda: _StubMFA())
    sys.modules['tldw_Server_API.app.core.AuthNZ.mfa_service'] = mfa_stub_mod

    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-needs-32-chars-minimum")
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.jwt_service import reset_jwt_service
    reset_settings()
    reset_jwt_service()

    # Reload a fresh app instance (router mounts use the stubbed module)
    import tldw_Server_API.app.main as _main
    reloaded = importlib.reload(_main)
    app = reloaded.app

    # Force Postgres branch inside endpoint
    import tldw_Server_API.app.api.v1.endpoints.auth as auth
    # Ensure we have the freshest route definitions (reflecting any code changes)
    auth = importlib.reload(auth)

    async def _is_pg() -> bool:
        return True

    auth.is_postgres_backend = _is_pg  # type: ignore

    # Override DB transaction dep with a stub
    class _StubDB:
        async def fetchval(self, *args, **kwargs):
            # No previous use of token
            return None

        async def fetchrow(self, *args, **kwargs):
            return {"id": 1, "used_at": None}

        async def execute(self, *args, **kwargs):
            class _C:
                async def fetchone(self):
                    return (1, None)
            return _C()

        async def commit(self):
            return True

    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_db_transaction

    async def _override_db_tx():
        return _StubDB()

    app.dependency_overrides[get_db_transaction] = _override_db_tx

    # Build a real password reset token
    from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    reset_token = JWTService(get_settings()).create_password_reset_token(
        user_id=777,
        email="user@example.com",
    )

    # Override password service dep to validate/hash
    class _StubPwd:
        def validate_password_strength(self, new_password: str, username: str | None = None):
            return None

        def hash_password(self, pwd: str) -> str:
            return "HASHED"

    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_password_service_dep

    app.dependency_overrides[get_password_service_dep] = lambda: _StubPwd()

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "new_password": "Strong@12345"},
        )
        assert r.status_code == 200, r.text
        assert "reset" in r.json().get("message", "").lower()

    app.dependency_overrides.clear()
    reset_settings()
    reset_jwt_service()


@pytest.mark.asyncio
async def test_mfa_setup_verify_disable_integration(isolated_test_environment, test_user, monkeypatch):
    """Integration test for MFA endpoints using stubbed MFA + email services.

    - Stubs MFA service via sys.modules before reload (avoids optional deps)
    - Stubs email service for verify step
    - Overrides get_current_active_user dep to provide a user
    """
    client, _db_name = isolated_test_environment

    # Prepare stub MFA and Email services
    class _StubMFA:
        def generate_secret(self) -> str:
            return "STUBSECRET"

        def generate_totp_uri(self, secret: str, username: str) -> str:
            return f"otpauth://totp/{username}?secret={secret}&issuer=TLDW"

        def generate_qr_code(self, totp_uri: str) -> bytes:
            return b"PNGDATA"

        def generate_backup_codes(self):

            return ["code1", "code2", "code3"]

        def verify_totp(self, secret: str, token: str) -> bool:
            return secret == "STUBSECRET" and token == "000000"

        async def get_user_mfa_status(self, user_id: int):
            return {"enabled": False}

        async def enable_mfa(self, user_id: int, secret: str, backup_codes: list[str]) -> bool:
            return True

        async def disable_mfa(self, user_id: int) -> bool:
            return True

    # Patch email service used by verify
    class _StubEmail:
        async def send_mfa_enabled_email(self, to_email: str, username: str, backup_codes, ip_address: str):
            return True

    import tldw_Server_API.app.api.v1.endpoints.auth as auth

    # Monkeypatch service resolvers to avoid optional dependencies
    stub_mfa_instance = _StubMFA()
    monkeypatch.setattr(auth, "_get_mfa_service", lambda: stub_mfa_instance)
    monkeypatch.setattr(auth, "_get_email_service", lambda: _StubEmail())

    # Override get_current_active_user to bypass authentication
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user

    async def _active_user():
        return User(
            id=test_user["id"],
            username=test_user["username"],
            email=test_user["email"],
            is_active=True,
            is_verified=True,
        )

    app = client.app
    previous_override_main = app.dependency_overrides.get(get_current_active_user)
    app.dependency_overrides[get_current_active_user] = _active_user
    # Ensure override binds to the exact reference used in the router
    app.dependency_overrides[auth.get_current_active_user] = _active_user  # type: ignore[attr-defined]

    try:
        # Setup
        r = client.post("/api/v1/auth/mfa/setup")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["secret"] == "STUBSECRET"
        assert data["qr_code"].startswith("data:image/png;base64,")
        assert len(data["backup_codes"]) >= 2

        # Verify using header-secret and token
        secret = data["secret"]
        r2 = client.post(
            "/api/v1/auth/mfa/verify",
            headers={"X-MFA-Secret": secret},
            json={"token": "000000"},
        )
        assert r2.status_code == 200, r2.text
        out = r2.json()
        assert "enabled" in out.get("message", "").lower()
        assert len(out.get("backup_codes", [])) >= 2

        # Disable
        r3 = client.post(
            "/api/v1/auth/mfa/disable",
            data={"password": test_user["password"]},
        )
        assert r3.status_code == 200, r3.text
        assert "disabled" in r3.json().get("message", "").lower()
    finally:
        if previous_override_main is not None:
            app.dependency_overrides[get_current_active_user] = previous_override_main
        else:
            app.dependency_overrides.pop(get_current_active_user, None)
        app.dependency_overrides.pop(auth.get_current_active_user, None)  # type: ignore[attr-defined]
