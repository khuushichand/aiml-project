import os
import types
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


@pytest.fixture(autouse=True)
def testing_env(monkeypatch, tmp_path):
    os.environ['TESTING']='true'
    from tldw_Server_API.app.core import config as cfg
    monkeypatch.setitem(cfg.settings, 'USER_DB_BASE_DIR', tmp_path)
    yield
    os.environ.pop('TESTING', None)
    app.dependency_overrides.clear()


@pytest.fixture()
def client(monkeypatch):
    class FakeCol:
        def __init__(self):
            self.ids=[]; self.emb=[]; self.docs=[]; self.metas=[]
        def get(self, limit=100, offset=0, include=None, where=None):
            end = min(offset+limit, len(self.ids))
            idxs = list(range(offset, end))
            out = {'ids': [self.ids[i] for i in idxs]}
            if include:
                if 'documents' in include:
                    out['documents'] = [self.docs[i] for i in idxs]
                if 'metadatas' in include:
                    out['metadatas'] = [self.metas[i] for i in idxs]
            return out
        def count(self): return len(self.ids)
    class FakeAdapter:
        def __init__(self):
            self._initialized=False
            self.config=types.SimpleNamespace(embedding_dim=8)
            self.col = FakeCol()
            self.manager = types.SimpleNamespace(get_or_create_collection=lambda name: self.col)
        async def initialize(self): self._initialized=True
        async def get_collection_stats(self, name):
            return {'dimension': 8, 'metadata': {}}
        async def upsert_vectors(self, name, ids, vectors, documents, metadatas):
            self.col.ids += ids
            self.col.docs += documents
            self.col.metas += metadatas
        async def create_collection(self, name, metadata=None):
            if metadata:
                pass

    fake = FakeAdapter()
    import tldw_Server_API.app.api.v1.endpoints.vector_stores_openai as vs
    async def fake_adapter_for_user(user, embedding_dim):
        fake.config.embedding_dim = embedding_dim
        return fake
    monkeypatch.setattr(vs, '_adapter_for_user', fake_adapter_for_user)
    def fake_create_embeddings_batch(texts, app_config, model_id):
        return [[0.0]*fake.config.embedding_dim for _ in texts]
    monkeypatch.setattr(vs, 'create_embeddings_batch', fake_create_embeddings_batch)
    async def override_user():
        return User(id=1, username='tester', email='e', is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user]=override_user
    with TestClient(app) as c:
        yield c


def test_list_vectors_pagination(client):
    # Create store
    s = client.post('/api/v1/vector_stores', json={'name':'PStore','dimensions':8}).json()
    # Upsert 25 items
    records = [{'id':f'id{i}','values':[0.0]*8, 'content': f'doc{i}', 'metadata': {'i':i}} for i in range(25)]
    r = client.post(f"/api/v1/vector_stores/{s['id']}/vectors", json={'records': records})
    assert r.status_code == 200

    # Page 1
    r1 = client.get(f"/api/v1/vector_stores/{s['id']}/vectors", params={'limit':10,'offset':0})
    assert r1.status_code == 200
    data1 = r1.json()
    assert len(data1['data']) == 10
    assert data1['pagination']['total'] == 25
    assert data1['pagination']['next_offset'] == 10

    # Page 3
    r3 = client.get(f"/api/v1/vector_stores/{s['id']}/vectors", params={'limit':10,'offset':20})
    data3 = r3.json()
    assert len(data3['data']) == 5
    assert data3['pagination']['next_offset'] is None
