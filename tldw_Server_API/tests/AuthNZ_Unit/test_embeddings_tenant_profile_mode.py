import os

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import (
    router as embeddings_router,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


def _make_app():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(embeddings_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_tenant_quotas_respects_profile_flag_over_mode(monkeypatch):
    """
    Ensure get_tenant_quotas uses PROFILE when set, but preserves the existing
    single-user AUTH_MODE behavior when PROFILE is unset.
    """
    # Force multi_user mode but PROFILE=single_user to simulate a desktop profile.
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("PROFILE", "single_user")
    monkeypatch.setenv("EMBEDDINGS_TENANT_RPS", "5")

    # Provide a simple get_request_user override so the dependency succeeds.
    async def _fake_get_request_user():
        return User(id=1, username="tester", is_active=True)

    from fastapi import FastAPI

    app = _make_app()
    app.dependency_overrides[get_request_user] = _fake_get_request_user

    with TestClient(app) as client:
        resp = client.get("/api/v1/embeddings/tenant/quotas")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    # PROFILE=single_user should disable tenant quotas regardless of AUTH_MODE.
    assert data["limit_rps"] == 0
    assert data["remaining"] is None


@pytest.mark.asyncio
async def test_tenant_quotas_falls_back_to_mode_when_profile_unset(monkeypatch):
    """
    When PROFILE is unset, behavior should match the legacy mode-based guard.
    """
    # Explicitly clear PROFILE and drive via AUTH_MODE.
    monkeypatch.delenv("PROFILE", raising=False)
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("EMBEDDINGS_TENANT_RPS", "5")

    async def _fake_get_request_user():
        return User(id=1, username="tester", is_active=True)

    app = _make_app()
    app.dependency_overrides[get_request_user] = _fake_get_request_user

    with TestClient(app) as client:
        resp = client.get("/api/v1/embeddings/tenant/quotas")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Legacy behavior: single_user AUTH_MODE disables tenant quotas.
    assert data["limit_rps"] == 0
    assert data["remaining"] is None


@pytest.mark.asyncio
async def test_tenant_quotas_local_single_user_profile(monkeypatch):
    """
    Explicit PROFILE=local-single-user should behave like single-user mode for
    tenant quotas, even when AUTH_MODE is multi_user.
    """
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("PROFILE", "local-single-user")
    monkeypatch.setenv("EMBEDDINGS_TENANT_RPS", "5")

    async def _fake_get_request_user():
        return User(id=1, username="tester", is_active=True)

    app = _make_app()
    app.dependency_overrides[get_request_user] = _fake_get_request_user

    with TestClient(app) as client:
        resp = client.get("/api/v1/embeddings/tenant/quotas")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    # PROFILE=local-single-user should disable tenant quotas.
    assert data["limit_rps"] == 0
    assert data["remaining"] is None
