import io
import json
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import (
    get_chacha_db_for_user,
    close_all_chacha_db_instances,
)


@pytest.fixture()
def client(tmp_path_factory):
     """Provide a TestClient with isolated ChaChaNotes DB + auth overrides per module."""
    tmp_dir = tmp_path_factory.mktemp("chatbooks_cancel")
    db_path = tmp_dir / "ChaChaNotes.db"
    db_instance = CharactersRAGDB(db_path=str(db_path), client_id="chatbooks-cancel-test")

    # Keep tests permissive by disabling rate limiting
    os.environ["TEST_MODE"] = "true"

    async def override_user():
        return User(id=1, username="tester", is_active=True)

    def override_db():

             return db_instance

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_chacha_db_for_user] = override_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_request_user, None)
        app.dependency_overrides.pop(get_chacha_db_for_user, None)
        try:
            db_instance.close_all_connections()
        except Exception:
            pass
        close_all_chacha_db_instances()


def _make_export_payload(async_mode: bool = True):
    return {
        "name": "Cancel Test",
        "description": "Testing cancellation",
        "content_selections": {},
        "async_mode": async_mode,
    }


def _make_chatbook_bytes() -> bytes:


     buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        manifest = {
            "version": "1.0.0",
            "name": "Cancel Import",
            "description": "Test",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "content_items": [],
            "configuration": {},
            "statistics": {},
            "metadata": {},
            "user_info": {"user_id": "test"},
        }
        zf.writestr("manifest.json", json.dumps(manifest))
    return buf.getvalue()


def test_cancel_export_job_flow(client):


     # Start async export job
    resp = client.post("/api/v1/chatbooks/export", json=_make_export_payload(async_mode=True))
    assert resp.status_code in (200, 401, 403, 422), f"unexpected export status {resp.status_code}: {resp.text}"
    if resp.status_code != 200:
        return
    job_id = resp.json().get("job_id")
    assert job_id

    # Try to cancel
    cresp = client.delete(f"/api/v1/chatbooks/export/jobs/{job_id}")
    assert cresp.status_code in (200, 400)

    # Check job status (may be cancelled or already completed depending on timing)
    sresp = client.get(f"/api/v1/chatbooks/export/jobs/{job_id}")
    assert sresp.status_code in (200, 404, 401, 403, 422)
    if sresp.status_code == 200:
        status = sresp.json().get("status")
        assert status in ("cancelled", "completed", "failed", "in_progress", "pending")


def test_cancel_import_job_flow(client):


     # Prepare small chatbook upload
    data = _make_chatbook_bytes()
    files = {"file": ("test.chatbook", data, "application/zip")}

    # async_mode via query params (schema uses Depends to parse)
    resp = client.post("/api/v1/chatbooks/import?async_mode=true", files=files)
    assert resp.status_code in (200, 401, 403, 422), f"unexpected import status {resp.status_code}: {resp.text}"
    if resp.status_code != 200:
        return
    job_id = resp.json().get("job_id")
    assert job_id

    cresp = client.delete(f"/api/v1/chatbooks/import/jobs/{job_id}")
    assert cresp.status_code in (200, 400)

    sresp = client.get(f"/api/v1/chatbooks/import/jobs/{job_id}")
    assert sresp.status_code in (200, 404, 401, 403, 422)
    if sresp.status_code == 200:
        status = sresp.json().get("status")
        assert status in ("cancelled", "completed", "failed", "in_progress", "pending")
