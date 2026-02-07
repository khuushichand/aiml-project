import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


pytestmark = pytest.mark.unit


@pytest.fixture
def media_ingest_jobs_client(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("SANDBOX_WS_REDIS_FANOUT", "0")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("SANDBOX_REDIS_URL", raising=False)
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)

    from tldw_Server_API.app.api.v1.endpoints.media.ingest_jobs import router as ingest_jobs_router

    app = FastAPI()
    app.include_router(ingest_jobs_router, prefix="/api/v1/media", tags=["media"])
    with TestClient(app) as client:
        yield client


def test_submit_media_ingest_jobs_creates_one_job_per_item(
    media_ingest_jobs_client,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))

    captured = []

    from tldw_Server_API.app.core.Jobs import manager as jobs_manager

    def fake_create_job(
        self,
        *,
        domain,
        queue,
        job_type,
        payload,
        owner_user_id,
        project_id=None,
        priority=5,
        max_retries=3,
        available_at=None,
        idempotency_key=None,
        request_id=None,
        trace_id=None,
    ):
        captured.append(
            {
                "domain": domain,
                "queue": queue,
                "job_type": job_type,
                "payload": payload,
                "owner_user_id": owner_user_id,
                "request_id": request_id,
                "trace_id": trace_id,
            }
        )
        return {"id": len(captured), "uuid": f"u{len(captured)}", "status": "queued"}

    monkeypatch.setattr(jobs_manager.JobManager, "create_job", fake_create_job, raising=True)

    upload_path = tmp_path / "sample.txt"
    upload_path.write_text("hello ingest job", encoding="utf-8")

    data = {
        "media_type": "document",
        "urls": "https://example.com/doc1",
    }
    files = [
        ("files", ("sample.txt", upload_path.read_bytes(), "text/plain")),
    ]

    resp = media_ingest_jobs_client.post(
        "/api/v1/media/ingest/jobs",
        data=data,
        files=files,
        headers={"X-API-KEY": "test-api-key-12345"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("batch_id")
    assert len(body.get("jobs", [])) == 2

    payloads = [item["payload"] for item in captured]
    url_payload = next(item for item in payloads if item.get("source_kind") == "url")
    file_payload = next(item for item in payloads if item.get("source_kind") == "file")

    assert url_payload["source"] == "https://example.com/doc1"
    assert file_payload["original_filename"] == "sample.txt"
    assert file_payload.get("temp_dir")
    assert Path(file_payload["source"]).exists()

    shutil.rmtree(file_payload["temp_dir"], ignore_errors=True)
