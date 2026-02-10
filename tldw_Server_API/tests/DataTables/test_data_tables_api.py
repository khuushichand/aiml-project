import asyncio

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.data_tables import (
    _wait_for_job_completion,
    get_job_manager,
)
from tldw_Server_API.app.api.v1.schemas.data_tables_schemas import DATA_TABLES_MAX_ROWS_LIMIT
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


pytestmark = pytest.mark.integration


def test_generate_and_get_data_table(tmp_path, data_tables_app_factory):
    db_path = tmp_path / "media.db"
    app, _ = data_tables_app_factory(db_path)

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


def test_list_update_delete_data_table(tmp_path, data_tables_app_factory):
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
    columns = seed_db.list_data_table_columns(table_id)
    column_ids = [col.get("column_id") for col in columns]
    seed_db.insert_data_table_rows(
        table_id,
        [{"row_index": 0, "row_json": {column_ids[0]: "Alpha", column_ids[1]: 10}}],
    )
    seed_db.close_connection()

    app, _ = data_tables_app_factory(db_path)
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


def test_job_status_and_cancel(tmp_path, data_tables_app_factory):
    db_path = tmp_path / "media.db"
    app, _ = data_tables_app_factory(db_path)

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


def test_data_table_job_status_rejects_boolean_admin_without_claims(tmp_path, data_tables_app_factory):
    db_path = tmp_path / "media.db"
    app, _ = data_tables_app_factory(db_path)

    class _StubJobManager:
        def get_job(self, _job_id: int):
            return {
                "id": 9,
                "domain": "data_tables",
                "owner_user_id": "2",
                "status": "queued",
                "job_type": "data_table_generate",
            }

    async def _principal_override():
        return AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject=None,
            token_type="access",
            jti=None,
            roles=["user"],
            permissions=["media.read"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )

    app.dependency_overrides[get_job_manager] = lambda: _StubJobManager()
    app.dependency_overrides[get_auth_principal] = _principal_override
    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/data-tables/jobs/9")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_job_manager, None)
        app.dependency_overrides.pop(get_auth_principal, None)


def test_generate_uses_configured_data_tables_queue(tmp_path, data_tables_app_factory, monkeypatch):
    db_path = tmp_path / "media.db"
    monkeypatch.setenv("DATA_TABLES_JOBS_QUEUE", "data-tables-custom")
    app, _ = data_tables_app_factory(db_path)

    captured: dict[str, object] = {}

    class _StubJobManager:
        def create_job(self, **kwargs):
            captured.update(kwargs)
            return {"id": 101, "uuid": "job-101", "status": "queued"}

    app.dependency_overrides[get_job_manager] = lambda: _StubJobManager()
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/data-tables/generate",
                json={
                    "name": "Queue Table",
                    "prompt": "Extract data",
                    "sources": [{"source_type": "chat", "source_id": "chat_queue"}],
                },
            )
            assert resp.status_code == 202, resp.text
            assert captured.get("queue") == "data-tables-custom"
    finally:
        app.dependency_overrides.pop(get_job_manager, None)


def test_regenerate_uses_configured_data_tables_queue(tmp_path, data_tables_app_factory, monkeypatch):
    db_path = tmp_path / "media.db"
    monkeypatch.setenv("DATA_TABLES_JOBS_QUEUE", "data-tables-custom")

    seed_db = MediaDatabase(db_path=str(db_path), client_id="test_client")
    table = seed_db.create_data_table(
        name="Regen Seed",
        prompt="Regenerate me",
        status="ready",
    )
    table_id = int(table.get("id"))
    seed_db.insert_data_table_sources(
        table_id,
        [{"source_type": "chat", "source_id": "chat_source"}],
    )
    seed_db.close_connection()

    app, _ = data_tables_app_factory(db_path)
    captured: dict[str, object] = {}

    class _StubJobManager:
        def create_job(self, **kwargs):
            captured.update(kwargs)
            return {"id": 102, "uuid": "job-102", "status": "queued"}

    app.dependency_overrides[get_job_manager] = lambda: _StubJobManager()
    try:
        with TestClient(app) as client:
            resp = client.post(f"/api/v1/data-tables/{table.get('uuid')}/regenerate", json={})
            assert resp.status_code == 202, resp.text
            assert captured.get("queue") == "data-tables-custom"
    finally:
        app.dependency_overrides.pop(get_job_manager, None)


