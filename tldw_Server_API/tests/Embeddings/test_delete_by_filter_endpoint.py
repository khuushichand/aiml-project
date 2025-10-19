from fastapi.testclient import TestClient
import pytest

from tldw_Server_API.app.main import app

pytestmark = pytest.mark.usefixtures("admin_user")


class _FakeAdapterDel:
    def __init__(self):
        self.called = 0
    async def initialize(self):
        return None
    async def delete_by_filter(self, store, f):
        self.called += 1
        return 3


def test_delete_by_filter_endpoint(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import vector_stores_openai as mod
    async def _fake_get_adapter_for_user(_user, _dim):
        return _FakeAdapterDel()
    monkeypatch.setenv('TEST_MODE','true')
    monkeypatch.setattr(mod, '_get_adapter_for_user', _fake_get_adapter_for_user)
    client = TestClient(app)
    r = client.post('/api/v1/vector_stores/vs_demo/admin/delete_by_filter', json={"filter": {"media_id":"42"}})
    assert r.status_code == 200
    assert r.json().get('deleted') == 3
