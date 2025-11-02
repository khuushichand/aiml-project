import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_personalization_db_for_user
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_personalization_db(tmp_path):
    db_path = tmp_path / "personalization.db"
    db = PersonalizationDB(str(db_path))

    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def override_db_dep():
        return db

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_personalization_db_for_user] = override_db_dep

    with TestClient(fastapi_app) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


def test_profile_roundtrip(client_with_personalization_db: TestClient):
    c = client_with_personalization_db
    # Get default profile
    r = c.get("/api/v1/personalization/profile")
    assert r.status_code == 200
    prof = r.json()
    assert "enabled" in prof

    # Opt in
    r2 = c.post("/api/v1/personalization/opt-in", json={"enabled": True})
    assert r2.status_code == 200
    prof2 = r2.json()
    assert prof2.get("enabled") is True

    # Update preferences
    r3 = c.post("/api/v1/personalization/preferences", json={"alpha": 0.3})
    assert r3.status_code == 200
    prof3 = r3.json()
    assert abs(prof3.get("alpha") - 0.3) < 1e-6


def test_memories_crud(client_with_personalization_db: TestClient):
    c = client_with_personalization_db
    # Add
    add = c.post("/api/v1/personalization/memories", json={"id": "tmp", "type": "semantic", "content": "Remember this", "pinned": False})
    assert add.status_code == 201
    mid = add.json()["id"]
    # List
    lst = c.get("/api/v1/personalization/memories")
    assert lst.status_code == 200
    data = lst.json()
    assert data["total"] >= 1
    # Delete
    dl = c.delete(f"/api/v1/personalization/memories/{mid}")
    assert dl.status_code == 200
