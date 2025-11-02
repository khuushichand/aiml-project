import os
import asyncio

from fastapi.security import HTTPAuthorizationCredentials

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


class _ReqStub:
    def __init__(self, schedule_id: str | None = None, headers: dict[str, str] | None = None):
        self.path_params = {}
        if schedule_id is not None:
            self.path_params["schedule_id"] = schedule_id
        self.headers = headers or {}


def test_enforce_scope_and_schedule_match(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_SECRET_KEY", "top_secret_key_for_tests_1234567890")
    reset_settings()
    svc = JWTService(get_settings())
    token = svc.create_virtual_access_token(
        user_id=1, username="tester", role="user", scope="workflows", ttl_minutes=5, schedule_id="sched-abc"
    )

    # Build the dependency function
    dep = require_token_scope("workflows", require_if_present=True, require_schedule_match=True)

    # Matching schedule_id -> OK (no exception)
    req = _ReqStub(schedule_id="sched-abc")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    asyncio.run(dep(request=req, credentials=creds))

    # Mismatch schedule_id -> raises HTTPException 403
    import pytest
    from fastapi import HTTPException
    req2 = _ReqStub(schedule_id="sched-xyz")
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dep(request=req2, credentials=creds))
    assert ei.value.status_code == 403
