from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ import permissions as perms_mod


class _FakeUserDB:
    def __init__(self):
        self.calls: list[tuple[str, int, str]] = []
        self._has_perm_result = False
        self._has_role_result = False

    def set_permission_result(self, value: bool) -> None:
        self._has_perm_result = bool(value)

    def set_role_result(self, value: bool) -> None:
        self._has_role_result = bool(value)

    def has_permission(self, user_id, permission: str) -> bool:
        self.calls.append(("perm", int(user_id), permission))
        return self._has_perm_result

    def has_role(self, user_id, role: str) -> bool:
        self.calls.append(("role", int(user_id), role))
        return self._has_role_result


def _make_user(roles=None, permissions=None, is_admin: bool = False) -> User:
    return User(
        id=1,
        username="testuser",
        email=None,
        is_active=True,
        roles=list(roles or []),
        permissions=list(permissions or []),
        is_admin=is_admin,
    )


@pytest.mark.asyncio
async def test_check_permission_uses_claims_true(monkeypatch):
    # Not in single-user mode
    monkeypatch.setattr(perms_mod, "is_single_user_mode", lambda: False)

    fake_db = _FakeUserDB()

    def _fake_get_user_database():
        return fake_db

    monkeypatch.setattr(perms_mod, "get_user_database", _fake_get_user_database)

    user = _make_user(permissions=["media.read", "media.create"])

    assert perms_mod.check_permission(user, "media.read") is True
    # When claims list is present, DB should not be consulted
    assert fake_db.calls == []


@pytest.mark.asyncio
async def test_check_permission_uses_claims_false_without_db(monkeypatch):
    monkeypatch.setattr(perms_mod, "is_single_user_mode", lambda: False)

    fake_db = _FakeUserDB()

    def _fake_get_user_database():
        return fake_db

    monkeypatch.setattr(perms_mod, "get_user_database", _fake_get_user_database)

    user = _make_user(permissions=["media.read"])

    assert perms_mod.check_permission(user, "media.create") is False
    # Claims present but missing; DB should not be hit
    assert fake_db.calls == []


@pytest.mark.asyncio
async def test_check_permission_falls_back_to_db_when_permissions_absent(monkeypatch):
    monkeypatch.setattr(perms_mod, "is_single_user_mode", lambda: False)

    fake_db = _FakeUserDB()
    fake_db.set_permission_result(True)

    def _fake_get_user_database():
        return fake_db

    monkeypatch.setattr(perms_mod, "get_user_database", _fake_get_user_database)

    # Use a minimal object without a permissions attribute
    user = SimpleNamespace(id=5, username="legacy-user", is_active=True)

    assert perms_mod.check_permission(user, "media.read") is True
    assert fake_db.calls == [("perm", 5, "media.read")]


@pytest.mark.asyncio
async def test_check_role_uses_claims_true(monkeypatch):
    monkeypatch.setattr(perms_mod, "is_single_user_mode", lambda: False)

    fake_db = _FakeUserDB()

    def _fake_get_user_database():
        return fake_db

    monkeypatch.setattr(perms_mod, "get_user_database", _fake_get_user_database)

    user = _make_user(roles=["user", "editor"])

    assert perms_mod.check_role(user, "editor") is True
    assert fake_db.calls == []


@pytest.mark.asyncio
async def test_check_role_uses_claims_false_without_db(monkeypatch):
    monkeypatch.setattr(perms_mod, "is_single_user_mode", lambda: False)

    fake_db = _FakeUserDB()

    def _fake_get_user_database():
        return fake_db

    monkeypatch.setattr(perms_mod, "get_user_database", _fake_get_user_database)

    user = _make_user(roles=["user"])

    assert perms_mod.check_role(user, "admin") is False
    assert fake_db.calls == []


@pytest.mark.asyncio
async def test_check_role_falls_back_to_db_when_roles_absent(monkeypatch):
    monkeypatch.setattr(perms_mod, "is_single_user_mode", lambda: False)

    fake_db = _FakeUserDB()
    fake_db.set_role_result(True)

    def _fake_get_user_database():
        return fake_db

    monkeypatch.setattr(perms_mod, "get_user_database", _fake_get_user_database)

    user = SimpleNamespace(id=8, username="legacy-user", is_active=True)

    assert perms_mod.check_role(user, "admin") is True
    assert fake_db.calls == [("role", 8, "admin")]


@pytest.mark.asyncio
async def test_check_permission_single_user_mode_always_true(monkeypatch):
    monkeypatch.setattr(perms_mod, "is_single_user_mode", lambda: True)

    fake_db = _FakeUserDB()

    def _fake_get_user_database():
        raise AssertionError("DB should not be used in single-user mode")

    monkeypatch.setattr(perms_mod, "get_user_database", _fake_get_user_database)

    user = _make_user(permissions=[])

    assert perms_mod.check_permission(user, "any.permission") is True


@pytest.mark.asyncio
async def test_check_role_single_user_mode_treats_as_admin(monkeypatch):
    monkeypatch.setattr(perms_mod, "is_single_user_mode", lambda: True)

    fake_db = _FakeUserDB()

    def _fake_get_user_database():
        raise AssertionError("DB should not be used in single-user mode")

    monkeypatch.setattr(perms_mod, "get_user_database", _fake_get_user_database)

    user = _make_user(roles=["user"])

    assert perms_mod.check_role(user, "admin") is True
    assert perms_mod.check_role(user, "user") is True
    # Non-admin/user roles still rejected
    assert perms_mod.check_role(user, "viewer") is False

