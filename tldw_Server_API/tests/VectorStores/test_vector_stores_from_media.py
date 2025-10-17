import os
import types
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.data = {'ids':[], 'embeddings':[], 'documents':[], 'metadatas':[]}
        self.metadata = {}
    def get(self, limit=100, offset=0, include=None, where=None):
        # simple where on media_id
        idxs = list(range(len(self.data['ids'])))
        if where and 'media_id' in where:
            mid = where['media_id']
            idxs = [i for i, m in enumerate(self.data['metadatas']) if m.get('media_id') == mid]
        end = min(offset+limit, len(idxs))
        sel = idxs[offset:end]
        out = {'ids': [self.data['ids'][i] for i in sel]}
        if include:
            if 'embeddings' in include:
                out['embeddings'] = [self.data['embeddings'][i] for i in sel]
            if 'documents' in include:
                out['documents'] = [self.data['documents'][i] for i in sel]
            if 'metadatas' in include:
                out['metadatas'] = [self.data['metadatas'][i] for i in sel]
        return out
    def count(self):
        return len(self.data['ids'])


class FakeAdapter:
    def __init__(self):
        self._initialized=False
        self.config = types.SimpleNamespace(embedding_dim=1536)
        self.collections={}
        self.manager = types.SimpleNamespace(get_or_create_collection=self.get_or_create_collection)
    async def initialize(self):
        self._initialized=True
    def get_or_create_collection(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]
    async def upsert_vectors(self, collection_name, ids, vectors, documents, metadatas):
        col = self.get_or_create_collection(collection_name)
        col.data['ids'] += ids
        col.data['embeddings'] += vectors
        col.data['documents'] += documents
        col.data['metadatas'] += metadatas
    async def create_collection(self, name, metadata=None):
        col = self.get_or_create_collection(name)
        if metadata:
            col.metadata.update(metadata)
    async def get_collection_stats(self, name):
        col = self.get_or_create_collection(name)
        dim = self.config.embedding_dim
        if col.data['embeddings']:
            dim = len(col.data['embeddings'][0])
        return {'metadata': getattr(col, 'metadata', {}), 'dimension': dim}


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
    fake = FakeAdapter()
    import tldw_Server_API.app.api.v1.endpoints.vector_stores_openai as vs
    async def fake_adapter_for_user(user, embedding_dim):
        fake.config.embedding_dim = embedding_dim
        return fake
    monkeypatch.setattr(vs, '_adapter_for_user', fake_adapter_for_user)
    # mock embeddings batch to fixed vectors
    def fake_create_embeddings_batch(texts, app_config, model_id):
        dim = 8
        return [[0.0]*dim for _ in texts]
    monkeypatch.setattr(vs, 'create_embeddings_batch', fake_create_embeddings_batch)
    # override user dep
    async def override_user():
        return User(id=1, username='tester', email='t@e.com', is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as c:
        yield c


def test_create_from_media_with_existing_embeddings(client):
    # create source collection embedding for media id 123
    # create destination store first
    dest = client.post('/api/v1/vector_stores', json={'name':'Dest','dimensions':8}).json()
    # populate source per-user media embeddings
    import tldw_Server_API.app.api.v1.endpoints.vector_stores_openai as vs
    adapter = pytest.MonkeyPatch().context()
    # Access our fake through adapter factory: get instance we created in fixture
    # easier: reconstruct expected collection name and populate via endpoint's fake adapter
    # We can reach fake through monkeypatch state, but here rebuild name and add using a new request path
    # Instead directly import and use _adapter_for_user
    # Retrieve adapter by calling our fake factory
    import asyncio
    fake_adapter = asyncio.run(vs._adapter_for_user(User(id=1, username='x', email='e', is_active=True, is_admin=True), 8))
    source = fake_adapter.get_or_create_collection('user_1_media_embeddings')
    source.data['ids'] = ['m123_c0']
    source.data['embeddings'] = [[0.0]*8]
    source.data['documents'] = ['doc']
    source.data['metadatas'] = [{'media_id':123}]

    body = {
        'store_name':'ignore',
        'dimensions':8,
        'media_ids':[123],
        'chunk_size':10,
        'chunk_overlap':0,
        'chunk_method':'words',
        'use_existing_embeddings': True,
        'update_existing_store_id': dest['id']
    }
    r = client.post('/api/v1/vector_stores/create_from_media', json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['store_id'] == dest['id']
    assert data['upserted'] == 1
