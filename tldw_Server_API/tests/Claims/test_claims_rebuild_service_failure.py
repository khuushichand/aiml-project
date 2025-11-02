import time

from tldw_Server_API.app.services.claims_rebuild_service import ClaimsRebuildService, ClaimsRebuildTask


def test_claims_rebuild_service_worker_handles_failure(monkeypatch):
    svc = ClaimsRebuildService(worker_threads=1)
    # Monkeypatch _process_task to raise an error
    def _boom(task: ClaimsRebuildTask):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(svc, "_process_task", _boom)
    svc.start()
    try:
        svc.submit(media_id=123, db_path=":memory:")
        # Give worker a moment to process
        time.sleep(0.2)
        stats = svc.get_stats()
        assert stats.get("enqueued", 0) >= 1
        # Should have recorded a failure and not crash
        assert stats.get("failed", 0) >= 1
        # processed should remain 0 because _process_task failed
        assert stats.get("processed", 0) == 0
    finally:
        svc.stop()
