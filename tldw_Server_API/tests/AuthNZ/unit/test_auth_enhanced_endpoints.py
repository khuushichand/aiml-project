from types import SimpleNamespace
import os
import time
from datetime import datetime

import pytest
from starlette.requests import Request

from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


@pytest.mark.asyncio
async def test_reset_password_weak_and_success(monkeypatch):
    reset_settings()
    # Stub DB adapter expected by endpoint (fetchval/execute/commit)
    class _StubDB:
        async def fetchval(self, *args, **kwargs):
            return None

        async def execute(self, *args, **kwargs):
            class _C:
                lastrowid = 1

                async def fetchone(self):
                    # Simulate existing reset token record
                    return (1, None)

            return _C()

        async def commit(self):
            return True

    class _StubJWT:
        def verify_token(self, token: str, token_type: str | None = None):
            return {"sub": 42}

        def hash_token_candidates(self, token: str) -> list[str]:
            return ["htok"]

        def hash_token(self, token: str) -> str:
            return "htok"

    class _StubPwd:
        def __init__(self, weak: bool = False):
            self.weak = weak
        def validate_password_strength(self, new_password: str, username: str | None = None):
            if self.weak:
                from tldw_Server_API.app.core.AuthNZ.exceptions import WeakPasswordError
                raise WeakPasswordError("Password too weak")
        def hash_password(self, pwd: str) -> str:
            return "HASHED"

    import tldw_Server_API.app.api.v1.endpoints.auth_enhanced as _auth_enh

    async def _fake_is_pg() -> bool:
        return False

    monkeypatch.setattr(_auth_enh, "is_postgres_backend", _fake_is_pg)

    # Weak password
    with pytest.raises(Exception):
        await _auth_enh.reset_password(
            data=_auth_enh.ResetPasswordRequest(token="tok", new_password="weak"),
            db=_StubDB(),
            jwt_service=_StubJWT(),
            password_service=_StubPwd(weak=True),
        )

    # Success path
    out = await _auth_enh.reset_password(
        data=_auth_enh.ResetPasswordRequest(token="tok", new_password="Strong@12345"),
        db=_StubDB(),
        jwt_service=_StubJWT(),
        password_service=_StubPwd(weak=False),
    )
    assert "success" in out.get("message", "").lower()


@pytest.mark.asyncio
async def test_logout_uses_utc_expiry(monkeypatch):
    if not hasattr(time, "tzset"):
        pytest.skip("tzset not available on this platform")
    reset_settings()

    import tldw_Server_API.app.api.v1.endpoints.auth_enhanced as auth_enh

    exp_ts = 1_700_000_000
    captured = {"expires_at": None, "revoked_sessions": []}

    class StubJWT:
        def __init__(self):
            pass

        def extract_jti(self, token: str) -> str:
            return "jti-123"

        def verify_token(self, token: str):
            return {"exp": exp_ts, "session_id": 777}

    class StubBlacklist:
        async def revoke_all_user_tokens(self, **kwargs):
            return 0

        async def revoke_token(
            self,
            *,
            jti,
            expires_at,
            user_id,
            token_type,
            reason,
            revoked_by=None,
            ip_address=None,
        ):
            captured["expires_at"] = expires_at
            captured["token_type"] = token_type
            captured["ip_address"] = ip_address
            return True

    class StubSessionManager:
        async def revoke_all_user_sessions(self, **kwargs):
            captured["revoked_sessions"].append(("all", kwargs))

        async def revoke_session(self, *, session_id, revoked_by=None, reason=None):
            captured["revoked_sessions"].append(
                ("single", {"session_id": session_id, "revoked_by": revoked_by, "reason": reason})
            )

    monkeypatch.setattr(auth_enh, "JWTService", StubJWT)
    stub_blacklist = StubBlacklist()
    monkeypatch.setattr(auth_enh, "get_token_blacklist", lambda: stub_blacklist)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/logout",
        "headers": [(b"authorization", b"Bearer my-token")],
        "client": ("203.0.113.5", 1234),
        "scheme": "http",
        "query_string": b"",
        "server": ("testserver", 80),
    }
    request = Request(scope)
    data = auth_enh.LogoutRequest(all_devices=False)
    current_user = SimpleNamespace(id=99)
    session_manager = StubSessionManager()

    original_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "US/Pacific"
        time.tzset()
        result = await auth_enh.logout(
            data=data,
            request=request,
            current_user=current_user,
            session_manager=session_manager,
        )
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()

    assert result["message"] == "Logged out successfully"
    assert captured["expires_at"] == datetime.utcfromtimestamp(exp_ts)
    assert captured["token_type"] == "access"
    assert captured["revoked_sessions"][0][0] == "single"
