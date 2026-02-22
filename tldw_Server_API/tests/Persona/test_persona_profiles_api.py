import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


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
    db = CharactersRAGDB(str(tmp_path / "persona_profiles_api.db"), client_id="persona-profiles-api-tests")
    yield db
    db.close_connection()


def test_persona_profile_scope_policy_crud(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        created = client.post(
            "/api/v1/persona/profiles",
            json={
                "name": "Ops Assistant",
                "mode": "persistent_scoped",
                "system_prompt": "Focus on support workflows.",
            },
        )
        assert created.status_code == 201, created.text
        profile = created.json()
        persona_id = profile["id"]
        assert profile["mode"] == "persistent_scoped"

        fetched = client.get(f"/api/v1/persona/profiles/{persona_id}")
        assert fetched.status_code == 200
        assert fetched.json()["name"] == "Ops Assistant"

        scope_replace = client.put(
            f"/api/v1/persona/profiles/{persona_id}/scope-rules",
            json={
                "rules": [
                    {"rule_type": "conversation_id", "rule_value": "conv-001", "include": True},
                    {"rule_type": "media_tag", "rule_value": "priority", "include": True},
                    {"rule_type": "media_id", "rule_value": "101", "include": False},
                ]
            },
        )
        assert scope_replace.status_code == 200, scope_replace.text
        scope_payload = scope_replace.json()
        assert scope_payload["replaced_count"] == 3
        assert len(scope_payload["rules"]) == 3

        policy_replace = client.put(
            f"/api/v1/persona/profiles/{persona_id}/policy-rules",
            json={
                "rules": [
                    {"rule_kind": "mcp_tool", "rule_name": "media.search", "allowed": True},
                    {
                        "rule_kind": "skill",
                        "rule_name": "workspace.digest",
                        "allowed": True,
                        "require_confirmation": False,
                        "max_calls_per_turn": 2,
                    },
                ]
            },
        )
        assert policy_replace.status_code == 200, policy_replace.text
        policy_payload = policy_replace.json()
        assert policy_payload["replaced_count"] == 2
        assert len(policy_payload["rules"]) == 2

        patched = client.patch(
            f"/api/v1/persona/profiles/{persona_id}",
            json={"mode": "session_scoped", "is_active": True},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["mode"] == "session_scoped"

        listed = client.get("/api/v1/persona/profiles")
        assert listed.status_code == 200
        listed_ids = {item["id"] for item in listed.json()}
        assert persona_id in listed_ids

        deleted = client.delete(f"/api/v1/persona/profiles/{persona_id}")
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"

        missing = client.get(f"/api/v1/persona/profiles/{persona_id}")
        assert missing.status_code == 404

    fastapi_app.dependency_overrides.clear()


def test_persona_session_response_includes_scope_audit(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        created = client.post(
            "/api/v1/persona/profiles",
            json={
                "name": "Scoped Analyst",
                "mode": "persistent_scoped",
                "system_prompt": "Use only scoped data.",
            },
        )
        assert created.status_code == 201, created.text
        persona_id = created.json()["id"]

        rules_resp = client.put(
            f"/api/v1/persona/profiles/{persona_id}/scope-rules",
            json={
                "rules": [
                    {"rule_type": "conversation_id", "rule_value": "conv-a", "include": True},
                    {"rule_type": "media_tag", "rule_value": "science", "include": True},
                    {"rule_type": "media_id", "rule_value": "999", "include": False},
                ]
            },
        )
        assert rules_resp.status_code == 200, rules_resp.text

        session = client.post("/api/v1/persona/session", json={"persona_id": persona_id})
        assert session.status_code == 200, session.text
        payload = session.json()
        assert payload["runtime_mode"] == "persistent_scoped"
        assert payload["scope_snapshot_id"]
        audit = payload.get("scope_audit") or {}
        assert audit.get("source_rule_count") == 3
        assert audit.get("include_rule_count") == 2
        assert audit.get("exclude_rule_count") == 1

        session_id = payload["session_id"]
        listed = client.get(f"/api/v1/persona/sessions?persona_id={persona_id}&limit=20")
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        assert any(
            row.get("session_id") == session_id
            and row.get("runtime_mode") == "persistent_scoped"
            and row.get("scope_snapshot_id") == payload["scope_snapshot_id"]
            for row in rows
        )

        detail = client.get(f"/api/v1/persona/sessions/{session_id}")
        assert detail.status_code == 200, detail.text
        detail_payload = detail.json()
        assert detail_payload["session_id"] == session_id
        assert detail_payload["scope_snapshot_id"] == payload["scope_snapshot_id"]
        assert isinstance(detail_payload.get("scope_audit"), dict)

    fastapi_app.dependency_overrides.clear()


def test_persona_profiles_are_user_scoped(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as user_one_client:
        created = user_one_client.post(
            "/api/v1/persona/profiles",
            json={"name": "Private Persona", "mode": "session_scoped"},
        )
        assert created.status_code == 201, created.text
        persona_id = created.json()["id"]

    fastapi_app.dependency_overrides.clear()

    with _client_for_user(2, persona_db) as user_two_client:
        fetched = user_two_client.get(f"/api/v1/persona/profiles/{persona_id}")
        assert fetched.status_code == 404

        sessions = user_two_client.get("/api/v1/persona/sessions")
        assert sessions.status_code == 200
        assert sessions.json() == []

    fastapi_app.dependency_overrides.clear()
