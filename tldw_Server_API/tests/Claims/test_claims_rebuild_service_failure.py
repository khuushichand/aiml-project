import time
from contextlib import contextmanager

from tldw_Server_API.app.core.Claims_Extraction import claims_rebuild_service
from tldw_Server_API.app.core.Claims_Extraction.claims_rebuild_service import ClaimsRebuildService, ClaimsRebuildTask


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


def test_claims_rebuild_service_persist_health_uses_managed_media_database(monkeypatch):
    class _FakeDb:
        def __init__(self) -> None:
            self.health_calls: list[dict[str, object]] = []

        def upsert_claims_monitoring_health(self, **kwargs) -> None:
            self.health_calls.append(kwargs)

        def close_connection(self) -> None:
            pass

    svc = ClaimsRebuildService(worker_threads=1)
    fake_db = _FakeDb()
    managed_calls: list[dict[str, object]] = []

    @contextmanager
    def _fake_managed_media_database(client_id, *, initialize=True, **kwargs):
        managed_calls.append(
            {
                "client_id": client_id,
                "initialize": initialize,
                "kwargs": kwargs,
            }
        )
        yield fake_db

    monkeypatch.setattr(claims_rebuild_service, "get_user_media_db_path", lambda _user_id: "/tmp/claims-health.db")
    monkeypatch.setattr(
        claims_rebuild_service,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )
    monkeypatch.setattr(
        claims_rebuild_service,
        "create_media_database",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy raw factory should not be used")),
        raising=False,
    )

    svc._persist_health(force=True)

    assert svc._health_db_initialized is True
    assert len(fake_db.health_calls) == 1
    assert managed_calls == [
        {
            "client_id": claims_rebuild_service.settings.get("SERVER_CLIENT_ID", "SERVER_API_V1"),
            "initialize": True,
            "kwargs": {
                "db_path": "/tmp/claims-health.db",
                "suppress_close_exceptions": claims_rebuild_service._CLAIMS_REBUILD_NONCRITICAL_EXCEPTIONS,
            },
        }
    ]


def test_claims_rebuild_service_process_task_uses_managed_media_database(monkeypatch):
    class _FakeDb:
        def __init__(self) -> None:
            self.deleted_media_ids: list[int] = []

        def get_media_by_id(self, media_id, include_deleted=False, include_trash=False):
            assert media_id == 7
            assert include_deleted is False
            assert include_trash is False
            return {
                "id": media_id,
                "title": "Doc",
                "content": "First. Second.",
            }

        def soft_delete_claims_for_media(self, media_id):
            self.deleted_media_ids.append(media_id)
            return 1

        def close_connection(self) -> None:
            pass

    svc = ClaimsRebuildService(worker_threads=1)
    fake_db = _FakeDb()
    managed_calls: list[dict[str, object]] = []
    store_calls: list[dict[str, object]] = []

    @contextmanager
    def _fake_managed_media_database(client_id, *, initialize=True, **kwargs):
        managed_calls.append(
            {
                "client_id": client_id,
                "initialize": initialize,
                "kwargs": kwargs,
            }
        )
        yield fake_db

    monkeypatch.setattr(
        claims_rebuild_service,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )
    monkeypatch.setattr(
        claims_rebuild_service,
        "create_media_database",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy raw factory should not be used")),
        raising=False,
    )
    monkeypatch.setattr(
        claims_rebuild_service,
        "chunk_for_embedding",
        lambda content, file_name: [
            {
                "text": content,
                "metadata": {"chunk_index": 0},
            }
        ],
    )
    monkeypatch.setattr(claims_rebuild_service, "resolve_claims_job_budget", lambda settings: "budget")
    monkeypatch.setattr(
        claims_rebuild_service,
        "extract_claims_for_chunks",
        lambda chunks, extractor_mode, max_per_chunk, budget: [
            {
                "chunk_index": 0,
                "claim_text": "First.",
            }
        ],
    )

    def _fake_store_claims(db, media_id, chunk_texts_by_index, claims):
        store_calls.append(
            {
                "db": db,
                "media_id": media_id,
                "chunk_texts_by_index": chunk_texts_by_index,
                "claims": claims,
            }
        )
        return 1

    monkeypatch.setattr(claims_rebuild_service, "store_claims", _fake_store_claims)

    svc._process_task(ClaimsRebuildTask(media_id=7, db_path="/tmp/claims-task.db"))

    assert fake_db.deleted_media_ids == [7]
    assert len(store_calls) == 1
    assert managed_calls == [
        {
            "client_id": claims_rebuild_service.settings.get("SERVER_CLIENT_ID", "SERVER_API_V1"),
            "initialize": False,
            "kwargs": {
                "db_path": "/tmp/claims-task.db",
                "suppress_close_exceptions": claims_rebuild_service._CLAIMS_REBUILD_NONCRITICAL_EXCEPTIONS,
            },
        }
    ]
