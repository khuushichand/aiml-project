from types import SimpleNamespace
import pytest
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
                    return None
            return _C()
        async def commit(self):
            return True

    class _StubJWT:
        def verify_token(self, token: str, token_type: str | None = None):
            return {"sub": 42}
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
