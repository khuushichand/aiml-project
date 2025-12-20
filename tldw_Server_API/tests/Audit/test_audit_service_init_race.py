import asyncio

import pytest

from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps
from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService
from tldw_Server_API.app.core.config import settings


@pytest.mark.asyncio
async def test_init_timeout_does_not_duplicate_service(tmp_path, monkeypatch):
    monkeypatch.setitem(settings, "AUDIT_INIT_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path))

    started = asyncio.Event()
    release = asyncio.Event()
    calls = {"count": 0}

    async def _slow_create(user_id: int) -> UnifiedAuditService:
        calls["count"] += 1
        started.set()
        await release.wait()
        svc = UnifiedAuditService(db_path=str(tmp_path / f"audit_{user_id}.db"))
        await svc.initialize()
        return svc

    monkeypatch.setattr(audit_deps, "_create_audit_service_for_user", _slow_create)

    task = asyncio.create_task(audit_deps.get_or_create_audit_service_for_user_id(123))
    await asyncio.wait_for(started.wait(), timeout=1.0)

    try:
        with pytest.raises(RuntimeError):
            await audit_deps.get_or_create_audit_service_for_user_id(123)

        assert calls["count"] == 1
    finally:
        release.set()

    svc1 = await task
    svc2 = await audit_deps.get_or_create_audit_service_for_user_id(123)
    assert svc1 is svc2

    await audit_deps.shutdown_all_audit_services()
