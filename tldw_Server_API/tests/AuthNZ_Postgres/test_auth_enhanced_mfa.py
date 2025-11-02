from types import SimpleNamespace
import os
import pytest

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


@pytest.mark.asyncio
async def test_mfa_setup_and_verify_roundtrip_pg(monkeypatch, setup_test_database):
    """MFA must only work on PostgreSQL.

    This test runs in the AuthNZ_Postgres suite, which requires a real
    PostgreSQL DSN via TEST_DATABASE_URL/DATABASE_URL. No monkeypatching of
    backend detection is allowed here.
    """
    # Enforce multi-user mode; DATABASE_URL is set by setup_test_database
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    reset_settings()

    # Stub MFA + Email services by preloading modules (behavioral unit-style)
    class _StubMFA:
        def generate_secret(self) -> str:
            return "SECRETPAD"

        def generate_totp_uri(self, secret: str, username: str) -> str:
            return f"otpauth://totp/{username}?secret={secret}&issuer=TLDW"

        def generate_qr_code(self, totp_uri: str) -> bytes:
            return b"PNGDATA"

        def generate_backup_codes(self):
            return ["code1", "code2", "code3"]

        def verify_totp(self, secret: str, token: str) -> bool:
            return token == "000000"

        async def enable_mfa(self, user_id: int, secret: str, backup_codes: list[str]) -> bool:
            return True

        async def get_user_mfa_status(self, user_id: int):
            return {"enabled": False}

    class _StubEmail:
        async def send_mfa_enabled_email(self, to_email: str, username: str, backup_codes, ip_address: str):
            return True

    import sys, types

    mfa_stub = types.ModuleType("mfa_service")
    setattr(mfa_stub, "get_mfa_service", lambda: _StubMFA())
    sys.modules['tldw_Server_API.app.core.AuthNZ.mfa_service'] = mfa_stub
    email_stub = types.ModuleType("email_service")
    setattr(email_stub, "get_email_service", lambda: _StubEmail())
    sys.modules['tldw_Server_API.app.core.AuthNZ.email_service'] = email_stub

    import tldw_Server_API.app.api.v1.endpoints.auth_enhanced as _auth_enh

    # Unit-style call: setup_mfa (allowed only because PG is real)
    res = await _auth_enh.setup_mfa(
        current_user=User(id=1, username="alice", email="alice@example.com", is_active=True),
        db=SimpleNamespace(),
    )
    assert res.secret == "SECRETPAD"
    assert res.qr_code.startswith("data:image/png;base64,")
    assert len(res.backup_codes) >= 2

    # Unit-style call: verify_mfa_setup
    req = SimpleNamespace(headers={"X-MFA-Secret": res.secret}, client=SimpleNamespace(host="127.0.0.1"))
    out = await _auth_enh.verify_mfa_setup(
        data=_auth_enh.MFAVerifyRequest(token="000000"),
        request=req,
        current_user=User(id=1, username="alice", email="alice@example.com", is_active=True),
    )
    assert out.get("message")
    assert len(out.get("backup_codes", [])) >= 2

    reset_settings()
