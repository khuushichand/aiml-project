from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.exceptions import (
    ByokValidationActiveRunError,
    ByokValidationDisabledError,
    ByokValidationRunNotFoundError,
)


@dataclass
class _RecordingRepo:
    created_payload: dict | None = None

    async def has_active_run(self) -> bool:
        return False

    async def create_run(self, **kwargs):
        self.created_payload = dict(kwargs)
        return {
            "id": "run-1",
            "status": "queued",
            "org_id": kwargs["org_id"],
            "provider": kwargs["provider"],
            "keys_checked": None,
            "valid_count": None,
            "invalid_count": None,
            "error_count": None,
            "requested_by_user_id": kwargs["requested_by_user_id"],
            "requested_by_label": kwargs["requested_by_label"],
            "job_id": None,
            "scope_summary": kwargs["scope_summary"],
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
class _ActiveRunRepo(_RecordingRepo):
    async def has_active_run(self) -> bool:
        return True


@dataclass
class _DuplicateRunRepo(_RecordingRepo):
    async def create_run(self, **kwargs):
        raise RuntimeError("duplicate key value violates unique constraint idx_byok_validation_runs_active")


def _platform_admin_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=7,
        username="ops-admin",
        email="ops-admin@example.com",
        roles=["admin"],
        permissions=["*"],
        is_admin=True,
    )


@pytest.mark.asyncio
async def test_create_validation_run_persists_scope_summary(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_byok_validation_service import (
        AdminByokValidationService,
    )

    repo = _RecordingRepo()
    service = AdminByokValidationService(repo=repo)
    principal = _platform_admin_principal()

    monkeypatch.setattr(
        "tldw_Server_API.app.services.admin_byok_validation_service.is_byok_enabled",
        lambda: True,
    )

    created = await service.create_run(
        principal,
        org_id=42,
        provider=" OpenAI ",
    )

    assert created["status"] == "queued"
    assert repo.created_payload is not None
    assert repo.created_payload["org_id"] == 42
    assert repo.created_payload["provider"] == "openai"
    assert repo.created_payload["requested_by_user_id"] == 7
    assert repo.created_payload["requested_by_label"] == "ops-admin@example.com"
    assert repo.created_payload["scope_summary"] == "org=42, provider=openai"


@pytest.mark.asyncio
async def test_create_validation_run_rejects_when_byok_disabled(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_byok_validation_service import (
        AdminByokValidationService,
    )

    service = AdminByokValidationService(repo=_RecordingRepo())

    monkeypatch.setattr(
        "tldw_Server_API.app.services.admin_byok_validation_service.is_byok_enabled",
        lambda: False,
    )

    with pytest.raises(ByokValidationDisabledError) as exc_info:
        await service.create_run(_platform_admin_principal(), org_id=42, provider="openai")

    assert str(exc_info.value) == "BYOK is disabled in this deployment"


@pytest.mark.asyncio
async def test_create_validation_run_enforces_org_scope(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_byok_validation_service import (
        AdminByokValidationService,
    )

    calls: list[int] = []

    async def _record_org_access(principal, org_id: int, *, require_admin: bool = True) -> None:
        calls.append(org_id)
        assert require_admin is True

    monkeypatch.setattr(
        "tldw_Server_API.app.services.admin_byok_validation_service.is_byok_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.services.admin_byok_validation_service.admin_scope_service.enforce_admin_org_access",
        _record_org_access,
    )

    service = AdminByokValidationService(repo=_RecordingRepo())
    await service.create_run(_platform_admin_principal(), org_id=42, provider="openai")

    assert calls == [42]


@pytest.mark.asyncio
async def test_create_validation_run_rejects_when_another_run_is_active(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_byok_validation_service import (
        AdminByokValidationService,
    )

    monkeypatch.setattr(
        "tldw_Server_API.app.services.admin_byok_validation_service.is_byok_enabled",
        lambda: True,
    )

    service = AdminByokValidationService(repo=_ActiveRunRepo())

    with pytest.raises(ByokValidationActiveRunError) as exc_info:
        await service.create_run(_platform_admin_principal(), org_id=42, provider="openai")

    assert str(exc_info.value) == "active_validation_run_exists"


@pytest.mark.asyncio
async def test_create_validation_run_maps_unique_index_race_to_conflict(monkeypatch) -> None:
    from tldw_Server_API.app.services.admin_byok_validation_service import (
        AdminByokValidationService,
    )

    monkeypatch.setattr(
        "tldw_Server_API.app.services.admin_byok_validation_service.is_byok_enabled",
        lambda: True,
    )

    service = AdminByokValidationService(repo=_DuplicateRunRepo())

    with pytest.raises(ByokValidationActiveRunError) as exc_info:
        await service.create_run(_platform_admin_principal(), org_id=42, provider="openai")

    assert str(exc_info.value) == "active_validation_run_exists"


@pytest.mark.asyncio
async def test_get_run_raises_not_found_when_missing() -> None:
    from tldw_Server_API.app.services.admin_byok_validation_service import (
        AdminByokValidationService,
    )

    service = AdminByokValidationService(repo=_RecordingRepo())

    with pytest.raises(ByokValidationRunNotFoundError) as exc_info:
        await service.get_run("missing-run")

    assert str(exc_info.value) == "byok_validation_run_not_found"
