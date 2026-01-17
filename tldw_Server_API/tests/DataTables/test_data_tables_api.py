import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.data_tables import router as data_tables_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


pytestmark = pytest.mark.integration


def _principal_override():
    async def _override(request=None) -> AuthPrincipal:
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="test-user",
            token_type="single_user",
            jti=None,
            roles=["admin"],
            permissions=["media.create", "media.read", "media.update", "media.delete"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            request.state.auth = AuthContext(
                principal=principal,
                ip=None,
                user_agent=None,
                request_id=None,
            )
        return principal

    return _override


def _build_app(db_path, monkeypatch) -> FastAPI:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path.parent / "jobs.db"))
    app = FastAPI()
    app.include_router(data_tables_router, prefix="/api/v1", tags=["data-tables"])

    async def _override_user() -> User:
        return User(id=1, username="tester", email=None, is_active=True, is_admin=True)

    async def _override_db():
        override_db = MediaDatabase(db_path=str(db_path), client_id="test_client")
        try:
            yield override_db
        finally:
            override_db.close_connection()

    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[get_auth_principal] = _principal_override()
    app.dependency_overrides[get_media_db_for_user] = _override_db
    return app


def test_generate_and_get_data_table(tmp_path, monkeypatch):
    db_path = tmp_path / "media.db"
    app = _build_app(db_path, monkeypatch)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/data-tables/generate",
            json={
                "name": "Test Table",
                "prompt": "Extract data",
                "description": "demo",
                "sources": [{"source_type": "chat", "source_id": "chat_1", "title": "Chat 1"}],
                "column_hints": [{"name": "Name", "type": "text"}],
                "model": "gpt-test",
                "max_rows": 10,
            },
        )
        assert resp.status_code == 202, resp.text
        payload = resp.json()
        table_uuid = payload["table"]["uuid"]
        job_id = payload["job_id"]
        assert table_uuid
        assert job_id

        detail = client.get(f"/api/v1/data-tables/{table_uuid}")
        assert detail.status_code == 200, detail.text
        detail_payload = detail.json()
        assert detail_payload["table"]["uuid"] == table_uuid
        assert detail_payload["sources"]


def test_list_update_delete_data_table(tmp_path, monkeypatch):
    db_path = tmp_path / "media.db"
    seed_db = MediaDatabase(db_path=str(db_path), client_id="test_client")
    table = seed_db.create_data_table(
        name="Seed Table",
        prompt="Seed prompt",
        description="Seed",
        status="ready",
        row_count=1,
    )
    table_id = int(table.get("id"))
    seed_db.insert_data_table_columns(
        table_id,
        [
            {"name": "Name", "type": "text", "position": 0},
            {"name": "Value", "type": "number", "position": 1},
        ],
    )
    seed_db.insert_data_table_rows(
        table_id,
        [{"row_index": 0, "data": {"Name": "Alpha", "Value": 10}}],
    )
    seed_db.close_connection()

    app = _build_app(db_path, monkeypatch)
    with TestClient(app) as client:
        resp = client.get("/api/v1/data-tables")
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["count"] >= 1

        table_uuid = table.get("uuid")
        patch = client.patch(
            f"/api/v1/data-tables/{table_uuid}",
            json={"name": "Renamed Table"},
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["name"] == "Renamed Table"

        delete = client.delete(f"/api/v1/data-tables/{table_uuid}")
        assert delete.status_code == 200, delete.text
        assert delete.json()["success"] is True


def test_job_status_and_cancel(tmp_path, monkeypatch):
    db_path = tmp_path / "media.db"
    app = _build_app(db_path, monkeypatch)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/data-tables/generate",
            json={
                "name": "Job Table",
                "prompt": "Extract data",
                "sources": [{"source_type": "chat", "source_id": "chat_job"}],
            },
        )
        assert resp.status_code == 202, resp.text
        job_id = resp.json()["job_id"]

        status_resp = client.get(f"/api/v1/data-tables/jobs/{job_id}")
        assert status_resp.status_code == 200, status_resp.text
        assert status_resp.json()["id"] == job_id

        cancel_resp = client.delete(f"/api/v1/data-tables/jobs/{job_id}")
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["success"] is True
