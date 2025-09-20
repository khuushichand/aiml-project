import os
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings as hyp_settings, strategies as st, HealthCheck
import uuid

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
def client(monkeypatch):
    # Use in-memory fake adapter to avoid filesystem DB in property tests
    class FakeCol:
        def __init__(self):
            self.ids=[]; self.emb=[]; self.docs=[]; self.metas=[]
        def count(self): return len(self.ids)
        def get(self, **kw): return {'ids': self.ids[:1]}
    class FakeAdapter:
        def __init__(self):
            self._initialized=False
            self.config=types.SimpleNamespace(embedding_dim=1536)
            self.col = FakeCol()
            self.manager = types.SimpleNamespace(get_or_create_collection=lambda name: self.col)
        async def initialize(self): self._initialized=True
        async def get_collection_stats(self, name):
            dim = self.config.embedding_dim
            if self.col.emb:
                dim = len(self.col.emb[0])
            return {'dimension': dim, 'metadata': {}}
        async def upsert_vectors(self, name, ids, vectors, documents, metadatas):
            self.col.ids += ids
            self.col.emb += vectors
            self.col.docs += documents
            self.col.metas += metadatas
        async def create_collection(self, name, metadata=None):
            if metadata:
                pass
    import types
    fake = FakeAdapter()
    import tldw_Server_API.app.api.v1.endpoints.vector_stores_openai as vs
    async def fake_adapter_for_user(user, embedding_dim):
        fake.config.embedding_dim = embedding_dim
        return fake
    monkeypatch.setattr(vs, '_adapter_for_user', fake_adapter_for_user)

    async def override_user():
        return User(id=1, username='tester', email='t@e.com', is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as c:
        yield c


def make_store(client, name, dim):
    r = client.post('/api/v1/vector_stores', json={'name': name, 'dimensions': dim})
    assert r.status_code == 200, r.text
    return r.json()['id']


@hyp_settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    dim=st.integers(min_value=4, max_value=64),
    num=st.integers(min_value=1, max_value=5),
)
def test_upsert_accepts_correct_dimension(client, dim, num):
    unique = uuid.uuid4().hex[:8]
    store_id = make_store(client, f"S{dim}_{num}_{unique}", dim)
    records = []
    for i in range(num):
        records.append({'id': f'v{i}', 'values': [0.0]*dim, 'content': f'doc {i}', 'metadata': {'i': i}})
    r = client.post(f"/api/v1/vector_stores/{store_id}/vectors", json={'records': records})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out['upserted'] == num


@hyp_settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    good_dim=st.integers(min_value=4, max_value=32),
    bad_dim=st.integers(min_value=2, max_value=8)
)
def test_upsert_rejects_wrong_dimension(client, good_dim, bad_dim):
    if bad_dim == good_dim:
        bad_dim = good_dim + 1
    unique = uuid.uuid4().hex[:6]
    store_id = make_store(client, f"Reject_{good_dim}_{unique}", good_dim)
    # Seed correct vector to set dimension, then try wrong-size vector
    ok = [{'id':'ok','values':[0.0]*good_dim, 'content':'ok', 'metadata': {'k':1}}]
    r0 = client.post(f"/api/v1/vector_stores/{store_id}/vectors", json={'records': ok})
    assert r0.status_code == 200
    bad = [{'id':'x','values':[0.0]*bad_dim, 'content':'bad', 'metadata': {'k':1}}]
    r = client.post(f"/api/v1/vector_stores/{store_id}/vectors", json={'records': bad})
    assert r.status_code in (400, 422)


def test_upsert_infers_dim_on_empty_collection(client):
    # Create with default dim but first vector provides 7 -> should adapt
    unique = uuid.uuid4().hex[:6]
    store_id = make_store(client, f"Infer_{unique}", 1536)
    r = client.post(f"/api/v1/vector_stores/{store_id}/vectors", json={'records': [{'id':'a','values':[0.0]*7, 'content':'x', 'metadata': {'k':1}}]})
    assert r.status_code == 200, r.text
