import pytest
from fastapi.testclient import TestClient
from importlib import import_module
from pathlib import Path

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=777, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_filters"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_job_filters_crud(client_with_user):
    c = client_with_user

    # Create job
    job_body = {
        "name": "Filters Job",
        "scope": {},
        "active": True,
    }
    r = c.post("/api/v1/watchlists/jobs", json=job_body)
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]

    # Replace filters
    payload = {
        "filters": [
            {"type": "keyword", "action": "exclude", "value": {"keywords": ["ai"], "match": "any"}, "priority": 100},
        ]
    }
    r = c.patch(f"/api/v1/watchlists/jobs/{job_id}/filters", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data.get("filters"), list) and len(data["filters"]) == 1

    # Append filter
    r = c.post(
        f"/api/v1/watchlists/jobs/{job_id}/filters:add",
        json={"filters": [{"type": "author", "action": "flag", "value": {"names": ["john"]}}]},
    )
    assert r.status_code == 200, r.text
    appended = r.json()
    assert len(appended.get("filters") or []) == 2

    # Get job and verify job_filters present
    r = c.get(f"/api/v1/watchlists/jobs/{job_id}")
    assert r.status_code == 200, r.text
    job = r.json()
    jf = job.get("job_filters") or {}
    assert isinstance(jf.get("filters"), list) and len(jf.get("filters")) == 2
