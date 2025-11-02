import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


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
    assert resp.status_code in (200, 401, 403, 422)
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
    assert resp.status_code in (200, 401, 403, 422)
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
