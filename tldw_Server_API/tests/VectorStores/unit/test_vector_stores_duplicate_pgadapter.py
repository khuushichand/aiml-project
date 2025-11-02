import asyncio
import json
import pathlib
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


class FakeAdapter:
    def __init__(self, embedding_dim=8):
        self.config = type('cfg', (), {'embedding_dim': embedding_dim})()
        self.created = []
        self.upserts = []

    async def initialize(self):
        return None

    async def get_collection_stats(self, store_id):
        return {'dimension': self.config.embedding_dim, 'metadata': {}}

    async def create_collection(self, name, metadata=None):
        self.created.append((name, metadata or {}))

    async def list_vectors_with_embeddings_paginated(self, store_id, limit, offset, filter=None):
        items = []
        total = 3
        # two pages: 2 then 1
        if offset == 0:
            items = [
                {'id': 'v1', 'vector': [0.1]*self.config.embedding_dim, 'content': 'doc1', 'metadata': {'i':1}},
                {'id': 'v2', 'vector': [0.2]*self.config.embedding_dim, 'content': 'doc2', 'metadata': {'i':2}},
            ]
        elif offset == 2:
            items = [
                {'id': 'v3', 'vector': [0.3]*self.config.embedding_dim, 'content': 'doc3', 'metadata': {'i':3}},
            ]
        return {'items': items, 'total': total}

    async def upsert_vectors(self, dest_id, ids, vectors, documents, metadatas):
        self.upserts.append((dest_id, list(ids)))


@pytest.fixture(autouse=True)
def testing_env(monkeypatch, tmp_path):
    # Wire USER_DB_BASE_DIR for meta dbs used by endpoints
    from tldw_Server_API.app.core import config as cfg
    monkeypatch.setitem(cfg.settings, 'USER_DB_BASE_DIR', pathlib.Path(tmp_path))
    yield


@pytest.fixture()
def client(monkeypatch):
    async def override_user():
        return User(id=1, username='tester', email='t@e.com', is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user

    # Patch adapter factory in the endpoint module
    import tldw_Server_API.app.api.v1.endpoints.vector_stores_openai as vs
    async def _fake_get_adapter(user, dim):
        return FakeAdapter(embedding_dim=dim or 8)
    monkeypatch.setattr(vs, '_get_adapter_for_user', _fake_get_adapter)

    settings = get_settings()
    headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as test_client:
        try:
            yield test_client
        finally:
            app.dependency_overrides.pop(get_request_user, None)


@pytest.mark.unit
def test_duplicate_pg_adapter_flow(client):
    # Duplicate into a new store name
    r = client.post('/api/v1/vector_stores/vs_src/vectors', json={'records': []})
    # Create a destination via duplicate
    payload = {"new_name": "DupDest", "dimensions": 8}
    resp = client.post('/api/v1/vector_stores/vs_src/duplicate', json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data['destination_id']
    assert data['upserted'] == 3
