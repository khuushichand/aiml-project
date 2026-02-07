from datetime import timezone
import io
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter
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


@pytest.mark.asyncio
async def test_get_current_user_prefers_jwt_then_falls_back_to_api_key_on_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"jwt": 0, "api_key": 0}

    async def _fake_verify_jwt_and_fetch_user(request, token: str = ""):
        calls["jwt"] += 1
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async def _fake_api_key_auth(request, api_key: str):
        calls["api_key"] += 1
        return {
            "id": 99,
            "username": "api-user",
            "is_active": True,
            "is_verified": True,
        }

    monkeypatch.setattr(auth_deps, "verify_jwt_and_fetch_user", _fake_verify_jwt_and_fetch_user)
    monkeypatch.setattr(auth_deps, "_authenticate_api_key_from_request", _fake_api_key_auth)

    request = _DummyRequest()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="aaa.bbb.ccc")

    user = await auth_deps.get_current_user(
        request=request,
        response=Response(),
        credentials=creds,
        session_manager=object(),
        db_pool=object(),
        x_api_key="api-key",
    )

    assert user["id"] == 99
    assert calls["jwt"] == 1
    assert calls["api_key"] == 1


@pytest.mark.asyncio
async def test_get_current_user_does_not_fall_back_when_jwt_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_verify_jwt_and_fetch_user(request, token: str = ""):
        return {
            "id": 42,
            "username": "jwt-user",
            "is_active": True,
            "is_verified": True,
        }

    async def _fake_api_key_auth(request, api_key: str):
        raise AssertionError("API key auth should not be used when JWT succeeds")

    monkeypatch.setattr(auth_deps, "verify_jwt_and_fetch_user", _fake_verify_jwt_and_fetch_user)
    monkeypatch.setattr(auth_deps, "_authenticate_api_key_from_request", _fake_api_key_auth)

    request = _DummyRequest()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="aaa.bbb.ccc")

    user = await auth_deps.get_current_user(
        request=request,
        response=Response(),
        credentials=creds,
        session_manager=object(),
        db_pool=object(),
        x_api_key="api-key",
    )

    assert user["id"] == 42


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


@pytest.mark.asyncio
async def test_check_rate_limit_falls_back_to_ip_for_non_int_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MODE", "0")
    request = _DummyRequest()
    request.state.user_id = "not-an-int"

    calls = {"user": 0, "ip": 0}

    class _StubLimiter:
        enabled = True

        async def check_user_rate_limit(self, user_id, endpoint, **kwargs):
            calls["user"] += 1
            return True, {}

        async def check_rate_limit(self, identifier, endpoint, **kwargs):
            calls["ip"] += 1
            return True, {}

    await auth_deps.check_rate_limit(request=request, rate_limiter=_StubLimiter())
    assert calls["user"] == 0
    assert calls["ip"] == 1


@pytest.mark.asyncio
async def test_check_auth_rate_limit_is_effectively_permissive_when_rg_disabled_and_limiter_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RG_ENABLED", "0")
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")
    monkeypatch.setenv("TESTING", "0")

    async def _fake_get_auth_governor() -> object:
        return object()

    monkeypatch.setattr(auth_deps, "get_auth_governor", _fake_get_auth_governor)

    request = _DummyRequest()
    request.url.path = "/api/v1/auth/forgot-password"

    limiter = RateLimiter(
        db_pool=None,
        settings=SimpleNamespace(
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_PER_MINUTE=1,
            RATE_LIMIT_BURST=1,
            SERVICE_ACCOUNT_RATE_LIMIT=1,
            REDIS_URL=None,
        ),
    )

    # No rg_policy_id is attached when RG middleware is disabled. In that case,
    # check_auth_rate_limit falls back to the AuthNZ limiter, whose checks are
    # intentional no-ops during RG cutover.
    await auth_deps.check_auth_rate_limit(request=request, rate_limiter=limiter)


@pytest.mark.asyncio
async def test_get_session_manager_dep_requires_explicit_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.delenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", raising=False)

    sentinel = object()

    async def _fake_get_session_manager() -> object:
        return sentinel

    monkeypatch.setattr(auth_deps, "get_session_manager", _fake_get_session_manager)

    resolved = await auth_deps.get_session_manager_dep()
    assert resolved is sentinel


@pytest.mark.asyncio
async def test_get_session_manager_dep_does_not_use_stub_without_explicit_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", raising=False)

    sentinel = object()

    async def _fake_get_session_manager() -> object:
        return sentinel

    monkeypatch.setattr(auth_deps, "get_session_manager", _fake_get_session_manager)

    resolved = await auth_deps.get_session_manager_dep()
    assert resolved is sentinel


@pytest.mark.asyncio
async def test_get_db_transaction_requires_explicit_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MODE", "0")

    sentinel = object()

    class _TxnCM:
        async def __aenter__(self) -> object:
            return sentinel

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    class _Pool:
        def transaction(self) -> _TxnCM:
            return _TxnCM()

        def acquire(self) -> object:
            raise AssertionError("adapter path should not be used when TEST_MODE=0")

    async def _fake_get_db_pool() -> _Pool:
        return _Pool()

    monkeypatch.setattr(auth_deps, "get_db_pool", _fake_get_db_pool)

    agen = auth_deps.get_db_transaction()
    try:
        conn = await agen.__anext__()
        assert conn is sentinel
    finally:
        await agen.aclose()