def test_regenerate_after_admin_patch_preserves_table_owner(tmp_path, data_tables_app_factory):
    db_path = tmp_path / "media.db"
    seed_db = MediaDatabase(db_path=str(db_path), client_id="seed_client")
    table = seed_db.create_data_table(
        name="Owner-Segregated Table",
        prompt="Regenerate me",
        status="ready",
        owner_user_id=77,
    )
    table_id = int(table.get("id"))
    seed_db.insert_data_table_sources(
        table_id,
        [{"source_type": "chat", "source_id": "chat_owner_77"}],
        owner_user_id=77,
    )
    seed_db.close_connection()

    app, _ = data_tables_app_factory(db_path)
    captured: dict[str, object] = {}

    class _StubJobManager:
        def create_job(self, **kwargs):
            captured.update(kwargs)
            return {"id": 103, "uuid": "job-103", "status": "queued"}

    app.dependency_overrides[get_job_manager] = lambda: _StubJobManager()
    try:
        with TestClient(app) as client:
            patch = client.patch(
                f"/api/v1/data-tables/{table.get('uuid')}",
                json={"name": "Renamed by admin"},
            )
            assert patch.status_code == 200, patch.text

            regen = client.post(f"/api/v1/data-tables/{table.get('uuid')}/regenerate", json={})
            assert regen.status_code == 202, regen.text
            payload = captured.get("payload")
            assert isinstance(payload, dict)
            assert payload.get("user_id") == "77"
    finally:
        app.dependency_overrides.pop(get_job_manager, None)

    verify_db = MediaDatabase(db_path=str(db_path), client_id="verify_client")
    try:
        assert verify_db.get_data_table(table_id, owner_user_id=77) is not None
        assert verify_db.get_data_table(table_id, owner_user_id="verify_client") is None
    finally:
        verify_db.close_connection()


def test_update_content_rejects_duplicate_row_indexes(tmp_path, data_tables_app_factory):
    db_path = tmp_path / "media.db"
    seed_db = MediaDatabase(db_path=str(db_path), client_id="test_client")
    table = seed_db.create_data_table(name="Edit Table", prompt="p", status="ready")
    seed_db.close_connection()

    app, _ = data_tables_app_factory(db_path)
    with TestClient(app) as client:
        resp = client.put(
            f"/api/v1/data-tables/{table.get('uuid')}/content",
            json={
                "columns": [
                    {"name": "Name", "type": "text"},
                    {"name": "Score", "type": "number"},
                ],
                "rows": [
                    {"row_index": 0, "data": {"Name": "Alice", "Score": 95}},
                    {"row_index": 0, "data": {"Name": "Bob", "Score": 88}},
                ],
            },
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == "duplicate_row_index"


def test_generate_rejects_max_rows_above_limit(tmp_path, data_tables_app_factory):
    db_path = tmp_path / "media.db"
    app, _ = data_tables_app_factory(db_path)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/data-tables/generate",
            json={
                "name": "Too Many Rows",
                "prompt": "Extract data",
                "sources": [{"source_type": "chat", "source_id": "chat_1"}],
                "max_rows": DATA_TABLES_MAX_ROWS_LIMIT + 1,
            },
        )
        assert resp.status_code == 422, resp.text


def test_wait_for_completion_treats_quarantined_as_terminal():
    class _StubJobManager:
        def get_job(self, _job_id: int):
            return {"id": 99, "status": "quarantined"}

    job = asyncio.run(
        _wait_for_job_completion(
            _StubJobManager(),
            99,
            timeout_seconds=1,
            poll_interval=0.0,
        )
    )
    assert job["status"] == "quarantined"
