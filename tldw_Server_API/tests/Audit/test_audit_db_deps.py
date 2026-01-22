import asyncio
import time

import pytest

from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as deps
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.exceptions import ServiceInitializationError


class _DummyService:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._tldw_stop_scheduled = False
        self._last_used_ts = time.monotonic() - 10.0
        self._tldw_evicted_at = None

    @property
    def owner_loop(self):
        return self._loop

    async def stop(self) -> None:
        raise RuntimeError("stop failed")


@pytest.mark.asyncio
async def test_get_audit_service_for_user_accepts_string_id(monkeypatch):
    sentinel = object()
    called = {}

    async def _fake_get_or_create(user_id: int):
        called["user_id"] = user_id
        return sentinel

    async def _fake_default():
        raise AssertionError("default audit service should not be used for numeric string ids")

    monkeypatch.setattr(deps, "get_or_create_audit_service_for_user_id", _fake_get_or_create)
    monkeypatch.setattr(deps, "get_or_create_default_audit_service", _fake_default)

    user = User(id="42", username="tester", email=None, is_active=True)
    svc = await deps.get_audit_service_for_user(user)

    assert svc is sentinel
    assert called["user_id"] == 42


@pytest.mark.asyncio
async def test_get_audit_service_for_user_uses_raw_non_numeric_id_in_tests(monkeypatch):
    sentinel = object()
    called = {}

    async def _fake_optional(user_id):
        called["user_id"] = user_id
        return sentinel

    monkeypatch.setattr(deps, "get_or_create_audit_service_for_user_id_optional", _fake_optional)

    user = User(id="tenant-alpha", username="tester", email=None, is_active=True)
    svc = await deps.get_audit_service_for_user(user)

    assert svc is sentinel
    assert called["user_id"] == "tenant-alpha"


@pytest.mark.asyncio
async def test_optional_audit_service_rejects_non_numeric_outside_tests(monkeypatch):
    monkeypatch.setattr(deps, "_is_test_context", lambda: False)

    async def _fake_get_or_create(_key):
        raise AssertionError("Should not create audit service for invalid non-numeric id")

    monkeypatch.setattr(deps, "_get_or_create_audit_service_for_key", _fake_get_or_create)

    with pytest.raises(ServiceInitializationError):
        await deps.get_or_create_audit_service_for_user_id_optional("tenant-alpha")


@pytest.mark.asyncio
async def test_schedule_service_stop_clears_flag_on_failure(monkeypatch):
    deps._services_stopping.clear()
    monkeypatch.setattr(deps, "EVICTION_GRACE_SECONDS", 0.0)

    loop = asyncio.get_running_loop()
    svc = _DummyService(loop)

    deps._schedule_service_stop(1, svc, "test")

    for _ in range(20):
        await asyncio.sleep(0)
        if not getattr(svc, "_tldw_stop_scheduled", True):
            break

    assert svc._tldw_stop_scheduled is False
    assert id(svc) not in deps._services_stopping


@pytest.mark.asyncio
async def test_optional_audit_service_accepts_non_numeric_in_tests(monkeypatch):
    sentinel = object()
    called = {}

    async def _fake_get_or_create(key):
        called["key"] = key
        return sentinel

    monkeypatch.setattr(deps, "_get_or_create_audit_service_for_key", _fake_get_or_create)
    monkeypatch.setattr(deps, "_is_test_context", lambda: True)

    svc = await deps.get_or_create_audit_service_for_user_id_optional("tenant-alpha")

    assert svc is sentinel
    assert called["key"] == "tenant-alpha"
