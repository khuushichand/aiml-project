import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


def _non_admin_user():
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=7, username="user", email="u@x", is_active=True, is_admin=False)
    return _f


@pytest.mark.unit
def test_admin_endpoints_require_admin(disable_heavy_startup, monkeypatch):
    # Force multi-user mode so admin guard applies
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    reset_settings()
    app.dependency_overrides[get_request_user] = _non_admin_user()

    client = TestClient(app)
    # GET index info
    r1 = client.get("/api/v1/vector_stores/store-1/admin/index_info")
    assert r1.status_code == 403
    # POST rebuild index
    r2 = client.post("/api/v1/vector_stores/store-1/admin/rebuild_index", json={"index_type": "hnsw"})
    assert r2.status_code == 403
    # POST delete by filter
    r3 = client.post("/api/v1/vector_stores/store-1/admin/delete_by_filter", json={"filter": {"kind": "chunk"}})
    assert r3.status_code == 403
    # GET health
    r4 = client.get("/api/v1/vector_stores/admin/health")
    assert r4.status_code == 403
    app.dependency_overrides.pop(get_request_user, None)
    reset_settings()


@pytest.mark.unit
def test_delete_by_filter_rejects_empty_filter(disable_heavy_startup, admin_user):
    client = TestClient(app)
    r = client.post("/api/v1/vector_stores/store-1/admin/delete_by_filter", json={"filter": {}})
    assert r.status_code == 400
    assert "Filter cannot be empty" in r.text


@pytest.mark.unit
def test_delete_by_filter_rejects_empty_boolean_ops(disable_heavy_startup, admin_user):
    client = TestClient(app)
    # Empty $and list
    r1 = client.post(
        "/api/v1/vector_stores/store-1/admin/delete_by_filter",
        json={"filter": {"$and": []}},
    )
    assert r1.status_code == 400
    assert "Filter cannot be empty" in r1.text

    # Empty $or list
    r2 = client.post(
        "/api/v1/vector_stores/store-1/admin/delete_by_filter",
        json={"filter": {"$or": []}},
    )
    assert r2.status_code == 400
    assert "Filter cannot be empty" in r2.text
