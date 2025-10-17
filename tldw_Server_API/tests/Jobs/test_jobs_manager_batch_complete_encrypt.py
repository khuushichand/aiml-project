import os
import base64
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.mark.unit
def test_batch_complete_applies_encryption_with_and_without_domain(tmp_path, monkeypatch):
    # Enable encryption for domain SECURE
    monkeypatch.setenv("JOBS_ENCRYPT_SECURE", "true")
    # Provide a 32-byte AES key for encryption routines
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_ENC_KEY", base64.b64encode(b"0" * 32).decode("ascii"))

    db_path = tmp_path / "jobs_enc.db"
    jm = JobManager(db_path=db_path)
    domain = "secure"
    queue = "default"

    # Create two jobs and acquire them so they are in processing state
    j1 = jm.create_job(domain=domain, queue=queue, job_type="enc1", payload={}, owner_user_id=None)
    j2 = jm.create_job(domain=domain, queue=queue, job_type="enc2", payload={}, owner_user_id=None)

    a1 = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id="w")
    a2 = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id="w")
    assert a1 and a2

    # Complete via batch: one with explicit domain, one without (manager should fetch domain)
    items = [
        {"job_id": int(a1["id"]), "result": {"ok": True}, "domain": domain},
        {"job_id": int(a2["id"]), "result": {"ok": True}},
    ]
    done = jm.batch_complete_jobs(items)
    assert done == 2

    # Disable decryption to validate that encrypted envelope is stored
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_ENC_KEY", "")

    r1 = jm.get_job(int(a1["id"]))
    r2 = jm.get_job(int(a2["id"]))
    assert r1 and r2
    # Results should be encrypted envelopes
    assert isinstance(r1.get("result"), dict) and "_encrypted" in r1.get("result")
    assert isinstance(r2.get("result"), dict) and "_encrypted" in r2.get("result")
