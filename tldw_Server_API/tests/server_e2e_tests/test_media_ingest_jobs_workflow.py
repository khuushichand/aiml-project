import os
import time
from pathlib import Path
from uuid import uuid4

import pytest


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "quarantined"}


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sample_doc_path() -> Path:
    return _repo_root() / "tldw_Server_API/tests/Media_Ingestion_Modification/test_media/sample.txt"


@pytest.mark.e2e
def test_media_ingest_jobs_local_file_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    sample_path = _sample_doc_path()

    submit_resp = page.request.post(
        "/api/v1/media/ingest/jobs",
        headers=headers,
        multipart={
            "media_type": "document",
            "title": f"E2E ingest job {suffix}",
            "perform_analysis": "false",
            "files": {
                "name": sample_path.name,
                "mimeType": "text/plain",
                "buffer": sample_path.read_bytes(),
            },
        },
    )
    _require_ok(submit_resp, "submit ingest job")
    submit_payload = submit_resp.json()
    batch_id = submit_payload["batch_id"]
    jobs = submit_payload.get("jobs", [])
    assert jobs, "Expected at least one ingest job"
    job_id = jobs[0]["id"]

    latest_status = None
    for _ in range(3):
        status_resp = page.request.get(f"/api/v1/media/ingest/jobs/{job_id}", headers=headers)
        _require_ok(status_resp, "poll ingest job")
        latest_status = status_resp.json()
        if str(latest_status.get("status", "")).lower() in TERMINAL_STATUSES:
            break
        time.sleep(0.5)

    list_resp = page.request.get(
        "/api/v1/media/ingest/jobs",
        headers=headers,
        params={"batch_id": batch_id},
    )
    _require_ok(list_resp, "list ingest jobs")
    list_payload = list_resp.json()
    listed_ids = {job.get("id") for job in list_payload.get("jobs", [])}
    assert job_id in listed_ids

    status_value = str((latest_status or {}).get("status", "")).lower()
    if status_value and status_value not in TERMINAL_STATUSES:
        cancel_resp = page.request.delete(
            f"/api/v1/media/ingest/jobs/{job_id}",
            headers=headers,
            params={"reason": "e2e cleanup"},
        )
        _require_ok(cancel_resp, "cancel ingest job")
        cancel_payload = cancel_resp.json()
        assert cancel_payload.get("status") == "cancelled"


@pytest.mark.e2e
def test_media_ingest_jobs_external_url_workflow(page, server_url):
    if os.getenv("TLDW_E2E_EXTERNAL_MEDIA_INGEST", "").lower() not in {"1", "true", "yes", "y", "on"}:
        pytest.skip("External media ingest disabled; set TLDW_E2E_EXTERNAL_MEDIA_INGEST=1 to enable.")

    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    submit_resp = page.request.post(
        "/api/v1/media/ingest/jobs",
        headers=headers,
        form={
            "media_type": "document",
            "title": f"E2E ingest URL {suffix}",
            "perform_analysis": "false",
            "urls": "https://example.com/",
        },
    )
    _require_ok(submit_resp, "submit ingest job (url)")
    submit_payload = submit_resp.json()
    batch_id = submit_payload["batch_id"]
    jobs = submit_payload.get("jobs", [])
    assert jobs, "Expected at least one ingest job"
    job_id = jobs[0]["id"]

    status_resp = page.request.get(f"/api/v1/media/ingest/jobs/{job_id}", headers=headers)
    _require_ok(status_resp, "poll ingest job (url)")
    status_payload = status_resp.json()

    list_resp = page.request.get(
        "/api/v1/media/ingest/jobs",
        headers=headers,
        params={"batch_id": batch_id},
    )
    _require_ok(list_resp, "list ingest jobs (url)")
    list_payload = list_resp.json()
    listed_ids = {job.get("id") for job in list_payload.get("jobs", [])}
    assert job_id in listed_ids

    status_value = str(status_payload.get("status", "")).lower()
    if status_value and status_value not in TERMINAL_STATUSES:
        cancel_resp = page.request.delete(
            f"/api/v1/media/ingest/jobs/{job_id}",
            headers=headers,
            params={"reason": "e2e cleanup"},
        )
        _require_ok(cancel_resp, "cancel ingest job (url)")
        cancel_payload = cancel_resp.json()
        assert cancel_payload.get("status") == "cancelled"
