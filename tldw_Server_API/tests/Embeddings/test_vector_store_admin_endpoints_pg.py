from fastapi.testclient import TestClient
import pytest

from tldw_Server_API.app.main import app

pytestmark = pytest.mark.usefixtures("admin_user")


class _FakeAdapterWithIndex:
    def __init__(self):
        self.set_val = None
    async def initialize(self):
        return None
    async def get_index_info(self, store):
        return {"backend":"pgvector","index_type":"hnsw","count":0,"dimension":8}
    def set_ef_search(self, v: int) -> int:
        self.set_val = int(v)
        return self.set_val
    async def rebuild_index(self, store, index_type: str, metric=None, m=16, ef_construction=200, lists=100):
        return {"backend":"pgvector","index_type":index_type,"ops":"vector_cosine_ops"}


class _FakeAdapterNoIndex:
    async def initialize(self):
        return None


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    monkeypatch.setenv('TEST_MODE','true')


def test_admin_set_ef_search_happy(monkeypatch):
    # Patch adapter factory path
    from tldw_Server_API.app.api.v1.endpoints import vector_stores_openai as mod
    async def _fake_get_adapter_for_user(_user, _dim):
        return _FakeAdapterWithIndex()
    monkeypatch.setattr(mod, '_get_adapter_for_user', _fake_get_adapter_for_user)

    client = TestClient(app)
    r = client.post('/api/v1/vector_stores/admin/hnsw_ef_search', json={"ef_search": 123})
    assert r.status_code == 200
    assert r.json().get('ef_search') == 123


def test_admin_rebuild_index_happy(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import vector_stores_openai as mod
    async def _fake_get_adapter_for_user(_user, _dim):
        return _FakeAdapterWithIndex()
    monkeypatch.setattr(mod, '_get_adapter_for_user', _fake_get_adapter_for_user)
    client = TestClient(app)
    r = client.post('/api/v1/vector_stores/vs_demo/admin/rebuild_index', json={"index_type":"hnsw","metric":"cosine","m":16,"ef_construction":200,"lists":100})
    assert r.status_code == 200
    body = r.json()
    assert body.get('backend') == 'pgvector'
    assert body.get('index_type') == 'hnsw'


def test_admin_rebuild_index_not_supported(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import vector_stores_openai as mod
    async def _fake_get_adapter_for_user(_user, _dim):
        return _FakeAdapterNoIndex()
    monkeypatch.setattr(mod, '_get_adapter_for_user', _fake_get_adapter_for_user)
    client = TestClient(app)
    r = client.post('/api/v1/vector_stores/vs_demo/admin/rebuild_index', json={"index_type":"hnsw"})
    assert r.status_code == 400
    assert 'not supported' in r.json().get('detail','').lower()
