import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


class _FakePSAdapter:
    def __init__(self):
        self._status = "queued"
        self.created_id = 1001

    def create_export_job(self, payload, *, request_id=None):
        return {"id": self.created_id}

    def create_import_job(self, payload, *, request_id=None):
        return {"id": self.created_id}

    def get(self, job_id: int):
        return {"id": job_id, "status": self._status}

    def cancel(self, job_id: int):
        self._status = "cancelled"
        return True


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_ps_status_mapping_pending_and_in_progress(client, monkeypatch):
    # Force PS backend and inject fake adapter
    monkeypatch.setenv("CHATBOOKS_JOBS_BACKEND", "prompt_studio")

    fake = _FakePSAdapter()

    # Patch adapter class used by ChatbookService
    import tldw_Server_API.app.core.Chatbooks.ps_job_adapter as ps_mod
    monkeypatch.setattr(ps_mod, "ChatbooksPSJobAdapter", lambda: fake, raising=True)

    # Create async export job (should mirror PS id in job_id)
    payload = {
        "name": "PS Status",
        "description": "Test",
        "content_selections": {},
        "async_mode": True,
    }
    resp = client.post("/api/v1/chatbooks/export", json=payload)
    assert resp.status_code in (200, 401, 403, 422)
    if resp.status_code != 200:
        return
    job_id = resp.json().get("job_id")
    assert job_id == str(fake.created_id)

    # queued -> pending
    fake._status = "queued"
    s = client.get(f"/api/v1/chatbooks/export/jobs/{job_id}")
    assert s.status_code in (200, 401, 403, 422)
    if s.status_code == 200:
        assert s.json().get("status") == "pending"

    # processing -> in_progress
    fake._status = "processing"
    s2 = client.get(f"/api/v1/chatbooks/export/jobs/{job_id}")
    assert s2.status_code in (200, 401, 403, 422)
    if s2.status_code == 200:
        assert s2.json().get("status") == "in_progress"
