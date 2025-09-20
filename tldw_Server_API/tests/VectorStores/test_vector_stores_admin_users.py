import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Embeddings.vector_store_meta_db import init_meta_db, register_store
from tldw_Server_API.app.core.Embeddings.vector_store_batches_db import init_db as init_batches_db, _connect as batches_conn


@pytest.fixture(autouse=True)
def testing_env(monkeypatch, tmp_path):
    os.environ['TESTING'] = 'true'
    from tldw_Server_API.app.core import config as cfg
    monkeypatch.setitem(cfg.settings, 'USER_DB_BASE_DIR', tmp_path)
    yield
    os.environ.pop('TESTING', None)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_admin():
    async def override_user():
        return User(id=1, username='admin', email='a@e.com', is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as c:
        yield c


def test_admin_users_list(client_admin, tmp_path):
    # Prepare two users with meta/batch DBs
    base = tmp_path
    for uid in ['1','2']:
        init_meta_db(uid)
        register_store(uid, f"vs_{uid}_A", f"StoreA_{uid}")
        init_batches_db(uid)
        with batches_conn(uid) as conn:
            conn.execute("INSERT OR REPLACE INTO vector_store_batches (id, store_id, user_id, status, upserted, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                         (f"vsb_{uid}_1", f"vs_{uid}_A", uid, 'completed', 10, 0, 0))
            conn.commit()

    r = client_admin.get('/api/v1/vector_stores/admin/users')
    assert r.status_code == 200, r.text
    data = r.json()['data']
    # Expect at least two users
    got = {row['user_id'] for row in data}
    assert '1' in got and '2' in got
