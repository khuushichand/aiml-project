import shutil
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


def _set_jobs_db(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)


def test_media_ingest_jobs_submit_status_cancel(
    test_client,
    auth_headers,
    monkeypatch,
    tmp_path,
):
    _set_jobs_db(monkeypatch, tmp_path)

    data = {
        "media_type": "audio",
        "urls": "https://example.com/audio.mp3",
    }
    resp = test_client.post(
        "/api/v1/media/ingest/jobs",
        data=data,
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("jobs")
    job_id = body["jobs"][0]["id"]

    status_resp = test_client.get(
        f"/api/v1/media/ingest/jobs/{job_id}",
        headers=auth_headers,
    )
    assert status_resp.status_code == 200, status_resp.text
    status_body = status_resp.json()
    assert status_body["media_type"] == "audio"
    assert status_body["source"] == "https://example.com/audio.mp3"
    assert status_body["status"] in {"queued", "processing"}

    cancel_resp = test_client.delete(
        f"/api/v1/media/ingest/jobs/{job_id}",
        headers=auth_headers,
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json().get("status") == "cancelled"

    status_resp = test_client.get(
        f"/api/v1/media/ingest/jobs/{job_id}",
        headers=auth_headers,
    )
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json().get("status") == "cancelled"


def test_media_ingest_jobs_file_staging_payload(
    test_client,
    auth_headers,
    monkeypatch,
    tmp_path,
):
    _set_jobs_db(monkeypatch, tmp_path)

    upload_path = tmp_path / "sample.txt"
    upload_path.write_text("hello ingest staging", encoding="utf-8")

    data = {"media_type": "document"}
    files = [("files", ("sample.txt", upload_path.read_bytes(), "text/plain"))]
    resp = test_client.post(
        "/api/v1/media/ingest/jobs",
        data=data,
        files=files,
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    job_id = body["jobs"][0]["id"]

    from tldw_Server_API.app.core.Jobs.manager import JobManager

    jm = JobManager()
    job = jm.get_job(job_id)
    assert job is not None
    payload = job.get("payload") or {}
    assert payload.get("source_kind") == "file"
    assert payload.get("original_filename") == "sample.txt"
    assert payload.get("temp_dir")
    assert Path(payload["source"]).exists()

    shutil.rmtree(payload["temp_dir"], ignore_errors=True)


def test_media_ingest_jobs_list_by_batch(
    test_client,
    auth_headers,
    monkeypatch,
    tmp_path,
):
    _set_jobs_db(monkeypatch, tmp_path)

    upload_path = tmp_path / "batch.txt"
    upload_path.write_text("batch ingest", encoding="utf-8")

    data = {
        "media_type": "document",
        "urls": "https://example.com/doc-1",
    }
    files = [("files", ("batch.txt", upload_path.read_bytes(), "text/plain"))]
    resp = test_client.post(
        "/api/v1/media/ingest/jobs",
        data=data,
        files=files,
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    batch_id = body.get("batch_id")
    assert batch_id
    job_ids = {job["id"] for job in body.get("jobs", [])}
    assert len(job_ids) == 2

    list_resp = test_client.get(
        f"/api/v1/media/ingest/jobs?batch_id={batch_id}",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    list_body = list_resp.json()
    assert list_body.get("batch_id") == batch_id
    listed_ids = {job["id"] for job in list_body.get("jobs", [])}
    assert listed_ids == job_ids
