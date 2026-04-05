"""
Integration tests for Manuscript Management endpoints using a real ChaChaNotes DB.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.integration


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "manuscript_integration.db"
    db = CharactersRAGDB(str(db_path), client_id="integration_user")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    def override_db():
        return db

    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_DISABLE", "media,audio")
    monkeypatch.setenv("SKIP_AUDIO_ROUTERS_IN_TESTS", "1")

    from tldw_Server_API.app import main as app_main

    importlib.reload(app_main)
    fastapi_app = app_main.app

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = override_db

    with TestClient(fastapi_app) as c:
        yield c

    fastapi_app.dependency_overrides.clear()


PREFIX = "/api/v1/writing/manuscripts"


def test_full_manuscript_crud(client: TestClient):
    """Full lifecycle: create project -> part -> chapter -> scene -> structure -> update -> search -> delete."""

    # --- Create project ---
    resp = client.post(
        f"{PREFIX}/projects",
        json={"title": "My Novel", "author": "Test Author", "genre": "Fantasy"},
    )
    assert resp.status_code == 201, resp.text
    project = resp.json()
    project_id = project["id"]
    assert project["title"] == "My Novel"
    assert project["word_count"] == 0
    assert project["version"] == 1

    # --- Create part ---
    resp = client.post(
        f"{PREFIX}/projects/{project_id}/parts",
        json={"title": "Part One", "sort_order": 1.0},
    )
    assert resp.status_code == 201, resp.text
    part = resp.json()
    part_id = part["id"]
    assert part["title"] == "Part One"

    # --- Create chapter under the part ---
    resp = client.post(
        f"{PREFIX}/projects/{project_id}/chapters",
        json={"title": "Chapter One", "part_id": part_id, "sort_order": 1.0},
    )
    assert resp.status_code == 201, resp.text
    chapter = resp.json()
    chapter_id = chapter["id"]
    assert chapter["title"] == "Chapter One"
    assert chapter["part_id"] == part_id

    # --- Create scene with content ---
    scene_text = "The dragon soared above the mountains casting long shadows across the valley below"
    resp = client.post(
        f"{PREFIX}/chapters/{chapter_id}/scenes",
        json={
            "title": "Opening Scene",
            "content": {"type": "doc", "content": [{"type": "paragraph", "text": scene_text}]},
            "content_plain": scene_text,
            "sort_order": 1.0,
        },
    )
    assert resp.status_code == 201, resp.text
    scene = resp.json()
    scene_id = scene["id"]
    assert scene["title"] == "Opening Scene"
    assert scene["word_count"] > 0

    # --- Get project structure ---
    resp = client.get(f"{PREFIX}/projects/{project_id}/structure")
    assert resp.status_code == 200, resp.text
    structure = resp.json()
    assert structure["project_id"] == project_id
    assert len(structure["parts"]) == 1
    assert len(structure["parts"][0]["chapters"]) == 1
    assert len(structure["parts"][0]["chapters"][0]["scenes"]) == 1

    # --- Update scene to change content ---
    new_text = "The ancient dragon descended gracefully landing before the trembling knight"
    resp = client.patch(
        f"{PREFIX}/scenes/{scene_id}",
        json={"content_plain": new_text},
        headers={"expected-version": str(scene["version"])},
    )
    assert resp.status_code == 200, resp.text
    updated_scene = resp.json()
    assert updated_scene["version"] == scene["version"] + 1
    # Word count should be recalculated
    expected_wc = len(new_text.split())
    assert updated_scene["word_count"] == expected_wc

    # --- Verify project word count propagated ---
    resp = client.get(f"{PREFIX}/projects/{project_id}")
    assert resp.status_code == 200, resp.text
    project_refreshed = resp.json()
    assert project_refreshed["word_count"] == expected_wc

    # --- Search scenes ---
    resp = client.get(
        f"{PREFIX}/projects/{project_id}/search",
        params={"q": "dragon"},
    )
    assert resp.status_code == 200, resp.text
    search = resp.json()
    assert search["query"] == "dragon"
    assert len(search["results"]) >= 1
    assert search["results"][0]["id"] == scene_id

    # --- Soft delete scene ---
    resp = client.delete(
        f"{PREFIX}/scenes/{scene_id}",
        headers={"expected-version": str(updated_scene["version"])},
    )
    assert resp.status_code == 204

    # --- Verify scene is gone ---
    resp = client.get(f"{PREFIX}/scenes/{scene_id}")
    assert resp.status_code == 404

    # --- Verify project word count dropped to 0 ---
    resp = client.get(f"{PREFIX}/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["word_count"] == 0


def test_project_list_and_filter(client: TestClient):
    """Create multiple projects, list all, then filter by status."""

    # Create two draft projects
    resp1 = client.post(
        f"{PREFIX}/projects",
        json={"title": "Draft Novel A", "status": "draft"},
    )
    assert resp1.status_code == 201
    resp2 = client.post(
        f"{PREFIX}/projects",
        json={"title": "Completed Novel B", "status": "complete"},
    )
    assert resp2.status_code == 201

    # List all
    resp = client.get(f"{PREFIX}/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    titles = [p["title"] for p in data["projects"]]
    assert "Draft Novel A" in titles
    assert "Completed Novel B" in titles

    # Filter by status=draft
    resp = client.get(f"{PREFIX}/projects", params={"status": "draft"})
    assert resp.status_code == 200
    data = resp.json()
    statuses = {p["status"] for p in data["projects"]}
    assert statuses == {"draft"}
    assert any(p["title"] == "Draft Novel A" for p in data["projects"])

    # Filter by status=complete
    resp = client.get(f"{PREFIX}/projects", params={"status": "complete"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(p["status"] == "complete" for p in data["projects"])
    assert any(p["title"] == "Completed Novel B" for p in data["projects"])


def test_optimistic_locking(client: TestClient):
    """Verify that updating with a stale version returns 409."""

    # Create project
    resp = client.post(
        f"{PREFIX}/projects",
        json={"title": "Locking Test Project"},
    )
    assert resp.status_code == 201
    project = resp.json()
    project_id = project["id"]
    v1 = project["version"]

    # Update successfully
    resp = client.patch(
        f"{PREFIX}/projects/{project_id}",
        json={"title": "Updated Title"},
        headers={"expected-version": str(v1)},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["version"] == v1 + 1

    # Try again with the stale version -> should get 409
    resp = client.patch(
        f"{PREFIX}/projects/{project_id}",
        json={"title": "Stale Update"},
        headers={"expected-version": str(v1)},
    )
    assert resp.status_code == 409


def test_reorder(client: TestClient):
    """Create scenes, reorder them, verify new sort order."""

    # Setup: project -> chapter -> 3 scenes
    resp = client.post(
        f"{PREFIX}/projects",
        json={"title": "Reorder Test"},
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = client.post(
        f"{PREFIX}/projects/{project_id}/chapters",
        json={"title": "Chapter R"},
    )
    assert resp.status_code == 201
    chapter_id = resp.json()["id"]

    scene_ids = []
    for i in range(3):
        resp = client.post(
            f"{PREFIX}/chapters/{chapter_id}/scenes",
            json={"title": f"Scene {i}", "sort_order": float(i)},
        )
        assert resp.status_code == 201
        scene_ids.append(resp.json()["id"])

    # Reorder: reverse the scenes
    resp = client.post(
        f"{PREFIX}/projects/{project_id}/reorder",
        json={
            "entity_type": "scenes",
            "items": [
                {"id": scene_ids[0], "sort_order": 3.0},
                {"id": scene_ids[1], "sort_order": 2.0},
                {"id": scene_ids[2], "sort_order": 1.0},
            ],
        },
    )
    assert resp.status_code == 204

    # Verify new order
    resp = client.get(f"{PREFIX}/chapters/{chapter_id}/scenes")
    assert resp.status_code == 200
    scenes = resp.json()
    assert len(scenes) == 3
    # Should be scene_ids[2], scene_ids[1], scene_ids[0] after ordering
    assert scenes[0]["id"] == scene_ids[2]
    assert scenes[1]["id"] == scene_ids[1]
    assert scenes[2]["id"] == scene_ids[0]


def test_not_found(client: TestClient):
    """Fetching nonexistent entities returns 404."""

    resp = client.get(f"{PREFIX}/projects/nonexistent-uuid")
    assert resp.status_code == 404

    resp = client.get(f"{PREFIX}/parts/nonexistent-uuid")
    assert resp.status_code == 404

    resp = client.get(f"{PREFIX}/chapters/nonexistent-uuid")
    assert resp.status_code == 404

    resp = client.get(f"{PREFIX}/scenes/nonexistent-uuid")
    assert resp.status_code == 404
