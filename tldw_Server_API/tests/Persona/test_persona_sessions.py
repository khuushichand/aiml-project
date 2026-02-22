import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.Persona.session_manager import SessionManager


pytestmark = pytest.mark.unit

fastapi_app = FastAPI()
fastapi_app.include_router(persona_ep.router, prefix="/api/v1/persona")


@pytest.fixture()
def persona_db(tmp_path):
    db = CharactersRAGDB(str(tmp_path / "persona_sessions.db"), client_id="persona-sessions-tests")
    yield db
    db.close_connection()


def _client_for_user(user_id: int, db: CharactersRAGDB):
    async def override_user():
        return User(id=user_id, username=f"user-{user_id}", email=None, is_active=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = lambda: db
    return TestClient(fastapi_app)


def test_persona_sessions_requires_auth():
    with TestClient(fastapi_app) as client:
        r_list = client.get("/api/v1/persona/sessions")
        r_detail = client.get("/api/v1/persona/sessions/sess_missing")
        assert r_list.status_code == 401
        assert r_detail.status_code == 401


def test_persona_sessions_list_and_detail_roundtrip(monkeypatch, persona_db: CharactersRAGDB):
    manager = SessionManager()
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)

    with _client_for_user(1, persona_db) as client:
        created = client.post("/api/v1/persona/session", json={"persona_id": "research_assistant"})
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        manager.append_turn(
            session_id=session_id,
            user_id="1",
            persona_id="research_assistant",
            role="user",
            content="hello",
            turn_type="user_message",
        )

        listed = client.get("/api/v1/persona/sessions")
        assert listed.status_code == 200
        payload = listed.json()
        assert isinstance(payload, list)
        assert any(item["session_id"] == session_id for item in payload)

        detail = client.get(f"/api/v1/persona/sessions/{session_id}?limit_turns=10")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["session_id"] == session_id
        assert detail_payload["turn_count"] >= 1
        assert len(detail_payload["turns"]) >= 1

    fastapi_app.dependency_overrides.clear()


def test_persona_session_resume_rejects_ownership_mismatch(monkeypatch, persona_db: CharactersRAGDB):
    manager = SessionManager()
    _ = manager.create(user_id="1", persona_id="research_assistant", resume_session_id="sess_owned_by_1")
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)

    with _client_for_user(2, persona_db) as client:
        resp = client.post(
            "/api/v1/persona/session",
            json={
                "persona_id": "research_assistant",
                "resume_session_id": "sess_owned_by_1",
            },
        )
        assert resp.status_code == 403

    fastapi_app.dependency_overrides.clear()


def test_persona_session_detail_is_user_scoped(monkeypatch, persona_db: CharactersRAGDB):
    manager = SessionManager()
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)
    persona_id = persona_db.create_persona_profile(
        {
            "id": "research_assistant",
            "user_id": "1",
            "name": "Research Assistant",
            "mode": "session_scoped",
            "system_prompt": "Helper",
            "is_active": True,
        }
    )
    _ = persona_db.create_persona_session(
        {
            "id": "sess_scoped",
            "persona_id": persona_id,
            "user_id": "1",
            "mode": "session_scoped",
            "reuse_allowed": False,
            "status": "active",
            "scope_snapshot_json": {},
        }
    )

    with _client_for_user(2, persona_db) as client:
        resp = client.get("/api/v1/persona/sessions/sess_scoped")
        assert resp.status_code == 404

    fastapi_app.dependency_overrides.clear()


def test_persona_sessions_return_404_when_disabled(monkeypatch, persona_db: CharactersRAGDB):
    manager = SessionManager()
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)
    monkeypatch.setattr(persona_ep, "is_persona_enabled", lambda: False)

    with _client_for_user(1, persona_db) as client:
        r_list = client.get("/api/v1/persona/sessions")
        r_detail = client.get("/api/v1/persona/sessions/sess_disabled")
        assert r_list.status_code == 404
        assert r_detail.status_code == 404

    fastapi_app.dependency_overrides.clear()
