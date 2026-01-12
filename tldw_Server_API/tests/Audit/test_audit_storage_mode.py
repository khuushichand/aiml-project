from pathlib import Path

import pytest

from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


@pytest.mark.asyncio
async def test_shared_mode_uses_shared_service(tmp_path, monkeypatch):
    monkeypatch.setitem(settings, "AUDIT_STORAGE_MODE", "shared")
    monkeypatch.setitem(settings, "AUDIT_STORAGE_ROLLBACK", False)
    shared_path = tmp_path / "audit_shared.db"
    monkeypatch.setitem(settings, "AUDIT_SHARED_DB_PATH", str(shared_path))
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    try:
        svc1 = await audit_deps.get_or_create_audit_service_for_user_id(1)
        svc2 = await audit_deps.get_or_create_audit_service_for_user_id(2)

        assert svc1 is svc2
        assert Path(svc1.db_path) == shared_path.resolve()
    finally:
        await audit_deps.shutdown_all_audit_services()


@pytest.mark.asyncio
async def test_storage_rollback_forces_per_user(tmp_path, monkeypatch):
    monkeypatch.setitem(settings, "AUDIT_STORAGE_MODE", "shared")
    monkeypatch.setitem(settings, "AUDIT_STORAGE_ROLLBACK", True)
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    user_id = 42
    expected = DatabasePaths.get_audit_db_path(user_id)

    try:
        svc = await audit_deps.get_or_create_audit_service_for_user_id(user_id)
        assert svc.db_path == expected
    finally:
        await audit_deps.shutdown_all_audit_services()
