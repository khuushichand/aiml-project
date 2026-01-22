import asyncio
import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.audiobooks import router as audiobooks_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.services import audiobook_jobs_worker

pytestmark = pytest.mark.integration


def _alignment_payload_for(text: str) -> dict:
    words = text.split()
    payload_words = []
    start = 0
    for idx, word in enumerate(words):
        end = start + 500
        payload_words.append(
            {
                "word": word,
                "start_ms": start,
                "end_ms": end,
                "char_start": None,
                "char_end": None,
            }
        )
        start = end
    return {
        "engine": "kokoro",
        "sample_rate": 24000,
        "words": payload_words,
    }


@pytest.fixture()
def user_base_dir(tmp_path, monkeypatch):
    base_dir = tmp_path / "user_dbs"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    return base_dir


@pytest.fixture()
def jobs_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path))
    return db_path


@pytest.fixture()
def fake_tts(monkeypatch):
    async def _fake_generate(*_args, **_kwargs):
        text = _kwargs.get("text") or ""
        return b"FAKEAUDIO", _alignment_payload_for(text)

    monkeypatch.setattr(audiobook_jobs_worker, "_generate_tts_audio", _fake_generate)


def _build_job_payload(project_id: str) -> dict:
    return {
        "project_title": "Test Book",
        "source": {"input_type": "txt", "raw_text": "Hello world."},
        "chapters": [
            {"chapter_id": "ch_001", "include": True, "voice": "af_heart", "speed": 1.0}
        ],
        "output": {"merge": False, "per_chapter": True, "formats": ["mp3"]},
        "subtitles": {"formats": ["srt"], "mode": "sentence", "variant": "wide"},
        "metadata": {"tts_model": "kokoro"},
        "project_id": project_id,
    }


def test_audiobook_worker_creates_outputs(user_base_dir, jobs_db_path, fake_tts):
    user_id = 1
    project_id = "abk_test01"
    payload = _build_job_payload(project_id)

    job_manager = JobManager()
    job = job_manager.create_job(
        domain="audiobooks",
        queue="default",
        job_type="audiobook_generate",
        payload=payload,
        owner_user_id=str(user_id),
        priority=5,
    )

    acquired = job_manager.acquire_next_job(
        domain="audiobooks",
        queue="default",
        lease_seconds=60,
        worker_id="test-worker",
    )
    assert acquired is not None

    asyncio.run(
        audiobook_jobs_worker.process_audiobook_job(
            acquired,
            job_manager=job_manager,
            worker_id="test-worker",
        )
    )

    job_row = job_manager.get_job(int(job["id"]))
    assert job_row is not None
    assert job_row.get("status") == "completed"

    collections_db = CollectionsDatabase(user_id)
    outputs, _total = collections_db.list_output_artifacts(job_id=int(job["id"]), limit=50, offset=0)
    types = {row.type for row in outputs}
    assert "audiobook_audio" in types
    assert "audiobook_subtitle" in types
    assert "audiobook_alignment" in types

    outputs_dir = DatabasePaths.get_user_outputs_dir(user_id)
    for row in outputs:
        path = outputs_dir / row.storage_path
        assert path.exists()
        if row.type == "audiobook_subtitle":
            assert "Hello world" in path.read_text(encoding="utf-8")
        if row.type == "audiobook_alignment":
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload.get("engine") == "kokoro"


@pytest.fixture()
def client_user_only(monkeypatch, user_base_dir):
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "false")
    existing_enable = (os.getenv("ROUTES_ENABLE") or "").strip()
    enable_parts = [p for p in existing_enable.replace(" ", ",").split(",") if p]
    if "audiobooks" not in [p.lower() for p in enable_parts]:
        enable_parts.append("audiobooks")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(enable_parts))

    app = FastAPI()
    app.include_router(audiobooks_router, prefix="/api/v1")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_audiobook_artifacts_endpoint_lists_outputs(
    client_user_only,
    jobs_db_path,
    fake_tts,
):
    create_payload = {
        "project_title": "Test Book",
        "source": {"input_type": "txt", "raw_text": "Hello world."},
        "chapters": [
            {"chapter_id": "ch_001", "include": True, "voice": "af_heart", "speed": 1.0}
        ],
        "output": {"merge": False, "per_chapter": True, "formats": ["mp3"]},
        "subtitles": {"formats": ["srt"], "mode": "sentence", "variant": "wide"},
    }
    resp = client_user_only.post("/api/v1/audiobooks/jobs", json=create_payload)
    assert resp.status_code == 200
    data = resp.json()
    job_id = data["job_id"]

    job_manager = JobManager()
    acquired = job_manager.acquire_next_job(
        domain="audiobooks",
        queue="default",
        lease_seconds=60,
        worker_id="test-worker",
    )
    assert acquired is not None

    asyncio.run(
        audiobook_jobs_worker.process_audiobook_job(
            acquired,
            job_manager=job_manager,
            worker_id="test-worker",
        )
    )

    artifacts_resp = client_user_only.get(f"/api/v1/audiobooks/jobs/{job_id}/artifacts")
    assert artifacts_resp.status_code == 200
    artifacts = artifacts_resp.json()["artifacts"]
    assert artifacts
    first = artifacts[0]
    assert first["output_id"]
    assert first["download_url"].endswith(f"/api/v1/outputs/{first['output_id']}/download")
