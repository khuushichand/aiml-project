import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.endpoints.media import listing as listing_endpoint
from tldw_Server_API.app.core.config import API_V1_PREFIX


pytestmark = pytest.mark.integration


class _FakeMediaDB:
    def search_media_db(self, **_kwargs):
        return ([{"id": 1, "title": "Alpha", "type": "document"}], 1)


@pytest.fixture()
def media_search_client(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    app = FastAPI()
    app.include_router(listing_endpoint.router, prefix=f"{API_V1_PREFIX}/media")
    app.dependency_overrides[get_media_db_for_user] = lambda: _FakeMediaDB()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_media_search_accepts_minimal_payload(media_search_client):


    resp = media_search_client.post("/api/v1/media/search", json={"query": "Alpha"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body and isinstance(body["items"], list)
    assert "pagination" in body and isinstance(body["pagination"], dict)


def test_media_search_forbids_extra_keys(media_search_client):


    resp = media_search_client.post(
        "/api/v1/media/search",
        json={"query": "Alpha", "extra_key": True},
    )
    assert resp.status_code == 422


def test_media_search_rejects_bad_fields_type(media_search_client):


    resp = media_search_client.post(
        "/api/v1/media/search",
        json={"query": "Alpha", "fields": "title"},
    )
    assert resp.status_code == 422


def test_media_search_rejects_query_too_long(media_search_client):


    resp = media_search_client.post(
        "/api/v1/media/search",
        json={"query": "a" * 1001},
    )
    assert resp.status_code == 422
