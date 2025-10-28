import asyncio
import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user as _dep_get_user


class _Admin:
    id = "admin"
    is_admin = True
    username = "admin"


@pytest.mark.unit
def test_compactor_admin_endpoint(monkeypatch):
    # Override auth dependency to return admin
    app.dependency_overrides[_dep_get_user] = lambda: _Admin()

    # Patch compact_once to avoid touching real DBs
    called = {}

    async def _fake_compact_once(user_id: str, db_path=None) -> int:
        called["user_id"] = user_id
        called["db_path"] = db_path
        return 3

    import types
    import sys
    # Insert a proper module object to avoid unhashable SimpleNamespace in sys.modules
    fake_service = types.ModuleType("vector_compactor_stub")
    setattr(fake_service, "compact_once", _fake_compact_once)
    sys.modules['tldw_Server_API.app.core.Embeddings.services.vector_compactor'] = fake_service

    client = TestClient(app)
    resp = client.post("/api/v1/embeddings/compactor/run", json={"user_id": "u42", "media_db_path": "Databases/Media_DB_v2.db"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user_id"] == "u42"
    assert data["collections_touched"] == 3
    assert "ts" in data
    assert called["user_id"] == "u42"
    # Cleanup dependency override
    app.dependency_overrides.pop(_dep_get_user, None)
