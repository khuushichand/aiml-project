import pytest

from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase


pytestmark = pytest.mark.integration


def test_sqlite_acquire_reclaim_without_advisory(tmp_path):
    db_path = tmp_path / "ps_sqlite_acquire.db"
    db = PromptStudioDatabase(str(db_path), "sqlite-acquire")

    job = db.create_job(job_type="optimization", entity_id=1, payload={})
    assert job.get("id")

    acquired = db.acquire_next_job()
    assert acquired is not None
    assert acquired.get("status") == "processing"

    # No second acquire while lease valid
    assert db.acquire_next_job() is None

    # Force lease expiration and reclaim
    db._execute(
        "UPDATE prompt_studio_job_queue SET leased_until = DATETIME('now', '-2 seconds') WHERE id = ?",
        (acquired["id"],),
    )
    reclaimed = db.acquire_next_job()
    assert reclaimed is not None
    assert reclaimed.get("id") == acquired.get("id")
