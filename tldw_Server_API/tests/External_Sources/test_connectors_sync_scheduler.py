from __future__ import annotations

import importlib

import pytest


@pytest.mark.asyncio
@pytest.mark.unit
async def test_connectors_sync_scheduler_scan_enqueues_renewal_repair_and_incremental(monkeypatch):
    try:
        scheduler_mod = importlib.import_module(
            "tldw_Server_API.app.services.connectors_sync_scheduler"
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - red phase
        pytest.fail(str(exc))

    class _DummyTx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _DummyPool:
        def transaction(self):
            return _DummyTx()

    async def _fake_get_db_pool():
        return _DummyPool()

    async def _fake_list_sources_for_scheduler(db):
        return [
            {
                "id": 11,
                "user_id": 1,
                "provider": "drive",
                "enabled": True,
                "sync_mode": "hybrid",
                "needs_full_rescan": False,
                "webhook_status": "active",
                "webhook_subscription_id": "drive-chan-1",
                "webhook_expires_at": "2026-03-06T22:05:00Z",
            },
            {
                "id": 12,
                "user_id": 2,
                "provider": "onedrive",
                "enabled": True,
                "sync_mode": "hybrid",
                "needs_full_rescan": True,
                "webhook_status": None,
                "webhook_subscription_id": None,
                "webhook_expires_at": None,
            },
            {
                "id": 13,
                "user_id": 3,
                "provider": "drive",
                "enabled": True,
                "sync_mode": "poll",
                "needs_full_rescan": False,
                "webhook_status": None,
                "webhook_subscription_id": None,
                "webhook_expires_at": None,
            },
            {
                "id": 14,
                "user_id": 4,
                "provider": "drive",
                "enabled": True,
                "sync_mode": "manual",
                "needs_full_rescan": False,
                "webhook_status": None,
                "webhook_subscription_id": None,
                "webhook_expires_at": None,
            },
            {
                "id": 15,
                "user_id": 5,
                "provider": "zotero",
                "enabled": True,
                "sync_mode": "poll",
                "needs_full_rescan": False,
                "webhook_status": None,
                "webhook_subscription_id": None,
                "webhook_expires_at": None,
            },
        ]

    queued_jobs: list[dict[str, object]] = []
    prune_calls: list[str] = []

    async def _fake_create_import_job(user_id, source_id, *, request_id=None, job_type="import"):
        queued_jobs.append(
            {
                "user_id": user_id,
                "source_id": source_id,
                "job_type": job_type,
            }
        )
        return {
            "id": f"job-{source_id}",
            "source_id": source_id,
            "type": job_type,
            "status": "queued",
            "progress_pct": 0,
            "counts": {"processed": 0, "skipped": 0, "failed": 0},
        }

    async def _fake_prune_webhook_receipts(db, *, older_than):
        prune_calls.append(str(older_than))
        return 2

    monkeypatch.setattr(scheduler_mod, "get_db_pool", _fake_get_db_pool, raising=False)
    monkeypatch.setattr(
        scheduler_mod,
        "list_sources_for_scheduler",
        _fake_list_sources_for_scheduler,
        raising=False,
    )
    monkeypatch.setattr(
        scheduler_mod,
        "create_import_job",
        _fake_create_import_job,
        raising=False,
    )
    monkeypatch.setattr(
        scheduler_mod,
        "prune_webhook_receipts",
        _fake_prune_webhook_receipts,
        raising=False,
    )

    scheduler = scheduler_mod._ConnectorsSyncScheduler()
    await scheduler._scan_once()

    assert len(prune_calls) == 1
    assert queued_jobs == [
        {"user_id": 1, "source_id": 11, "job_type": "subscription_renewal"},
        {"user_id": 2, "source_id": 12, "job_type": "repair_rescan"},
        {"user_id": 3, "source_id": 13, "job_type": "incremental_sync"},
        {"user_id": 5, "source_id": 15, "job_type": "incremental_sync"},
    ]
