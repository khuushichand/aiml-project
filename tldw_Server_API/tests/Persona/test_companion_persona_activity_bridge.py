from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Persona.session_manager import SessionManager
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit

fastapi_app = FastAPI()
fastapi_app.include_router(persona_ep.router, prefix="/api/v1/persona")


@pytest.fixture()
def persona_client_with_companion_opt_in(monkeypatch, tmp_path):
    user_id = 1
    base_dir = tmp_path / "user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")

    persona_db = CharactersRAGDB(str(tmp_path / "persona_sessions.db"), client_id="companion-persona-tests")
    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))
    personalization_db.update_profile(str(user_id), enabled=1)
    session_manager = SessionManager()
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: session_manager)

    async def override_user():
        return User(id=user_id, username="user-1", email=None, is_active=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = lambda: persona_db
    try:
        with TestClient(fastapi_app) as client:
            yield client, personalization_db
    finally:
        fastapi_app.dependency_overrides.clear()
        persona_db.close_connection()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_persona_session_creation_records_companion_activity(persona_client_with_companion_opt_in):
    client, personalization_db = persona_client_with_companion_opt_in

    created = client.post("/api/v1/persona/session", json={"persona_id": "research_assistant"})
    assert created.status_code == 200, created.text
    payload = created.json()

    events, total = personalization_db.list_companion_activity_events("1", limit=10)
    assert total == 1
    event = events[0]
    assert event["event_type"] == "persona_session_started"
    assert event["source_type"] == "persona_session"
    assert event["source_id"] == payload["session_id"]
    assert event["surface"] == "api.persona"
    assert event["provenance"]["capture_mode"] == "explicit"
    assert event["provenance"]["route"] == "/api/v1/persona/session"
    assert event["metadata"]["persona_id"] == payload["persona"]["id"]
    assert event["metadata"]["runtime_mode"] == payload["runtime_mode"]
