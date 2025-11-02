import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=123, username="tester", email=None, is_active=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


def test_templates_crud_and_preview(client_with_user):
    client = client_with_user

    # Create
    payload = {
        "name": "daily-brief",
        "type": "newsletter_markdown",
        "format": "md",
        "body": "# Hello {{ date }}\n",
        "description": "Daily brief template",
        "is_default": True,
    }
    r = client.post("/api/v1/outputs/templates", json=payload)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["name"] == "daily-brief"
    tid = created["id"]

    # List
    r = client.get("/api/v1/outputs/templates")
    assert r.status_code == 200, r.text
    lst = r.json()
    assert lst["total"] >= 1
    assert any(t["name"] == "daily-brief" for t in lst["items"])

    # Get
    r = client.get(f"/api/v1/outputs/templates/{tid}")
    assert r.status_code == 200
    got = r.json()
    assert got["id"] == tid
    assert got["format"] == "md"

    # Update
    r = client.patch(f"/api/v1/outputs/templates/{tid}", json={"description": "Updated"})
    assert r.status_code == 200
    upd = r.json()
    assert upd["description"] == "Updated"

    # Preview (returns body as-is for now)
    r = client.post(f"/api/v1/outputs/templates/{tid}/preview", json={"template_id": tid, "item_ids": [1]})
    assert r.status_code == 200
    prev = r.json()
    assert prev["rendered"].startswith("# Hello ")

    # Delete
    r = client.delete(f"/api/v1/outputs/templates/{tid}")
    assert r.status_code == 200
    assert r.json().get("success") is True

    # Get after delete -> 404
    r = client.get(f"/api/v1/outputs/templates/{tid}")
    assert r.status_code == 404
