import os
import asyncio
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


class _Req:
    def __init__(self, method="POST", path="/api/v1/scheduler/workflows/dry-run"):
        self.method = method
        class _U:
            def __init__(self, p):
                self.path = p
        self.url = _U(path)
        self.path_params = {}
        self.headers = {}


def test_allowed_endpoints_and_max_calls(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    reset_settings()
    svc = JWTService(get_settings())
    token = svc.create_virtual_access_token(
        user_id=1,
        username="u",
        role="user",
        scope="workflows",
        ttl_minutes=5,
        additional_claims={
            "allowed_endpoints": ["scheduler.workflows.dry_run"],
            "max_calls": 1,
        },
    )
    dep = require_token_scope(
        "workflows",
        require_if_present=True,
        endpoint_id="scheduler.workflows.dry_run",
        count_as="call",
    )
    req = _Req()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    # First call OK
    asyncio.run(dep(request=req, credentials=creds))
    # Second call exceeds max_calls
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dep(request=req, credentials=creds))
    assert ei.value.status_code == 403
