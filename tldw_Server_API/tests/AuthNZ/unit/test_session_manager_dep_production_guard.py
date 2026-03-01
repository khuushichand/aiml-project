from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.api.v1.API_Deps import auth_deps


@pytest.mark.asyncio
async def test_session_manager_dep_uses_test_stub_in_non_production(monkeypatch: pytest.MonkeyPatch) -> None:
    marker = object()
    calls = {"real": 0}

    async def _real_session_manager():
        calls["real"] += 1
        return marker

    monkeypatch.setattr(auth_deps, "get_session_manager", _real_session_manager)
    monkeypatch.setattr(auth_deps, "_is_explicit_pytest_runtime", lambda: True)
    monkeypatch.setattr(auth_deps, "_is_production_like_env", lambda: False)
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.delenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", raising=False)

    resolved = await auth_deps.get_session_manager_dep()

    assert resolved is not marker
    assert calls["real"] == 0
    assert hasattr(resolved, "create_session")


@pytest.mark.asyncio
@pytest.mark.parametrize("allow_override", ["0", "1"])
async def test_session_manager_dep_never_uses_test_stub_in_production_like_env(
    monkeypatch: pytest.MonkeyPatch,
    allow_override: str,
) -> None:
    marker = object()
    calls = {"real": 0}

    async def _real_session_manager():
        calls["real"] += 1
        return marker

    monkeypatch.setattr(auth_deps, "get_session_manager", _real_session_manager)
    monkeypatch.setattr(auth_deps, "_is_explicit_pytest_runtime", lambda: True)
    monkeypatch.setattr(auth_deps, "_is_production_like_env", lambda: True)
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ALLOW_TEST_MODE_IN_PRODUCTION", allow_override)
    monkeypatch.delenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", raising=False)

    resolved = await auth_deps.get_session_manager_dep()

    assert resolved is marker
    assert calls["real"] == 1


@pytest.mark.asyncio
async def test_session_manager_dep_test_stub_create_session_accepts_expiry_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = object()
    calls = {"real": 0}

    async def _real_session_manager():
        calls["real"] += 1
        return marker

    monkeypatch.setattr(auth_deps, "get_session_manager", _real_session_manager)
    monkeypatch.setattr(auth_deps, "_is_explicit_pytest_runtime", lambda: True)
    monkeypatch.setattr(auth_deps, "_is_production_like_env", lambda: False)
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.delenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", raising=False)

    resolved = await auth_deps.get_session_manager_dep()

    assert resolved is not marker
    assert calls["real"] == 0

    access_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    refresh_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    access_value = f"access-{access_expiry.timestamp()}"
    refresh_value = f"refresh-{refresh_expiry.timestamp()}"
    session = await resolved.create_session(
        user_id=123,
        access_token=access_value,
        refresh_token=refresh_value,
        expires_at_override=access_expiry,
        refresh_expires_at_override=refresh_expiry,
    )

    assert session["expires_at"] == access_expiry
    assert session["refresh_expires_at"] == refresh_expiry
