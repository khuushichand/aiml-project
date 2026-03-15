import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import (
    get_chacha_db_for_user,
)
from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit

fastapi_app = FastAPI()
fastapi_app.include_router(persona_ep.router, prefix="/api/v1/persona")


def _client_for_user(user_id: int, db: CharactersRAGDB) -> TestClient:
    async def override_user() -> User:
        return User(
            id=user_id,
            username=f"persona-user-{user_id}",
            email=None,
            is_active=True,
        )

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = lambda: db
    fastapi_app.dependency_overrides[check_rate_limit] = lambda: None
    return TestClient(fastapi_app)


@pytest.fixture()
def persona_db(tmp_path):
    db = CharactersRAGDB(
        str(tmp_path / "persona_setup_analytics_api.db"),
        client_id="persona-setup-analytics-api-tests",
    )
    yield db
    db.close_connection()


def _create_persona(client: TestClient, *, name: str) -> str:
    response = client.post(
        "/api/v1/persona/profiles",
        json={
            "name": name,
            "mode": "persistent_scoped",
            "setup": {
                "status": "in_progress",
                "version": 1,
                "run_id": "setup-run-1",
                "current_step": "persona",
                "completed_steps": [],
                "completed_at": None,
                "last_test_type": None,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_persona_setup_events_dedupe_by_event_key(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        persona_id = _create_persona(client, name="Setup Analytics Persona")
        body = {
            "event_id": "evt-1",
            "event_key": "step_viewed:test",
            "run_id": "setup-run-1",
            "event_type": "step_viewed",
            "step": "test",
        }

        first = client.post(
            f"/api/v1/persona/profiles/{persona_id}/setup-events",
            json=body,
        )
        second = client.post(
            f"/api/v1/persona/profiles/{persona_id}/setup-events",
            json={**body, "event_id": "evt-2"},
        )

        assert first.status_code == 201, first.text
        assert first.json()["deduped"] is False
        assert second.status_code == 200, second.text
        assert second.json()["deduped"] is True

        rows = persona_db.execute_query(
            """
            SELECT event_id, run_id, event_type, event_key, step
            FROM persona_setup_events
            WHERE user_id = ? AND persona_id = ?
            ORDER BY created_at ASC, event_id ASC
            """,
            (1, persona_id),
        ).fetchall()
        assert len(rows) == 1
        assert dict(rows[0]) == {
            "event_id": "evt-1",
            "run_id": "setup-run-1",
            "event_type": "step_viewed",
            "event_key": "step_viewed:test",
            "step": "test",
        }

    fastapi_app.dependency_overrides.clear()


def test_persona_setup_analytics_summary_returns_recent_runs_and_rates(
    persona_db: CharactersRAGDB,
):
    with _client_for_user(1, persona_db) as client:
        persona_id = _create_persona(client, name="Setup Summary Persona")

        run_one_events = [
            {
                "event_id": "run-1-start",
                "event_key": "setup_started",
                "run_id": "setup-run-1",
                "event_type": "setup_started",
            },
            {
                "event_id": "run-1-view-test",
                "event_key": "step_viewed:test",
                "run_id": "setup-run-1",
                "event_type": "step_viewed",
                "step": "test",
            },
            {
                "event_id": "run-1-complete",
                "event_key": "setup_completed",
                "run_id": "setup-run-1",
                "event_type": "setup_completed",
                "step": "test",
                "completion_type": "dry_run",
            },
            {
                "event_id": "run-1-handoff-click",
                "run_id": "setup-run-1",
                "event_type": "handoff_action_clicked",
                "action_target": "live",
            },
            {
                "event_id": "run-1-handoff-target",
                "event_key": "handoff_target_reached:commands.command_list",
                "run_id": "setup-run-1",
                "event_type": "handoff_target_reached",
                "action_target": "commands.command_list",
            },
            {
                "event_id": "run-1-first-action",
                "event_key": "first_post_setup_action",
                "run_id": "setup-run-1",
                "event_type": "first_post_setup_action",
                "action_target": "live",
            },
        ]
        run_two_events = [
            {
                "event_id": "run-2-start",
                "event_key": "setup_started",
                "run_id": "setup-run-2",
                "event_type": "setup_started",
            },
            {
                "event_id": "run-2-view-commands",
                "event_key": "step_viewed:commands",
                "run_id": "setup-run-2",
                "event_type": "step_viewed",
                "step": "commands",
            },
            {
                "event_id": "run-2-detour-start",
                "run_id": "setup-run-2",
                "event_type": "detour_started",
                "step": "test",
                "detour_source": "live_failure",
            },
            {
                "event_id": "run-2-detour-return",
                "event_key": "detour_returned:live_failure",
                "run_id": "setup-run-2",
                "event_type": "detour_returned",
                "step": "test",
                "detour_source": "live_failure",
            },
            {
                "event_id": "run-2-error",
                "run_id": "setup-run-2",
                "event_type": "step_error",
                "step": "commands",
            },
        ]

        for event in [*run_one_events, *run_two_events]:
            response = client.post(
                f"/api/v1/persona/profiles/{persona_id}/setup-events",
                json=event,
            )
            assert response.status_code in {200, 201}, response.text

        analytics = client.get(f"/api/v1/persona/profiles/{persona_id}/setup-analytics")
        assert analytics.status_code == 200, analytics.text
        payload = analytics.json()

        assert payload["persona_id"] == persona_id
        assert payload["summary"] == {
            "total_runs": 2,
            "completed_runs": 1,
            "completion_rate": 0.5,
            "dry_run_completion_count": 1,
            "live_session_completion_count": 0,
            "most_common_dropoff_step": "commands",
            "handoff_click_rate": 0.5,
            "handoff_target_reach_rate": 1.0,
            "first_post_setup_action_rate": 0.5,
            "handoff_target_reached_counts": {"commands.command_list": 1},
            "detour_started_counts": {"live_failure": 1},
            "detour_returned_counts": {"live_failure": 1},
        }
        assert [run["run_id"] for run in payload["recent_runs"]] == [
            "setup-run-2",
            "setup-run-1",
        ]
        assert payload["recent_runs"][0]["completed_at"] is None
        assert payload["recent_runs"][0]["completion_type"] is None
        assert payload["recent_runs"][0]["terminal_step"] == "commands"
        assert payload["recent_runs"][0]["handoff_clicked"] is False
        assert payload["recent_runs"][0]["handoff_target_reached"] is False
        assert payload["recent_runs"][0]["handoff_dismissed"] is False
        assert payload["recent_runs"][0]["first_post_setup_action"] is False
        assert payload["recent_runs"][1]["completion_type"] == "dry_run"
        assert payload["recent_runs"][1]["terminal_step"] == "test"
        assert payload["recent_runs"][1]["handoff_clicked"] is True
        assert payload["recent_runs"][1]["handoff_target_reached"] is True
        assert payload["recent_runs"][1]["handoff_dismissed"] is False
        assert payload["recent_runs"][1]["first_post_setup_action"] is True
        assert payload["recent_runs"][1]["completed_at"]

    fastapi_app.dependency_overrides.clear()
