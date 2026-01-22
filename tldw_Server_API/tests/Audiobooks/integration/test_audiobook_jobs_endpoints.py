import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.audiobooks import router as audiobooks_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

pytestmark = pytest.mark.integration


@pytest.fixture()
def client_audiobooks_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))

    app = FastAPI()
    app.include_router(audiobooks_router, prefix="/api/v1")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def job_payload():
    return {
        "project_title": "Example Book",
        "source": {"input_type": "txt", "raw_text": "Hello world."},
        "chapters": [
            {"chapter_id": "ch_001", "include": True, "voice": "af_heart", "speed": 1.0}
        ],
        "output": {"merge": True, "per_chapter": True, "formats": ["mp3"]},
        "subtitles": {"formats": ["srt"], "mode": "sentence", "variant": "wide"},
        "queue": {"priority": 3, "batch_group": "batch_01"},
    }


def test_create_job_status_and_artifacts(client_audiobooks_jobs, job_payload):
    create_resp = client_audiobooks_jobs.post("/api/v1/audiobooks/jobs", json=job_payload)
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["status"] == "queued"
    assert isinstance(data["job_id"], int)
    assert data["project_id"].startswith("abk_")

    from tldw_Server_API.app.core.Jobs.manager import JobManager

    jm = JobManager()
    job = jm.get_job(int(data["job_id"]))
    assert job is not None
    assert job.get("batch_group") == "batch_01"

    status_resp = client_audiobooks_jobs.get(f"/api/v1/audiobooks/jobs/{data['job_id']}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["job_id"] == data["job_id"]
    assert status_data["project_id"] == data["project_id"]
    assert status_data["status"] in {"queued", "processing", "completed", "failed", "canceled"}

    artifacts_resp = client_audiobooks_jobs.get(f"/api/v1/audiobooks/jobs/{data['job_id']}/artifacts")
    assert artifacts_resp.status_code == 200
    artifacts = artifacts_resp.json()
    assert artifacts["project_id"] == data["project_id"]
    assert isinstance(artifacts["artifacts"], list)
