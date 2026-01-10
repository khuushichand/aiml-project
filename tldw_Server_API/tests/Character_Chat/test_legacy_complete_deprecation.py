import os
import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_legacy_complete_deprecation_headers():
    os.environ.setdefault("AUTH_MODE", "single_user")
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    from tldw_Server_API.app.main import app

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    client = TestClient(app)

    # Pick a character and create a chat
    r = client.get("/api/v1/characters/", headers=headers)
    assert r.status_code == 200
    character_id = r.json()[0]["id"]

    r = client.post("/api/v1/chats/", json={"character_id": character_id}, headers=headers)
    assert r.status_code == 201
    chat_id = r.json()["id"]

    # Call legacy endpoint with a non-empty body
    r = client.post(f"/api/v1/chats/{chat_id}/complete", json={"foo": "bar"}, headers=headers)
    assert r.status_code == 422
    # Deprecation header should be present even on error
    assert r.headers.get("Deprecation") == "true"
    assert "Sunset" in r.headers
