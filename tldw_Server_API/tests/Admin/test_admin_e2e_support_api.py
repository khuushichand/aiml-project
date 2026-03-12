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
    jobs_db_path = tmp_path / 'jobs_with_e2e.db'
    backup_root = tmp_path / 'backups'
    user_db_base_dir = tmp_path / 'user_dbs'
    monkeypatch.setenv('AUTH_MODE', 'multi_user')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')
    monkeypatch.setenv('JOBS_DB_PATH', str(jobs_db_path))
    monkeypatch.setenv('JWT_SECRET_KEY', 'playwright-test-secret-1234567890')
    monkeypatch.setenv('JWT_ALGORITHM', 'HS256')
    monkeypatch.setenv('DEFER_HEAVY_STARTUP', 'true')
    monkeypatch.setenv('TEST_MODE', 'true')
    monkeypatch.setenv('ENABLE_ADMIN_E2E_TEST_MODE', 'true')
    monkeypatch.setenv('TLDW_DB_BACKUP_PATH', str(backup_root))
    monkeypatch.setenv('USER_DB_BASE_DIR', str(user_db_base_dir))

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


def test_admin_e2e_dsr_seed_supports_real_preview(e2e_client):
    seed = e2e_client.post(
        '/api/v1/test-support/admin-e2e/seed',
        json={'scenario': 'dsr_jwt_admin'},
    ).json()
    bootstrap = e2e_client.post(
        '/api/v1/test-support/admin-e2e/bootstrap-jwt-session',
        json={'principal_key': seed['users']['admin']['key']},
    ).json()
    access_token = next(
        cookie['value']
        for cookie in bootstrap['cookies']
        if cookie['name'] == 'access_token'
    )

    response = e2e_client.post(
        '/api/v1/admin/data-subject-requests/preview',
        headers={'Authorization': f'Bearer {access_token}'},
        json={'requester_identifier': seed['users']['requester']['email'], 'request_type': 'access'},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['resolved_user_id'] == seed['users']['requester']['id']
    assert payload['counts']['media_records'] > 0
    assert payload['counts']['chat_messages'] > 0
    assert payload['counts']['notes'] > 0
    assert payload['counts']['audit_events'] > 0


def test_admin_e2e_reset_clears_backup_schedules(e2e_client):
    seed = e2e_client.post(
        '/api/v1/test-support/admin-e2e/seed',
        json={'scenario': 'dsr_jwt_admin'},
    ).json()
    bootstrap = e2e_client.post(
        '/api/v1/test-support/admin-e2e/bootstrap-jwt-session',
        json={'principal_key': seed['users']['admin']['key']},
    ).json()
    access_token = next(
        cookie['value']
        for cookie in bootstrap['cookies']
        if cookie['name'] == 'access_token'
    )
    headers = {'Authorization': f'Bearer {access_token}'}

    create = e2e_client.post(
        '/api/v1/admin/backup-schedules',
        headers=headers,
        json={
            'dataset': 'media',
            'target_user_id': seed['users']['requester']['id'],
            'frequency': 'daily',
            'time_of_day': '02:00',
            'retention_count': 3,
        },
    )
    assert create.status_code == 200, create.text

    listed_before = e2e_client.get('/api/v1/admin/backup-schedules', headers=headers)
    assert listed_before.status_code == 200, listed_before.text
    assert listed_before.json()['total'] == 1

    reset = e2e_client.post('/api/v1/test-support/admin-e2e/reset')
    assert reset.status_code == 200, reset.text

    listed_after = e2e_client.get('/api/v1/admin/backup-schedules', headers=headers)
    assert listed_after.status_code == 200, listed_after.text
    assert listed_after.json()['total'] == 0


def test_admin_e2e_run_due_backup_schedules_processes_scheduled_run(e2e_client):
    seed = e2e_client.post(
        '/api/v1/test-support/admin-e2e/seed',
        json={'scenario': 'dsr_jwt_admin'},
    ).json()
    bootstrap = e2e_client.post(
        '/api/v1/test-support/admin-e2e/bootstrap-jwt-session',
        json={'principal_key': seed['users']['admin']['key']},
    ).json()
    access_token = next(
        cookie['value']
        for cookie in bootstrap['cookies']
        if cookie['name'] == 'access_token'
    )
    headers = {'Authorization': f'Bearer {access_token}'}

    create = e2e_client.post(
        '/api/v1/admin/backup-schedules',
        headers=headers,
        json={
            'dataset': 'media',
            'target_user_id': seed['users']['requester']['id'],
            'frequency': 'daily',
            'time_of_day': '02:00',
            'retention_count': 3,
        },
    )
    assert create.status_code == 200, create.text

    trigger = e2e_client.post('/api/v1/test-support/admin-e2e/run-due-backup-schedules')
    assert trigger.status_code == 200, trigger.text
    trigger_payload = trigger.json()
    assert trigger_payload['triggered_runs'] == 1

    listed = e2e_client.get('/api/v1/admin/backup-schedules', headers=headers)
    assert listed.status_code == 200, listed.text
    item = listed.json()['items'][0]
    assert item['last_status'] == 'succeeded'
    assert item['last_run_at']

    backups = e2e_client.get(
        '/api/v1/admin/backups',
        headers=headers,
        params={'dataset': 'media', 'user_id': seed['users']['requester']['id']},
    )
    assert backups.status_code == 200, backups.text
    assert backups.json()['items']
