from typing import Dict, List, Optional

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.types import Scope

from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as user_db


def _make_request() -> Request:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


class _StubJWTService:
    def __init__(self, payload: Dict[str, object]) -> None:
        self._payload = payload

    def decode_access_token(self, _token: str) -> Dict[str, object]:
        return dict(self._payload)


class _StubSessionManager:
    async def is_token_blacklisted(self, _token: str, _jti: Optional[str] = None) -> bool:
        return False


class _StubUsersRepo:
    async def get_user_by_id(self, user_id: int):
        return {
            "id": user_id,
            "username": "jwt-user",
            "email": "jwt@example.com",
            "role": "user",
            "is_active": True,
            "is_verified": True,
        }

    async def get_user_by_uuid(self, _identifier: str):
        return None

    async def get_user_by_username(self, _username: str):
        return None


@pytest.mark.asyncio
async def test_verify_jwt_and_fetch_user_rejects_stale_memberships(monkeypatch):
    payload = {
        "sub": "1",
        "org_ids": [2],
        "team_ids": [20],
        "jti": "jti-1",
        "type": "access",
    }

    async def _fake_get_session_manager():
        return _StubSessionManager()

    async def _fake_list_memberships_for_user(_user_id: int) -> List[Dict[str, int]]:
        return [{"org_id": 1, "team_id": 10}]

    def _fake_enrich(_user_id, _user_data, *, pii_redact_logs=False):
        return ["user"], ["media.read"], False

    async def _fake_from_pool():
        return _StubUsersRepo()

    monkeypatch.setattr(user_db, "get_jwt_service", lambda: _StubJWTService(payload))
    monkeypatch.setattr(user_db, "get_session_manager", _fake_get_session_manager)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.repos.users_repo.AuthnzUsersRepo.from_pool",
        _fake_from_pool,
    )
    monkeypatch.setattr(user_db, "list_memberships_for_user", _fake_list_memberships_for_user)
    monkeypatch.setattr(user_db, "_enrich_user_with_rbac", _fake_enrich)

    request = _make_request()

    with pytest.raises(HTTPException) as exc_info:
        await user_db.verify_jwt_and_fetch_user(request, token="aaa.bbb.ccc")

    assert exc_info.value.status_code == 403
    assert "membership" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_verify_jwt_and_fetch_user_accepts_valid_membership_claims(monkeypatch):
    payload = {
        "sub": "1",
        "org_ids": [1],
        "team_ids": [10],
        "active_org_id": 1,
        "active_team_id": 10,
        "jti": "jti-2",
        "type": "access",
    }

    async def _fake_get_session_manager():
        return _StubSessionManager()

    async def _fake_list_memberships_for_user(_user_id: int) -> List[Dict[str, int]]:
        return [{"org_id": 1, "team_id": 10}]

    def _fake_enrich(_user_id, _user_data, *, pii_redact_logs=False):
        return ["user"], ["media.read"], False

    async def _fake_from_pool():
        return _StubUsersRepo()

    monkeypatch.setattr(user_db, "get_jwt_service", lambda: _StubJWTService(payload))
    monkeypatch.setattr(user_db, "get_session_manager", _fake_get_session_manager)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.repos.users_repo.AuthnzUsersRepo.from_pool",
        _fake_from_pool,
    )
    monkeypatch.setattr(user_db, "list_memberships_for_user", _fake_list_memberships_for_user)
    monkeypatch.setattr(user_db, "_enrich_user_with_rbac", _fake_enrich)

    request = _make_request()
    user = await user_db.verify_jwt_and_fetch_user(request, token="aaa.bbb.ccc")

    assert user.username == "jwt-user"
    assert request.state.org_ids == [1]
    assert request.state.team_ids == [10]
    assert request.state.active_org_id == 1
    assert request.state.active_team_id == 10
