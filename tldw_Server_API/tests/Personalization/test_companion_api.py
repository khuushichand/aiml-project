from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_personalization_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.main import app as fastapi_app


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_companion_db(tmp_path):
    db = PersonalizationDB(str(tmp_path / "personalization.db"))

    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def override_db_dep():
        return db

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_personalization_db_for_user] = override_db_dep

    with TestClient(fastapi_app) as client:
        yield client, db

    fastapi_app.dependency_overrides.clear()


def test_companion_activity_endpoint_returns_provenance(client_with_companion_db) -> None:
    client, db = client_with_companion_db
    db.insert_companion_activity_event(
        user_id="1",
        event_type="reading.saved",
        source_type="reading_item",
        source_id="42",
        surface="reading",
        dedupe_key="reading.saved:reading_item:42",
        tags=["research", "project-alpha"],
        provenance={"source_ids": ["42"], "capture_mode": "explicit"},
        metadata={"title": "Example article"},
    )

    response = client.get("/api/v1/companion/activity?limit=10")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["event_type"] == "reading.saved"
    assert payload["items"][0]["provenance"]["capture_mode"] == "explicit"
    assert payload["items"][0]["metadata"]["title"] == "Example article"


def test_companion_knowledge_endpoint_returns_cards(client_with_companion_db) -> None:
    client, db = client_with_companion_db
    db.upsert_companion_knowledge_card(
        user_id="1",
        card_type="project_focus",
        title="Current focus",
        summary="Recent explicit activity clusters around 'project-alpha'.",
        evidence=[{"source_id": "42"}],
        score=0.9,
    )

    response = client.get("/api/v1/companion/knowledge")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["card_type"] == "project_focus"
    assert payload["items"][0]["evidence"] == [{"source_id": "42"}]


def test_companion_activity_create_records_explicit_capture(client_with_companion_db) -> None:
    client, db = client_with_companion_db

    response = client.post(
        "/api/v1/companion/activity",
        json={
            "event_type": "extension.selection_saved",
            "source_type": "browser_selection",
            "source_id": "capture-1",
            "surface": "extension.sidepanel",
            "dedupe_key": "extension.selection_saved:capture-1",
            "tags": ["extension", "selection"],
            "provenance": {
                "capture_mode": "explicit",
                "route": "extension.context_menu",
                "action": "save_selection",
            },
            "metadata": {
                "selection": "Remember this paragraph.",
                "page_url": "https://example.com/article",
                "page_title": "Example article",
            },
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["event_type"] == "extension.selection_saved"
    assert payload["source_id"] == "capture-1"
    assert payload["provenance"]["capture_mode"] == "explicit"
    assert payload["metadata"]["selection"] == "Remember this paragraph."

    rows, total = db.list_companion_activity_events("1", limit=10, offset=0)
    assert total == 1
    assert rows[0]["source_id"] == "capture-1"
    assert rows[0]["provenance"]["action"] == "save_selection"


def test_companion_activity_create_rejects_missing_provenance(
    client_with_companion_db,
) -> None:
    client, _db = client_with_companion_db

    response = client.post(
        "/api/v1/companion/activity",
        json={
            "event_type": "extension.selection_saved",
            "source_type": "browser_selection",
            "source_id": "capture-1",
            "surface": "extension.sidepanel",
            "metadata": {
                "selection": "Remember this paragraph.",
            },
        },
    )

    assert response.status_code == 422, response.text


def test_companion_check_in_create_records_explicit_capture(client_with_companion_db) -> None:
    client, db = client_with_companion_db

    response = client.post(
        "/api/v1/companion/check-ins",
        json={
            "title": "Morning reset",
            "summary": "Re-focused on the companion capture backlog before lunch.",
            "tags": ["planning", "focus"],
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["event_type"] == "companion_check_in_recorded"
    assert payload["source_type"] == "companion_check_in"
    assert payload["surface"] == "companion.workspace"
    assert payload["metadata"]["title"] == "Morning reset"
    assert payload["metadata"]["summary"] == "Re-focused on the companion capture backlog before lunch."
    assert payload["provenance"]["route"] == "/api/v1/companion/check-ins"
    assert payload["provenance"]["action"] == "manual_check_in"

    rows, total = db.list_companion_activity_events("1", limit=10, offset=0)
    assert total == 1
    assert rows[0]["event_type"] == "companion_check_in_recorded"
    assert rows[0]["tags"] == ["planning", "focus"]


def test_companion_check_in_create_accepts_surface_override(client_with_companion_db) -> None:
    client, db = client_with_companion_db

    response = client.post(
        "/api/v1/companion/check-ins",
        json={
            "summary": "Logged a quick update from the persona sidepanel.",
            "surface": "persona.sidepanel",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["surface"] == "persona.sidepanel"
    assert payload["metadata"]["summary"] == "Logged a quick update from the persona sidepanel."
    assert payload["provenance"]["route"] == "/api/v1/companion/check-ins"

    rows, total = db.list_companion_activity_events("1", limit=10, offset=0)
    assert total == 1
    assert rows[0]["surface"] == "persona.sidepanel"


def test_companion_goals_create_and_list(client_with_companion_db) -> None:
    client, _db = client_with_companion_db

    create_response = client.post(
        "/api/v1/companion/goals",
        json={
            "title": "Finish reading queue",
            "description": "Read 3 saved papers this week",
            "goal_type": "reading_backlog",
            "config": {"target_count": 3},
            "progress": {"completed_count": 0},
        },
    )

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["title"] == "Finish reading queue"
    assert created["goal_type"] == "reading_backlog"
    assert created["config"] == {"target_count": 3}

    list_response = client.get("/api/v1/companion/goals")

    assert list_response.status_code == 200, list_response.text
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == created["id"]


def test_companion_goal_patch_updates_fields(client_with_companion_db) -> None:
    client, db = client_with_companion_db
    goal_id = db.create_companion_goal(
        user_id="1",
        title="Finish reading queue",
        description="Read 3 saved papers this week",
        goal_type="reading_backlog",
        config={"target_count": 3},
        progress={"completed_count": 0},
    )

    response = client.patch(
        f"/api/v1/companion/goals/{goal_id}",
        json={
            "title": "Shrink reading queue",
            "progress": {"completed_count": 1},
            "status": "paused",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == goal_id
    assert payload["title"] == "Shrink reading queue"
    assert payload["progress"] == {"completed_count": 1}
    assert payload["status"] == "paused"


def test_companion_goal_patch_rejects_null_for_non_nullable_fields(client_with_companion_db) -> None:
    client, db = client_with_companion_db
    goal_id = db.create_companion_goal(
        user_id="1",
        title="Finish reading queue",
        description="Read 3 saved papers this week",
        goal_type="reading_backlog",
        config={"target_count": 3},
        progress={"completed_count": 0},
    )

    response = client.patch(
        f"/api/v1/companion/goals/{goal_id}",
        json={"status": None},
    )

    assert response.status_code == 422, response.text
