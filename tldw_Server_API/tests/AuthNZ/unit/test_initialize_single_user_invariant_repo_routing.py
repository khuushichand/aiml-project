from __future__ import annotations

import pytest

from tldw_Server_API.app.core.AuthNZ import initialize
from tldw_Server_API.app.core.AuthNZ.repos import api_keys_repo as api_keys_repo_module
from tldw_Server_API.app.core.AuthNZ.repos import users_repo as users_repo_module


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_collect_single_user_invariants_uses_repo_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeUsersRepo:
        calls: list[dict[str, object]] = []

        def __init__(self, db_pool):
            self.db_pool = db_pool

        async def list_users(
            self,
            *,
            offset: int,
            limit: int,
            role: str | None = None,
            is_active: bool | None = None,
            search: str | None = None,
            org_ids: list[int] | None = None,
        ):
            _FakeUsersRepo.calls.append(
                {
                    "offset": offset,
                    "limit": limit,
                    "role": role,
                    "is_active": is_active,
                    "search": search,
                    "org_ids": org_ids,
                }
            )
            if role == "admin":
                return [{"id": 1}], 1
            return [{"id": 1}], 1

    class _FakeApiKeysRepo:
        calls: list[dict[str, object]] = []

        def __init__(self, db_pool):
            self.db_pool = db_pool

        async def list_user_keys(self, *, user_id: int, include_revoked: bool = False):
            _FakeApiKeysRepo.calls.append(
                {"user_id": user_id, "include_revoked": include_revoked}
            )
            return [{"id": 7, "key_hash": "expected_hash", "is_virtual": False}]

    monkeypatch.setattr(users_repo_module, "AuthnzUsersRepo", _FakeUsersRepo)
    monkeypatch.setattr(api_keys_repo_module, "AuthnzApiKeysRepo", _FakeApiKeysRepo)

    errors = await initialize._collect_single_user_invariant_errors(
        pool=object(),  # pool is passed through to repos only
        expected_user_id=1,
        expected_key_hash="expected_hash",
        check_keys=True,
    )

    assert errors == []
    assert len(_FakeUsersRepo.calls) == 2
    assert _FakeUsersRepo.calls[0]["role"] is None
    assert _FakeUsersRepo.calls[0]["is_active"] is True
    assert _FakeUsersRepo.calls[1]["role"] == "admin"
    assert _FakeUsersRepo.calls[1]["is_active"] is True
    assert _FakeApiKeysRepo.calls == [{"user_id": 1, "include_revoked": False}]


@pytest.mark.asyncio
async def test_collect_single_user_invariants_reports_repo_driven_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeUsersRepo:
        def __init__(self, db_pool):
            self.db_pool = db_pool

        async def list_users(
            self,
            *,
            offset: int,
            limit: int,
            role: str | None = None,
            is_active: bool | None = None,
            search: str | None = None,
            org_ids: list[int] | None = None,
        ):
            if role == "admin":
                return [{"id": 1}, {"id": 3}], 2
            return [{"id": 1}, {"id": 2}], 2

    class _FakeApiKeysRepo:
        def __init__(self, db_pool):
            self.db_pool = db_pool

        async def list_user_keys(self, *, user_id: int, include_revoked: bool = False):
            return [
                {"id": 10, "key_hash": "hash-a", "is_virtual": False},
                {"id": 11, "key_hash": "hash-b", "is_virtual": False},
            ]

    monkeypatch.setattr(users_repo_module, "AuthnzUsersRepo", _FakeUsersRepo)
    monkeypatch.setattr(api_keys_repo_module, "AuthnzApiKeysRepo", _FakeApiKeysRepo)

    errors = await initialize._collect_single_user_invariant_errors(
        pool=object(),
        expected_user_id=1,
        expected_key_hash="expected_hash",
        check_keys=True,
    )

    assert any("Multiple active users detected" in message for message in errors)
    assert any("Multiple admin users detected" in message for message in errors)
    assert any(
        "Active primary API key does not match SINGLE_USER_API_KEY." in message
        for message in errors
    )
    assert any(
        "Unexpected active non-virtual API keys found" in message for message in errors
    )
