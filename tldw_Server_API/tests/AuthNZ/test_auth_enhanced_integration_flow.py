import types
import sys
import importlib
import json

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_reset_password_integration_success(monkeypatch):
    """End-to-end reset-password via dependency overrides of JWT and DB.

    - Overrides get_jwt_service_dep to return a stub verifying the token
    - Overrides DB transaction to accept queries
    - Forces Postgres code path in the endpoint for simpler branches
    - Overrides password service to accept and hash new password
    """
    # Ensure MFA import path is stubbed prior to auth_enhanced import
    class _StubMFA:
        def generate_secret(self) -> str:
            return "IGNORED"

    mfa_stub_mod = types.ModuleType("mfa_service")
    setattr(mfa_stub_mod, "get_mfa_service", lambda: _StubMFA())
    sys.modules['tldw_Server_API.app.core.AuthNZ.mfa_service'] = mfa_stub_mod

    # Reload a fresh app instance (router mounts use the stubbed module)
    import tldw_Server_API.app.main as _main
    reloaded = importlib.reload(_main)
    app = reloaded.app

    # Force Postgres branch inside endpoint
    import tldw_Server_API.app.api.v1.endpoints.auth_enhanced as auth_enh
    # Ensure we have the freshest route definitions (reflecting any code changes)
    auth_enh = importlib.reload(auth_enh)

    async def _is_pg() -> bool:
        return True

    auth_enh.is_postgres_backend = _is_pg  # type: ignore

    # Override DB transaction dep with a stub
    class _StubDB:
        async def fetchval(self, *args, **kwargs):
            # No previous use of token
            return None

        async def execute(self, *args, **kwargs):
            class _C:
                async def fetchone(self):
                    return None
            return _C()

        async def commit(self):
            return True

    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_db_transaction

    async def _override_db_tx():
        return _StubDB()

    app.dependency_overrides[get_db_transaction] = _override_db_tx

    # Override JWT service dep to accept provided token
    class _StubJWT:
        def verify_token(self, token: str, token_type: str | None = None):
            return {"sub": 777, "type": "password_reset"}

        def hash_token(self, token: str) -> str:
            return "htok"

    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_jwt_service_dep

    app.dependency_overrides[get_jwt_service_dep] = lambda: _StubJWT()

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
            json={"token": "dummy-token", "new_password": "Strong@12345"},
        )
        assert r.status_code == 200, r.text
        assert "reset" in r.json().get("message", "").lower()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mfa_setup_verify_disable_integration(tmp_path, monkeypatch):
    """Integration test for MFA endpoints using stubbed MFA + email services.

    - Stubs MFA service via sys.modules before reload (avoids optional deps)
    - Stubs email service for verify step
    - Overrides get_current_active_user dep to provide a user
    """
    # Ensure test-mode behavior for DB adapter path and deterministic CSRF
    monkeypatch.setenv("TEST_MODE", "true")

    # Prepare stub MFA and Email services prior to app import
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

    mfa_stub_mod = types.ModuleType("mfa_service")
    setattr(mfa_stub_mod, "get_mfa_service", lambda: _StubMFA())
    sys.modules['tldw_Server_API.app.core.AuthNZ.mfa_service'] = mfa_stub_mod

    # Preload and reload enhanced auth module so main picks up latest router
    mod = importlib.import_module('tldw_Server_API.app.api.v1.endpoints.auth_enhanced')
    auth_enh_pre = importlib.reload(mod)

    # Build a minimal FastAPI app with just the enhanced auth router mounted
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(auth_enh_pre.router, prefix="/api/v1")

    # Patch email service used by verify
    class _StubEmail:
        async def send_mfa_enabled_email(self, to_email: str, username: str, backup_codes, ip_address: str):
            return True

    import tldw_Server_API.app.api.v1.endpoints.auth_enhanced as auth_enh
    # ensure we use the reloaded module reference
    auth_enh = auth_enh_pre
    auth_enh.get_email_service = lambda: _StubEmail()  # type: ignore

    # Override get_current_active_user to bypass authentication
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user

    async def _active_user():
        return User(id=1, username="alice", email="alice@example.com", is_active=True)

    app.dependency_overrides[get_current_active_user] = _active_user
    # Also ensure override binds to the exact reference used in the router
    app.dependency_overrides[auth_enh.get_current_active_user] = _active_user  # type: ignore[attr-defined]

    # Override DB transaction to a minimal stub (route doesn't use it but dependency resolves)
    async def _override_db_tx():
        class _Conn:
            async def execute(self, *args, **kwargs):
                class _C:
                    async def fetchone(self):
                        return None
                return _C()

            async def fetchrow(self, *args, **kwargs):
                return None

            async def fetch(self, *args, **kwargs):
                return []

            async def fetchval(self, *args, **kwargs):
                return None

            async def commit(self):
                return True

        return _Conn()

    # Important: Override using the exact function object referenced by the router
    app.dependency_overrides[auth_enh.get_db_transaction] = _override_db_tx  # type: ignore[attr-defined]

    with TestClient(app) as client:
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
            data={"password": "irrelevant"},
        )
        assert r3.status_code == 200, r3.text
        assert "disabled" in r3.json().get("message", "").lower()

    app.dependency_overrides.clear()
