import os
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


def test_admin_users_403_for_non_admin():
    async def override_user():
        return User(id=3, username='user', email='u@e.com', is_active=True, is_admin=False)
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        r = client.get('/api/v1/vector_stores/admin/users')
    assert r.status_code == 403
