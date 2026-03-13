from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.main import app


def _setup_env(monkeypatch, *, user_db_base: str) -> None:
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "unit-test-api-key")
    monkeypatch.setenv("USER_DB_BASE_DIR", user_db_base)
    auth_db_path = Path(user_db_base).parent / "users_test_maintenance_rotation.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{auth_db_path}")
    monkeypatch.setenv("TEST_MODE", "true")


@dataclass
class _FakeRotationService:
    created_calls: list[dict] = field(default_factory=list)

    async def create_run(self, **kwargs):
        self.created_calls.append(dict(kwargs))
        if kwargs["mode"] == "execute" and not kwargs["confirmed"]:
            raise HTTPException(status_code=400, detail="confirmation_required")
        return {
            "id": "run-1",
            "mode": kwargs["mode"],
            "status": "queued",
            "domain": kwargs["domain"],
            "queue": kwargs["queue"],
            "job_type": kwargs["job_type"],
            "fields_json": "[\"payload\",\"result\"]",
            "limit": kwargs["limit"],
            "affected_count": None,
            "requested_by_user_id": kwargs["requested_by_user_id"],
            "requested_by_label": kwargs["requested_by_label"],
            "confirmation_recorded": kwargs["confirmed"],
            "job_id": None,
            "scope_summary": "domain=jobs, queue=default, job_type=encryption_rotation, fields=payload,result, limit=100",
            "key_source": "env:jobs_crypto_rotate",
            "error_message": None,
            "created_at": "2026-03-12T20:00:00+00:00",
            "started_at": None,
            "completed_at": None,
        }

    async def list_runs(self, *, limit: int, offset: int):
        return {
            "items": [
                {
                    "id": "run-1",
                    "mode": "dry_run",
                    "status": "complete",
                    "domain": "jobs",
                    "queue": "default",
                    "job_type": "encryption_rotation",
                    "fields_json": "[\"payload\",\"result\"]",
                    "limit": 100,
                    "affected_count": 42,
                    "requested_by_user_id": 1,
                    "requested_by_label": "ops-admin@example.com",
                    "confirmation_recorded": False,
                    "job_id": "job-1",
                    "scope_summary": "domain=jobs, queue=default, job_type=encryption_rotation, fields=payload,result, limit=100",
                    "key_source": "env:jobs_crypto_rotate",
                    "error_message": None,
                    "created_at": "2026-03-12T20:00:00+00:00",
                    "started_at": "2026-03-12T20:00:05+00:00",
                    "completed_at": "2026-03-12T20:00:15+00:00",
                }
            ],
            "total": 1,
            "limit": limit,
            "offset": offset,
        }

    async def get_run(self, run_id: str):
        if run_id != "run-1":
            return None
        return {
            "id": "run-1",
            "mode": "dry_run",
            "status": "complete",
            "domain": "jobs",
            "queue": "default",
            "job_type": "encryption_rotation",
            "fields_json": "[\"payload\",\"result\"]",
            "limit": 100,
            "affected_count": 42,
            "requested_by_user_id": 1,
            "requested_by_label": "ops-admin@example.com",
            "confirmation_recorded": False,
            "job_id": "job-1",
            "scope_summary": "domain=jobs, queue=default, job_type=encryption_rotation, fields=payload,result, limit=100",
            "key_source": "env:jobs_crypto_rotate",
            "error_message": None,
            "created_at": "2026-03-12T20:00:00+00:00",
            "started_at": "2026-03-12T20:00:05+00:00",
            "completed_at": "2026-03-12T20:00:15+00:00",
        }


@pytest.mark.asyncio
async def test_maintenance_rotation_create_list_and_detail_roundtrip(monkeypatch, tmp_path) -> None:
    _setup_env(monkeypatch, user_db_base=str(tmp_path / "user_dbs"))

    from tldw_Server_API.app.api.v1.endpoints.admin import admin_ops

    service = _FakeRotationService()
    app.dependency_overrides[admin_ops.get_admin_maintenance_rotation_service] = lambda: service

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}

    try:
        with TestClient(app, headers=headers) as client:
            create_resp = client.post(
                "/api/v1/admin/maintenance/rotation-runs",
                json={
                    "mode": "dry_run",
                    "domain": "jobs",
                    "queue": "default",
                    "job_type": "encryption_rotation",
                    "fields": ["payload", "result"],
                    "limit": 100,
                    "confirmed": False,
                },
            )
            assert create_resp.status_code == 200, create_resp.text
            created = create_resp.json()["item"]
            assert created["id"] == "run-1"
            assert service.created_calls[0]["domain"] == "jobs"

            list_resp = client.get("/api/v1/admin/maintenance/rotation-runs?limit=25&offset=0")
            assert list_resp.status_code == 200, list_resp.text
            listed = list_resp.json()
            assert listed["total"] == 1
            assert listed["items"][0]["id"] == "run-1"

            detail_resp = client.get("/api/v1/admin/maintenance/rotation-runs/run-1")
            assert detail_resp.status_code == 200, detail_resp.text
            assert detail_resp.json()["id"] == "run-1"
            assert detail_resp.json()["affected_count"] == 42
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_maintenance_rotation_execute_create_requires_confirmation(monkeypatch, tmp_path) -> None:
    _setup_env(monkeypatch, user_db_base=str(tmp_path / "user_dbs"))

    from tldw_Server_API.app.api.v1.endpoints.admin import admin_ops

    service = _FakeRotationService()
    app.dependency_overrides[admin_ops.get_admin_maintenance_rotation_service] = lambda: service

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}

    try:
        with TestClient(app, headers=headers) as client:
            response = client.post(
                "/api/v1/admin/maintenance/rotation-runs",
                json={
                    "mode": "execute",
                    "domain": "jobs",
                    "queue": "default",
                    "job_type": "encryption_rotation",
                    "fields": ["payload"],
                    "limit": 100,
                    "confirmed": False,
                },
            )
            assert response.status_code == 400, response.text
            assert response.json()["detail"] == "confirmation_required"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_maintenance_rotation_create_preserves_domain_scope_enforcement(
    monkeypatch,
    tmp_path,
) -> None:
    _setup_env(monkeypatch, user_db_base=str(tmp_path / "user_dbs"))

    from tldw_Server_API.app.api.v1.endpoints.admin import admin_ops

    principal = AuthPrincipal(
        kind="user",
        user_id=41,
        subject="user:41",
        roles=["admin"],
        is_admin=True,
    )

    def _fake_scope_check(*args, **kwargs):
        raise HTTPException(status_code=403, detail="Not authorized for this domain")

    service = _FakeRotationService()
    app.dependency_overrides[get_auth_principal] = lambda: principal
    app.dependency_overrides[admin_ops.get_admin_maintenance_rotation_service] = lambda: service
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.admin.admin_ops._enforce_domain_scope_unified",
        _fake_scope_check,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/admin/maintenance/rotation-runs",
                json={
                    "mode": "dry_run",
                    "domain": "jobs",
                    "queue": "default",
                    "job_type": "encryption_rotation",
                    "fields": ["payload"],
                    "limit": 100,
                    "confirmed": False,
                },
            )
            assert response.status_code == 403, response.text
            assert response.json()["detail"] == "Not authorized for this domain"
    finally:
        app.dependency_overrides.clear()
