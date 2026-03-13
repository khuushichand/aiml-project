from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException


@dataclass
class _RecordingRepo:
    created_payload: dict | None = None

    async def has_active_execute_run(self) -> bool:
        return False

    async def create_run(self, **kwargs):
        self.created_payload = dict(kwargs)
        return {
            "id": "run-1",
            "mode": kwargs["mode"],
            "status": "queued",
            "domain": kwargs["domain"],
            "queue": kwargs["queue"],
            "job_type": kwargs["job_type"],
            "fields_json": kwargs["fields_json"],
            "limit": kwargs["limit"],
            "affected_count": None,
            "requested_by_user_id": kwargs["requested_by_user_id"],
            "requested_by_label": kwargs["requested_by_label"],
            "confirmation_recorded": kwargs["confirmation_recorded"],
            "job_id": None,
            "scope_summary": kwargs["scope_summary"],
            "key_source": kwargs["key_source"],
            "error_message": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
        }

    async def list_runs(self, *, limit: int, offset: int):
        return [], 0

    async def get_run(self, run_id: str):
        return None


@dataclass
class _ActiveExecuteRepo(_RecordingRepo):
    async def has_active_execute_run(self) -> bool:
        return True


@dataclass
class _DuplicateExecuteRepo(_RecordingRepo):
    async def create_run(self, **kwargs):
        raise RuntimeError("duplicate key value violates unique constraint idx_maintenance_rotation_runs_active_execute")


@pytest.mark.asyncio
async def test_create_dry_run_persists_scope_summary_and_key_source(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_maintenance_rotation_service import (
        AdminMaintenanceRotationService,
    )

    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_OLD_KEY", "old-key-material")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_NEW_KEY", "new-key-material")

    repo = _RecordingRepo()
    service = AdminMaintenanceRotationService(repo=repo)

    created = await service.create_run(
        mode="dry_run",
        domain="jobs",
        queue="default",
        job_type="encryption_rotation",
        fields=["payload", "result"],
        limit=250,
        confirmed=False,
        requested_by_user_id=7,
        requested_by_label="ops-admin@example.com",
    )

    assert created["mode"] == "dry_run"
    assert created["status"] == "queued"
    assert repo.created_payload is not None
    assert repo.created_payload["fields_json"] == '["payload","result"]'
    assert repo.created_payload["scope_summary"] == (
        "domain=jobs, queue=default, job_type=encryption_rotation, "
        "fields=payload,result, limit=250"
    )
    assert repo.created_payload["key_source"] == "env:jobs_crypto_rotate"
    assert repo.created_payload["confirmation_recorded"] is False


@pytest.mark.asyncio
async def test_create_execute_requires_confirmation(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_maintenance_rotation_service import (
        AdminMaintenanceRotationService,
    )

    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_OLD_KEY", "old-key-material")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_NEW_KEY", "new-key-material")

    service = AdminMaintenanceRotationService(repo=_RecordingRepo())

    with pytest.raises(HTTPException) as exc_info:
        await service.create_run(
            mode="execute",
            domain="jobs",
            queue="default",
            job_type="encryption_rotation",
            fields=["payload"],
            limit=100,
            confirmed=False,
            requested_by_user_id=7,
            requested_by_label="ops-admin@example.com",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "confirmation_required"


@pytest.mark.asyncio
async def test_create_run_rejects_when_rotation_key_source_is_unavailable(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_maintenance_rotation_service import (
        AdminMaintenanceRotationService,
    )

    monkeypatch.delenv("JOBS_CRYPTO_ROTATE_OLD_KEY", raising=False)
    monkeypatch.delenv("JOBS_CRYPTO_ROTATE_NEW_KEY", raising=False)

    service = AdminMaintenanceRotationService(repo=_RecordingRepo())

    with pytest.raises(HTTPException) as exc_info:
        await service.create_run(
            mode="dry_run",
            domain="jobs",
            queue="default",
            job_type="encryption_rotation",
            fields=["payload"],
            limit=100,
            confirmed=False,
            requested_by_user_id=7,
            requested_by_label="ops-admin@example.com",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "rotation_key_source_unavailable"


@pytest.mark.asyncio
async def test_create_execute_rejects_when_another_execute_run_is_active(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_maintenance_rotation_service import (
        AdminMaintenanceRotationService,
    )

    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_OLD_KEY", "old-key-material")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_NEW_KEY", "new-key-material")

    service = AdminMaintenanceRotationService(repo=_ActiveExecuteRepo())

    with pytest.raises(HTTPException) as exc_info:
        await service.create_run(
            mode="execute",
            domain="jobs",
            queue="default",
            job_type="encryption_rotation",
            fields=["payload"],
            limit=100,
            confirmed=True,
            requested_by_user_id=7,
            requested_by_label="ops-admin@example.com",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "active_execute_run_exists"


@pytest.mark.asyncio
async def test_create_execute_maps_unique_index_race_to_conflict(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_maintenance_rotation_service import (
        AdminMaintenanceRotationService,
    )

    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_OLD_KEY", "old-key-material")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_NEW_KEY", "new-key-material")

    service = AdminMaintenanceRotationService(repo=_DuplicateExecuteRepo())

    with pytest.raises(HTTPException) as exc_info:
        await service.create_run(
            mode="execute",
            domain="jobs",
            queue="default",
            job_type="encryption_rotation",
            fields=["payload"],
            limit=100,
            confirmed=True,
            requested_by_user_id=7,
            requested_by_label="ops-admin@example.com",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "active_execute_run_exists"


@pytest.mark.asyncio
async def test_create_run_normalizes_scope_before_persisting(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_maintenance_rotation_service import (
        AdminMaintenanceRotationService,
    )

    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_OLD_KEY", "old-key-material")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_NEW_KEY", "new-key-material")

    repo = _RecordingRepo()
    service = AdminMaintenanceRotationService(repo=repo)

    await service.create_run(
        mode="dry_run",
        domain=" jobs ",
        queue=" default ",
        job_type=" encryption_rotation ",
        fields=[" payload ", "result", "payload"],
        limit=10,
        confirmed=False,
        requested_by_user_id=3,
        requested_by_label="ops-admin@example.com",
    )

    assert repo.created_payload is not None
    assert repo.created_payload["domain"] == "jobs"
    assert repo.created_payload["queue"] == "default"
    assert repo.created_payload["job_type"] == "encryption_rotation"
    assert repo.created_payload["fields_json"] == '["payload","result"]'
