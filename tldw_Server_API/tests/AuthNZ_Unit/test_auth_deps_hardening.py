from datetime import timezone
import io
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Response
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


class _FailingCommitConn:
    async def execute(self, query: str, params: Any) -> Any:
        return SimpleNamespace()

    async def commit(self) -> None:
        raise RuntimeError("sqlite commit failed")


class _AcquireCM:
    async def __aenter__(self) -> _FailingCommitConn:
        return _FailingCommitConn()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeDBPool:
    def acquire(self) -> _AcquireCM:
             return _AcquireCM()


class _DummyRequest:
    def __init__(self) -> None:
             self.state = SimpleNamespace()
        self.client = SimpleNamespace(host="127.0.0.1")
        self.method = "GET"
        self.url = SimpleNamespace(path="/test")
        self.headers: dict[str, str] = {}


@pytest.mark.asyncio
async def test_test_db_adapter_execute_propagates_sqlite_commit_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_get_db_pool() -> _FakeDBPool:
        return _FakeDBPool()

    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setattr(auth_deps, "get_db_pool", _fake_get_db_pool)

    agen = auth_deps.get_db_transaction()
    adapter = await agen.__anext__()
    try:
        with pytest.raises(RuntimeError, match="sqlite commit failed"):
            await adapter.execute("SELECT 1")
    finally:
        await agen.aclose()


@pytest.mark.asyncio
async def test_test_db_adapter_commit_propagates_sqlite_commit_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_get_db_pool() -> _FakeDBPool:
        return _FakeDBPool()

    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setattr(auth_deps, "get_db_pool", _fake_get_db_pool)

    agen = auth_deps.get_db_transaction()
    adapter = await agen.__anext__()
    try:
        with pytest.raises(RuntimeError, match="sqlite commit failed"):
            await adapter.commit()
    finally:
        await agen.aclose()


@pytest.mark.asyncio
async def test_stub_session_manager_uses_timezone_aware_timestamps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.delenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", raising=False)

    sm = await auth_deps.get_session_manager_dep()
    sess = await sm.create_session(
        user_id=1,
        access_token="access",
        refresh_token="refresh",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    for field in ("created_at", "last_activity", "expires_at"):
        dt = sess[field]
        assert getattr(dt, "tzinfo", None) is timezone.utc

    refreshed = await sm.refresh_session("unused-positional", session_id=1, user_id=1)
    assert str(refreshed["expires_at"]).endswith("+00:00")

@pytest.mark.asyncio
async def test_get_current_user_fast_path_sanitizes_cached_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MODE", "0")

    request = _DummyRequest()
    request.state._auth_user = {
        "id": 42,
        "username": "alice",
        "email": "alice@example.com",
        "role": "user",
        "password_hash": "super-secret",
        "hashed_password": "super-secret",
        "two_factor_secret": "2fa-secret",
        "totp_secret": "totp-secret",
        "backup_codes": "backup-secret",
        "access_token": "access-secret",
        "refresh_token": "refresh-secret",
        "api_key": "api-key-secret",
        "ssn": "123-45-6789",
    }
    request.state.auth = AuthContext(
        principal=AuthPrincipal(kind="user", user_id=42, is_admin=True),
    )

    user = await auth_deps.get_current_user(
        request=request,
        response=Response(),
        credentials=None,
        session_manager=object(),
        db_pool=object(),
        x_api_key=None,
    )

    assert user["id"] == 42
    assert user["username"] == "alice"
    assert "password_hash" not in user
    assert "hashed_password" not in user
    assert "two_factor_secret" not in user
    assert "totp_secret" not in user
    assert "backup_codes" not in user
    assert "access_token" not in user
    assert "refresh_token" not in user
    assert "api_key" not in user
    assert "ssn" not in user

    cached = request.state._auth_user
    assert isinstance(cached, dict)
    assert "password_hash" not in cached


@pytest.mark.asyncio
async def test_api_key_auth_error_logging_does_not_leak_exception_message_outside_test_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "__auth_deps_secret__"

    async def _boom_api_key_mgr() -> Any:
        raise RuntimeError(f"boom: {secret}")

    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")
    monkeypatch.setattr(auth_deps, "get_api_key_manager", _boom_api_key_mgr)

    sink = io.StringIO()
    token = logger.add(sink, level="ERROR")
    try:
        with pytest.raises(HTTPException) as exc_info:
            await auth_deps.get_current_user(
                request=_DummyRequest(),
                response=Response(),
                credentials=None,
                session_manager=object(),
                db_pool=object(),
                x_api_key="not-a-real-key",
            )
        assert exc_info.value.status_code == 401
    finally:
        logger.remove(token)

    captured = sink.getvalue()
    assert "API key authentication error in get_current_user" in captured
    assert secret not in captured


def _profile_helper_should_not_be_called() -> bool:


     raise AssertionError("Profile helper should not be used for rate-limit bypass")

def _mode_helper_should_not_be_called() -> bool:

     raise AssertionError("Mode helper should not be used for rate-limit bypass")


@pytest.mark.asyncio
@pytest.mark.parametrize("func_name", ["check_rate_limit", "check_auth_rate_limit"])
async def test_admin_rate_limit_bypass_is_principal_first(
    monkeypatch: pytest.MonkeyPatch,
    func_name: str,
) -> None:
    async def _boom_auth_governor() -> Any:
        raise RuntimeError("auth_governor_called")

    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")
    monkeypatch.setattr(auth_deps, "is_single_user_mode", _mode_helper_should_not_be_called)
    monkeypatch.setattr(auth_deps, "is_single_user_profile_mode", _profile_helper_should_not_be_called)
    monkeypatch.setattr(auth_deps, "get_auth_governor", _boom_auth_governor)

    calls = {"count": 0}

    def _fake_is_single_user_principal(principal: AuthPrincipal | None) -> bool:
        calls["count"] += 1
        if not isinstance(principal, AuthPrincipal):
            return False
        return getattr(principal, "subject", None) == "single_user"

    monkeypatch.setattr(auth_deps, "is_single_user_principal", _fake_is_single_user_principal)

    request = _DummyRequest()
    request.state.auth = AuthContext(
        principal=AuthPrincipal(kind="user", is_admin=True, subject=None),
    )

    func = getattr(auth_deps, func_name)

    with pytest.raises(RuntimeError, match="auth_governor_called"):
        await func(request=request, rate_limiter=object())
    assert calls["count"] == 1

    request.state.auth = AuthContext(
        principal=AuthPrincipal(kind="user", is_admin=True, subject="single_user"),
    )
    await func(request=request, rate_limiter=object())
    assert calls["count"] == 2
