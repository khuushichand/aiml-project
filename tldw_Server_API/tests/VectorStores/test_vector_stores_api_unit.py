import os
import json
import types
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self._data = {
            'ids': [],
            'embeddings': [],
            'documents': [],
            'metadatas': []
        }
        self.metadata = {}

    def modify(self, metadata=None):
        if metadata:
            self.metadata.update(metadata)

    def get(self, limit=100, offset=0, include=None, where=None):
        # ignore where for unit tests
        end = min(offset + limit, len(self._data['ids']))
        idxs = list(range(offset, end))
        out = {}
        if include is None:
            include = []
        out['ids'] = [self._data['ids'][i] for i in idxs]
        if 'embeddings' in include:
            out['embeddings'] = [self._data['embeddings'][i] for i in idxs]
        if 'documents' in include:
            out['documents'] = [self._data['documents'][i] for i in idxs]
        if 'metadatas' in include:
            out['metadatas'] = [self._data['metadatas'][i] for i in idxs]
        return out

    def delete(self, ids=None):
        if not ids:
            return
        keep = [i for i, vid in enumerate(self._data['ids']) if vid not in ids]
        self._data['ids'] = [self._data['ids'][i] for i in keep]
        self._data['embeddings'] = [self._data['embeddings'][i] for i in keep]
        self._data['documents'] = [self._data['documents'][i] for i in keep]
        self._data['metadatas'] = [self._data['metadatas'][i] for i in keep]

    def count(self):
        return len(self._data['ids'])


class FakeAdapter:
    def __init__(self):
        self.config = types.SimpleNamespace(embedding_dim=1536)
        self._initialized = False
        self._collections = {}
        self.manager = types.SimpleNamespace(get_or_create_collection=self.get_or_create_collection)

    async def initialize(self):
        self._initialized = True

    async def list_collections(self):
        return list(self._collections.keys())

    async def get_collection_stats(self, name):
        col = self.get_or_create_collection(name)
        # dimension from stored any embedding
        dim = self.config.embedding_dim
        if col._data['embeddings']:
            dim = len(col._data['embeddings'][0])
        return {'name': name, 'dimension': dim, 'metadata': getattr(col, 'metadata', {})}

    async def upsert_vectors(self, collection_name, ids, vectors, documents, metadatas):
        col = self.get_or_create_collection(collection_name)
        col._data['ids'].extend(ids)
        col._data['embeddings'].extend(vectors)
        col._data['documents'].extend(documents)
        col._data['metadatas'].extend(metadatas)

    async def create_collection(self, name, metadata=None):
        col = self.get_or_create_collection(name)
        if metadata:
            col.metadata.update(metadata)

    async def delete_collection(self, name):
        if name in self._collections:
            del self._collections[name]

    def get_or_create_collection(self, name):
        if name not in self._collections:
            self._collections[name] = FakeCollection(name)
        return self._collections[name]


@pytest.fixture(autouse=True)
def testing_env(monkeypatch, tmp_path):
    os.environ['TESTING'] = 'true'
    # per-user DB base dir
    from tldw_Server_API.app.core import config as cfg
    monkeypatch.setitem(cfg.settings, 'USER_DB_BASE_DIR', tmp_path)
    yield
    os.environ.pop('TESTING', None)
    app.dependency_overrides.clear()


@pytest.fixture()
def client(monkeypatch):
    fake = FakeAdapter()

    # override adapter factory
    import tldw_Server_API.app.api.v1.endpoints.vector_stores_openai as vs
    async def fake_adapter_for_user(user, embedding_dim):
        fake.config.embedding_dim = embedding_dim
        return fake
    monkeypatch.setattr(vs, '_adapter_for_user', fake_adapter_for_user)

    # override user dep
    async def override_user():
        return User(id=1, username='tester', email='t@e.com', is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user

    with TestClient(app) as c:
        yield c


def test_create_store_and_uniqueness(client):
    # create A
    r1 = client.post('/api/v1/vector_stores', json={'name': 'Alpha', 'dimensions': 1536})
    assert r1.status_code == 200, r1.text
    # creating same name conflicts
    r2 = client.post('/api/v1/vector_stores', json={'name': 'alpha', 'dimensions': 1536})
    assert r2.status_code == 409


def test_rename_store_uniqueness(client):
    a = client.post('/api/v1/vector_stores', json={'name': 'A', 'dimensions': 1536}).json()
    b = client.post('/api/v1/vector_stores', json={'name': 'B', 'dimensions': 1536}).json()
    # rename B to A -> 409
    r = client.patch(f"/api/v1/vector_stores/{b['id']}", json={'name': 'A'})
    assert r.status_code == 409


def test_list_uses_meta_db(client):
    client.post('/api/v1/vector_stores', json={'name': 'One', 'dimensions': 1536})
    client.post('/api/v1/vector_stores', json={'name': 'Two', 'dimensions': 1536})
    r = client.get('/api/v1/vector_stores')
    assert r.status_code == 200
    names = [row['name'] for row in r.json()['data']]
    assert 'One' in names and 'Two' in names


def test_duplicate_store(client):
    src = client.post('/api/v1/vector_stores', json={'name': 'Src', 'dimensions': 4}).json()
    # insert a vector via upsert endpoint
    up = client.post(f"/api/v1/vector_stores/{src['id']}/vectors", json={'records':[{'id':'v1','values':[0,0,0,0],'content':'doc','metadata':{}}]})
    assert up.status_code == 200
    dup = client.post(f"/api/v1/vector_stores/{src['id']}/duplicate", json={'new_name': 'Copy'})
    assert dup.status_code == 200, dup.text
    data = dup.json()
    assert data['source_id'] == src['id']
    assert data['upserted'] == 1
