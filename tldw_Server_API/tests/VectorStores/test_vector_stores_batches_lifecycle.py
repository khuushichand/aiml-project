import os
import types
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


@pytest.fixture(autouse=True)
def testing_env(monkeypatch, tmp_path):
    os.environ['TESTING'] = 'true'
    from tldw_Server_API.app.core import config as cfg
    monkeypatch.setitem(cfg.settings, 'USER_DB_BASE_DIR', tmp_path)
    yield
    os.environ.pop('TESTING', None)
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    async def override_user():
        return User(id=1, username='tester', email='e', is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as c:
        yield c


def test_batch_lifecycle_success(client):
    s = client.post('/api/v1/vector_stores', json={'name':'BStore','dimensions':8}).json()
    # Start batch via endpoint
    payload = {'records': [{'id':'a','values':[0.0]*8,'content':'x','metadata':{'k':1}}]}
    rb = client.post(f"/api/v1/vector_stores/{s['id']}/vectors/batches", json=payload)
    assert rb.status_code == 200, rb.text
    data = rb.json()
    assert data['status'] in ('processing','completed','failed')
    # List batches
    lst_resp = client.get('/api/v1/vector_stores/batches')
    assert lst_resp.status_code == 200, lst_resp.text
    lst = lst_resp.json()
    assert 'data' in lst and isinstance(lst['data'], list)
    assert any(isinstance(row, dict) for row in lst['data'])


def test_batch_lifecycle_failure(client):
    s = client.post('/api/v1/vector_stores', json={'name':'BStore2','dimensions':8}).json()
    # Seed correct to lock dimension, then wrong dimension to force error
    ok = {'records': [{'id':'seed','values':[0.0]*8,'content':'seed','metadata':{'k':1}}]}
    client.post(f"/api/v1/vector_stores/{s['id']}/vectors", json=ok)
    bad = {'records': [{'id':'a','values':[0.0]*7,'content':'x','metadata':{'k':1}}]}
    rb = client.post(f"/api/v1/vector_stores/{s['id']}/vectors/batches", json=bad)
    assert rb.status_code >= 400
    # List batches: should include a failed row
    lst_resp = client.get('/api/v1/vector_stores/batches')
    assert lst_resp.status_code == 200, lst_resp.text
    lst = lst_resp.json()
    assert any(row.get('status')=='failed' for row in lst.get('data', []))
