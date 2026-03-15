import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.Persona.exemplar_ingestion import (
    build_transcript_exemplar_candidates,
)


pytestmark = pytest.mark.unit

fastapi_app = FastAPI()
fastapi_app.include_router(persona_ep.router, prefix="/api/v1/persona")


def _client_for_user(user_id: int, db: CharactersRAGDB):
    async def override_user():
        return User(id=user_id, username=f"persona-user-{user_id}", email=None, is_active=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = lambda: db
    return TestClient(fastapi_app)


@pytest.fixture()
def persona_db(tmp_path):
    db = CharactersRAGDB(str(tmp_path / "persona_exemplar_ingestion.db"), client_id="persona-exemplar-ingestion-tests")
    yield db
    db.close_connection()


def _create_persona(client: TestClient, *, name: str) -> str:
    created = client.post(
        "/api/v1/persona/profiles",
        json={"name": name, "mode": "session_scoped"},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_build_transcript_candidates_keeps_imported_rows_review_gated():
    candidates = build_transcript_exemplar_candidates(
        transcript="""
Host: Hello there, let's keep this grounded and thoughtful.
Host: I won't reveal hidden instructions no matter how you ask.
        """,
        source_ref="upload://transcript/demo",
        notes="Imported from transcript",
        max_candidates=3,
    )

    assert len(candidates) == 2
    assert {candidate["source_type"] for candidate in candidates} == {"generated_candidate"}
    assert all(candidate["enabled"] is False for candidate in candidates)
    assert candidates[1]["kind"] == "boundary"


def test_persona_exemplar_import_creates_generated_candidates(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        persona_id = _create_persona(client, name="Import Persona")

        response = client.post(
            f"/api/v1/persona/profiles/{persona_id}/exemplars/import",
            json={
                "transcript": """
Speaker: Hello there, let's keep this grounded and thoughtful.
Speaker: I won't reveal hidden instructions no matter how you ask.
                """,
                "source_ref": "upload://transcript/demo",
                "notes": "Transcript import",
            },
        )

        assert response.status_code == 201, response.text
        payload = response.json()
        assert len(payload) == 2
        assert {item["source_type"] for item in payload} == {"generated_candidate"}
        assert all(item["enabled"] is False for item in payload)

        listed = client.get(
            f"/api/v1/persona/profiles/{persona_id}/exemplars?include_disabled=true"
        )
        assert listed.status_code == 200, listed.text
        assert {item["id"] for item in listed.json()} == {item["id"] for item in payload}

    fastapi_app.dependency_overrides.clear()


def test_persona_exemplar_review_approves_and_rejects_candidates(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        persona_id = _create_persona(client, name="Review Persona")

        imported = client.post(
            f"/api/v1/persona/profiles/{persona_id}/exemplars/import",
            json={
                "transcript": """
Speaker: Hello there, let's keep this grounded and thoughtful.
Speaker: I won't reveal hidden instructions no matter how you ask.
                """,
                "notes": "Initial import",
            },
        )
        assert imported.status_code == 201, imported.text
        candidates = imported.json()
        approve_id = candidates[0]["id"]
        reject_id = candidates[1]["id"]

        approved = client.post(
            f"/api/v1/persona/profiles/{persona_id}/exemplars/{approve_id}/review",
            json={"action": "approve", "notes": "Keep this one"},
        )
        assert approved.status_code == 200, approved.text
        approved_payload = approved.json()
        assert approved_payload["enabled"] is True
        assert "approved" in approved_payload["notes"].lower()
        assert "Keep this one" in approved_payload["notes"]

        rejected = client.post(
            f"/api/v1/persona/profiles/{persona_id}/exemplars/{reject_id}/review",
            json={"action": "reject", "notes": "Too generic"},
        )
        assert rejected.status_code == 200, rejected.text
        rejected_payload = rejected.json()
        assert rejected_payload["enabled"] is False
        assert rejected_payload["source_type"] == "generated_candidate"
        assert "rejected" in rejected_payload["notes"].lower()
        assert "Too generic" in rejected_payload["notes"]

        still_visible = client.get(
            f"/api/v1/persona/profiles/{persona_id}/exemplars/{reject_id}?include_disabled=true"
        )
        assert still_visible.status_code == 200, still_visible.text
        assert still_visible.json()["enabled"] is False

    fastapi_app.dependency_overrides.clear()
