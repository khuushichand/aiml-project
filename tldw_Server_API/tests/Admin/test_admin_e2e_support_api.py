from __future__ import annotations

import importlib

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Audit.unified_audit_service import shutdown_audit_service
from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.DB_Management.Users_DB import reset_users_db
from tldw_Server_API.app.services.registration_service import reset_registration_service


async def _reset_auth_runtime() -> None:
    await reset_db_pool()
    await reset_session_manager()
    reset_settings()
    await reset_registration_service()
    await shutdown_audit_service()
    await reset_users_db()


@pytest_asyncio.fixture
async def client_without_e2e_support(tmp_path, monkeypatch):
    db_path = tmp_path / 'authnz_no_e2e.db'
    monkeypatch.setenv('AUTH_MODE', 'multi_user')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')
    monkeypatch.setenv('JWT_SECRET_KEY', 'playwright-test-secret-1234567890')
    monkeypatch.setenv('JWT_ALGORITHM', 'HS256')
    monkeypatch.setenv('DEFER_HEAVY_STARTUP', 'true')
    monkeypatch.setenv('TEST_MODE', 'true')
    monkeypatch.delenv('ENABLE_ADMIN_E2E_TEST_MODE', raising=False)

    await _reset_auth_runtime()

    import tldw_Server_API.app.main as app_main

    app = importlib.reload(app_main).app
    with TestClient(app) as client:
        yield client

    await _reset_auth_runtime()


@pytest_asyncio.fixture
async def e2e_client(tmp_path, monkeypatch):
    db_path = tmp_path / 'authnz_with_e2e.db'
    monkeypatch.setenv('AUTH_MODE', 'multi_user')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')
    monkeypatch.setenv('JWT_SECRET_KEY', 'playwright-test-secret-1234567890')
    monkeypatch.setenv('JWT_ALGORITHM', 'HS256')
    monkeypatch.setenv('DEFER_HEAVY_STARTUP', 'true')
    monkeypatch.setenv('TEST_MODE', 'true')
    monkeypatch.setenv('ENABLE_ADMIN_E2E_TEST_MODE', 'true')

    await _reset_auth_runtime()

    import tldw_Server_API.app.main as app_main

    app = importlib.reload(app_main).app
    with TestClient(app) as client:
        yield client

    await _reset_auth_runtime()


def test_admin_e2e_routes_are_unavailable_without_flag(client_without_e2e_support):
    response = client_without_e2e_support.post('/api/v1/test-support/admin-e2e/reset')
    assert response.status_code == 404


def test_admin_e2e_seed_returns_stable_fixture_ids(e2e_client):
    response = e2e_client.post(
        '/api/v1/test-support/admin-e2e/seed',
        json={'scenario': 'dsr_jwt_admin'},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['users']['admin']['id']
    assert payload['users']['admin']['key']
    assert payload['fixtures']['alerts'][0]['alert_id']


def test_admin_e2e_bootstrap_jwt_session_returns_cookie_payload(e2e_client):
    seed = e2e_client.post(
        '/api/v1/test-support/admin-e2e/seed',
        json={'scenario': 'jwt_admin'},
    ).json()
    response = e2e_client.post(
        '/api/v1/test-support/admin-e2e/bootstrap-jwt-session',
        json={'principal_key': seed['users']['admin']['key']},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['cookies'][0]['name'] == 'access_token'
