import pytest
from httpx import AsyncClient, ASGITransport
import sys, types

# Stub heavy modules before importing the full app
torch_stub = types.ModuleType("torch")
setattr(torch_stub, "__spec__", None)
sys.modules.setdefault('torch', torch_stub)

dill_stub = types.ModuleType("dill")
setattr(dill_stub, "__spec__", None)
sys.modules.setdefault('dill', dill_stub)


class _FakeConn:
    def execute(self, *args, **kwargs):
        return None
    def commit(self):
        return None


class _FakeDB:
    def __init__(self):
        self.last_filters = None
    def transaction(self):
        class _Tx:
            def __enter__(self_inner):
                return _FakeConn()
            def __exit__(self_inner, exc_type, exc, tb):
                return False
        return _Tx()
    def get_connection(self):
        return _FakeConn()
    def search_by_safe_metadata(self, filters=None, match_all=True, page=1, per_page=20, group_by_media=True):
        self.last_filters = filters
        return [], 0


@pytest.mark.asyncio
async def test_metadata_search_normalizes_doi(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user

    fake_db = _FakeDB()
    app.dependency_overrides[get_media_db_for_user] = lambda: fake_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/media/metadata-search",
            params={"field": "doi", "op": "eq", "value": "10.1234/ABC-123"},
        )
        assert r.status_code == 200
        assert fake_db.last_filters and fake_db.last_filters[0]["value"] == "10.1234/ABC-123"

    app.dependency_overrides.pop(get_media_db_for_user, None)


@pytest.mark.asyncio
async def test_metadata_search_invalid_doi_returns_400(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user

    fake_db = _FakeDB()
    app.dependency_overrides[get_media_db_for_user] = lambda: fake_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/media/metadata-search",
            params={"field": "doi", "op": "eq", "value": "bad"},
        )
        assert r.status_code == 400

    app.dependency_overrides.pop(get_media_db_for_user, None)


@pytest.mark.asyncio
async def test_by_identifier_invalid_doi_returns_400(monkeypatch):
    from tldw_Server_API.app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/media/by-identifier",
            params={"doi": "nope"},
        )
        assert r.status_code == 400
