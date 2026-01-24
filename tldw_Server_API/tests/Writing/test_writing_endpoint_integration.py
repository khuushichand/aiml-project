"""
Integration tests for Writing Playground endpoints using a real ChaChaNotes DB.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.integration


def _has_tiktoken() -> bool:
    try:
        import tiktoken  # noqa: F401
    except Exception:
        return False
    return True


@pytest.fixture()
def client_with_writing_db(tmp_path, monkeypatch):
    db_path = tmp_path / "writing_integration.db"
    db = CharactersRAGDB(str(db_path), client_id="integration_user")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    def override_db_dep():
        return db

    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")

    from tldw_Server_API.app import main as app_main

    importlib.reload(app_main)
    fastapi_app = app_main.app

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = override_db_dep

    with TestClient(fastapi_app) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


def test_writing_sessions_crud_and_clone(client_with_writing_db: TestClient):
    client = client_with_writing_db

    create_resp = client.post(
        "/api/v1/writing/sessions",
        json={"name": "Session One", "payload": {"text": "Draft 1"}},
    )
    assert create_resp.status_code == 201, create_resp.text
    session = create_resp.json()
    session_id = session["id"]

    list_resp = client.get("/api/v1/writing/sessions")
    assert list_resp.status_code == 200, list_resp.text
    listed = list_resp.json()
    assert listed["total"] >= 1
    assert any(item["id"] == session_id for item in listed["sessions"])

    get_resp = client.get(f"/api/v1/writing/sessions/{session_id}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["payload"]["text"] == "Draft 1"
    version = fetched["version"]

    update_resp = client.patch(
        f"/api/v1/writing/sessions/{session_id}",
        json={"name": "Session One Updated", "payload": {"text": "Draft 2"}},
        headers={"expected-version": str(version)},
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["version"] == version + 1
    assert updated["payload"]["text"] == "Draft 2"

    stale_update = client.patch(
        f"/api/v1/writing/sessions/{session_id}",
        json={"name": "Session One Stale"},
        headers={"expected-version": str(version)},
    )
    assert stale_update.status_code in (400, 409)

    clone_resp = client.post(
        f"/api/v1/writing/sessions/{session_id}/clone",
        json={"name": "Session One Clone"},
    )
    assert clone_resp.status_code == 200, clone_resp.text
    clone = clone_resp.json()
    assert clone["version_parent_id"] == session_id
    assert clone["name"] == "Session One Clone"

    refreshed = client.get(f"/api/v1/writing/sessions/{session_id}").json()
    del_resp = client.delete(
        f"/api/v1/writing/sessions/{session_id}",
        headers={"expected-version": str(refreshed["version"])},
    )
    assert del_resp.status_code in (200, 204)
    assert client.get(f"/api/v1/writing/sessions/{session_id}").status_code == 404


def test_writing_templates_and_themes_crud(client_with_writing_db: TestClient):
    client = client_with_writing_db

    tmpl_resp = client.post(
        "/api/v1/writing/templates",
        json={"name": "Template A", "payload": {"preset": "alpha"}},
    )
    assert tmpl_resp.status_code == 201, tmpl_resp.text
    template = tmpl_resp.json()
    tmpl_version = template["version"]

    list_templates = client.get("/api/v1/writing/templates")
    assert list_templates.status_code == 200
    templates_payload = list_templates.json()
    assert templates_payload["total"] == 1

    upd_tmpl = client.patch(
        "/api/v1/writing/templates/Template A",
        json={"is_default": True},
        headers={"expected-version": str(tmpl_version)},
    )
    assert upd_tmpl.status_code == 200, upd_tmpl.text
    updated_template = upd_tmpl.json()
    assert updated_template["is_default"] is True

    del_tmpl = client.delete(
        "/api/v1/writing/templates/Template A",
        headers={"expected-version": str(updated_template["version"])},
    )
    assert del_tmpl.status_code in (200, 204)
    assert client.get("/api/v1/writing/templates/Template A").status_code == 404

    theme_resp = client.post(
        "/api/v1/writing/themes",
        json={"name": "Theme A", "class_name": "theme-a", "css": ".theme-a { color: #111; }", "order": 2},
    )
    assert theme_resp.status_code == 201, theme_resp.text
    theme = theme_resp.json()
    theme_version = theme["version"]
    assert theme["order"] == 2

    list_themes = client.get("/api/v1/writing/themes")
    assert list_themes.status_code == 200
    themes_payload = list_themes.json()
    assert themes_payload["total"] == 1

    upd_theme = client.patch(
        "/api/v1/writing/themes/Theme A",
        json={"order": 1},
        headers={"expected-version": str(theme_version)},
    )
    assert upd_theme.status_code == 200, upd_theme.text
    updated_theme = upd_theme.json()
    assert updated_theme["order"] == 1

    del_theme = client.delete(
        "/api/v1/writing/themes/Theme A",
        headers={"expected-version": str(updated_theme["version"])},
    )
    assert del_theme.status_code in (200, 204)
    assert client.get("/api/v1/writing/themes/Theme A").status_code == 404


def test_writing_capabilities_basic(client_with_writing_db: TestClient):
    client = client_with_writing_db

    version_resp = client.get("/api/v1/writing/version")
    assert version_resp.status_code == 200, version_resp.text
    assert version_resp.json()["version"] == 1

    resp = client.get("/api/v1/writing/capabilities", params={"include_providers": "false"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["version"] == 1
    assert data["server"]["sessions"] is True
    assert data["server"]["wordclouds"] is True
    assert data["providers"] is None


def test_writing_wordclouds_flow(client_with_writing_db: TestClient):
    client = client_with_writing_db

    text = "Alpha beta beta gamma gamma gamma"
    create_resp = client.post(
        "/api/v1/writing/wordclouds",
        json={"text": text, "options": {"stopwords": []}},
    )
    assert create_resp.status_code in (200, 202), create_resp.text
    payload = create_resp.json()
    assert payload["status"] in ("ready", "queued", "running", "failed")
    assert payload["id"]

    if payload["status"] == "ready":
        words = {entry["text"]: entry["weight"] for entry in payload["result"]["words"]}
        assert words["gamma"] == 3
        assert words["beta"] == 2

    cached_resp = client.post(
        "/api/v1/writing/wordclouds",
        json={"text": text, "options": {"stopwords": []}},
    )
    assert cached_resp.status_code in (200, 202), cached_resp.text
    cached = cached_resp.json()
    assert cached["id"] == payload["id"]

    get_resp = client.get(f"/api/v1/writing/wordclouds/{payload['id']}")
    assert get_resp.status_code == 200, get_resp.text
    fetched = get_resp.json()
    assert fetched["id"] == payload["id"]


def test_writing_wordclouds_empty_result(client_with_writing_db: TestClient):
    client = client_with_writing_db

    text = "the and of"
    resp = client.post(
        "/api/v1/writing/wordclouds",
        json={"text": text},
    )
    assert resp.status_code in (200, 202), resp.text
    data = resp.json()
    assert data["status"] in ("ready", "queued", "running", "failed")
    if data["status"] == "ready":
        assert data["result"]["words"] == []


def test_writing_capabilities_provider_tokenizers(client_with_writing_db: TestClient, monkeypatch):
    client = client_with_writing_db

    async def fake_get_configured_providers_async(include_deprecated: bool = False):
        return {
            "default_provider": "openai",
            "providers": [
                {
                    "name": "openai",
                    "models": ["gpt-3.5-turbo", "definitely-not-a-real-model"],
                    "capabilities": {},
                }
            ],
        }

    from tldw_Server_API.app.api.v1.endpoints import writing as writing_endpoints

    monkeypatch.setattr(writing_endpoints, "get_configured_providers_async", fake_get_configured_providers_async)

    resp = client.get("/api/v1/writing/capabilities")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    providers = data["providers"]
    assert providers
    tokenizers = providers[0]["tokenizers"]
    assert "gpt-3.5-turbo" in tokenizers
    assert "definitely-not-a-real-model" in tokenizers
    assert tokenizers["definitely-not-a-real-model"]["available"] is False
    if _has_tiktoken():
        assert tokenizers["gpt-3.5-turbo"]["available"] is True
        assert tokenizers["gpt-3.5-turbo"]["tokenizer"].startswith("tiktoken:")
    else:
        assert tokenizers["gpt-3.5-turbo"]["available"] is False
        assert "unavailable" in tokenizers["gpt-3.5-turbo"]["error"].lower()


def test_writing_tokenize_and_count(client_with_writing_db: TestClient):
    if not _has_tiktoken():
        pytest.skip("tiktoken not available")

    client = client_with_writing_db
    count_resp = client.post(
        "/api/v1/writing/token-count",
        json={"provider": "openai", "model": "gpt-3.5-turbo", "text": "Hello world"},
    )
    assert count_resp.status_code == 200, count_resp.text
    count_payload = count_resp.json()
    assert count_payload["count"] >= 1

    tokenize_resp = client.post(
        "/api/v1/writing/tokenize",
        json={
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "text": "Hello world",
            "options": {"include_strings": False},
        },
    )
    assert tokenize_resp.status_code == 200, tokenize_resp.text
    tokens = tokenize_resp.json()
    assert tokens["strings"] is None


def test_writing_tokenize_provider_model_mismatch(client_with_writing_db: TestClient):
    if not _has_tiktoken():
        pytest.skip("tiktoken not available")

    client = client_with_writing_db
    resp = client.post(
        "/api/v1/writing/token-count",
        json={"provider": "anthropic", "model": "gpt-3.5-turbo", "text": "Mismatch OK"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] >= 1


def test_writing_tokenize_unavailable(client_with_writing_db: TestClient):
    client = client_with_writing_db
    resp = client.post(
        "/api/v1/writing/token-count",
        json={"provider": "openai", "model": "definitely-not-a-real-model", "text": "Hello"},
    )
    assert resp.status_code == 422, resp.text
    detail = str(resp.json().get("detail", "")).lower()
    if _has_tiktoken():
        assert "not available" in detail
    else:
        assert "unavailable" in detail
