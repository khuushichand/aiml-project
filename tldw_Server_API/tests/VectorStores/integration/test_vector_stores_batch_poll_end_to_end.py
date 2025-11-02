import os
import time
import pathlib
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def testing_env(monkeypatch, tmp_path):
    os.environ['TESTING'] = 'true'
    from tldw_Server_API.app.core import config as cfg
    monkeypatch.setitem(cfg.settings, 'USER_DB_BASE_DIR', pathlib.Path(tmp_path))
    yield
    os.environ.pop('TESTING', None)
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    async def override_user():
        return User(id=1, username='tester', email='t@e.com', is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user
    settings = get_settings()
    headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
    return TestClient(app, headers=headers)


def test_batch_upsert_then_poll_to_completion(client: TestClient):
    # Create store
    r = client.post('/api/v1/vector_stores', json={'name': 'BatchPoll', 'dimensions': 8})
    assert r.status_code == 200, r.text
    sid = r.json()['id']

    # Start batch upsert with explicit vectors
    payload = {
        'records': [
            {'id': 'bp1', 'values': [0.1]*8, 'content': 'one', 'metadata': {'i': 1}},
            {'id': 'bp2', 'values': [0.2]*8, 'content': 'two', 'metadata': {'i': 2}},
        ]
    }
    b = client.post(f"/api/v1/vector_stores/{sid}/vectors/batches", json=payload)
    assert b.status_code == 200, b.text
    batch = b.json(); bid = batch.get('id')
    assert bid and batch.get('status') in ('processing','completed','failed')

    # Poll until completed/failed or timeout
    deadline = time.time() + 5.0
    status = batch.get('status')
    while status not in ('completed', 'failed') and time.time() < deadline:
        g = client.get(f"/api/v1/vector_stores/{sid}/vectors/batches/{bid}")
        if g.status_code != 200:
            time.sleep(0.05)
            continue
        status = g.json().get('status')
        if status in ('completed', 'failed'):
            break
        time.sleep(0.05)

    assert status in ('completed', 'failed')
    if status == 'completed':
        # On completion, upserted should be >= number of records
        g = client.get(f"/api/v1/vector_stores/{sid}/vectors/batches/{bid}")
        assert g.status_code == 200
        assert g.json().get('upserted', 0) >= 2
