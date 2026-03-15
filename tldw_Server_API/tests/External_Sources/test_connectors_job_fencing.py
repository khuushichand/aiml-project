from __future__ import annotations

import aiosqlite
import pytest

from tldw_Server_API.app.core.External_Sources import connectors_service as svc


@pytest.fixture
async def sqlite_db(tmp_path):
    db = await aiosqlite.connect(tmp_path / "connectors.sqlite3")
    db.row_factory = aiosqlite.Row
    db._is_sqlite = True
    try:
        yield db
    finally:
        await db.close()


async def _create_account_and_source(db: aiosqlite.Connection) -> tuple[dict, dict]:
    account = await svc.create_account(
        db,
        user_id=7,
        provider="drive",
        display_name="Drive",
        email="user@example.com",
        tokens={"access_token": "token"},
    )
    source = await svc.create_source(
        db,
        account_id=account["id"],
        provider="drive",
        remote_id="root",
        type_="folder",
        path="/",
        options={"recursive": True},
    )
    return account, source


class _DummyTx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyPool:
    def __init__(self, db):
        self._db = db

    def transaction(self):
        return _DummyTx(self._db)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_source_sync_fence_lifecycle_tracks_active_job_and_outcome(
    sqlite_db: aiosqlite.Connection,
) -> None:
    _, source = await _create_account_and_source(sqlite_db)

    reserved = await svc.reserve_source_sync_job(
        sqlite_db,
        source_id=source["id"],
        job_id="job-101",
    )
    started = await svc.start_source_sync_job(
        sqlite_db,
        source_id=source["id"],
        job_id="job-101",
    )
    finished = await svc.finish_source_sync_job(
        sqlite_db,
        source_id=source["id"],
        job_id="job-101",
        outcome="success",
    )

    assert reserved["active_job_id"] == "job-101"
    assert reserved["active_job_started_at"] is None
    assert started["active_job_id"] == "job-101"
    assert started["active_job_started_at"] is not None
    assert started["last_sync_started_at"] is not None
    assert finished["active_job_id"] is None
    assert finished["active_job_started_at"] is None
    assert finished["last_sync_succeeded_at"] is not None
    assert finished.get("last_error") in (None, "")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_import_job_returns_existing_active_job_for_source(
    sqlite_db: aiosqlite.Connection,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.Jobs.manager as jobs_manager

    _, source = await _create_account_and_source(sqlite_db)
    jobs_db = tmp_path / "jobs.sqlite3"
    real_job_manager = jobs_manager.JobManager

    class _PatchedJobManager(real_job_manager):
        def __init__(self):
            super().__init__(jobs_db)

    async def _fake_get_db_pool():
        return _DummyPool(sqlite_db)

    monkeypatch.setattr(jobs_manager, "JobManager", _PatchedJobManager)
    monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)

    first = await svc.create_import_job(user_id=7, source_id=source["id"])
    second = await svc.create_import_job(user_id=7, source_id=source["id"])
    state = await svc.get_source_sync_state(sqlite_db, source_id=source["id"])
    jm = real_job_manager(jobs_db)
    first_job = jm.get_job(int(first["id"]))

    assert first["id"] == second["id"]
    assert state is not None
    assert state["active_job_id"] == first["id"]
    assert state["active_job_started_at"] is None
    assert first_job is not None
    assert first_job["status"] == "queued"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_worker_requeues_job_when_source_fence_is_owned_by_other_job(
    sqlite_db: aiosqlite.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tldw_Server_API.app.services.connectors_worker as worker

    _, source = await _create_account_and_source(sqlite_db)
    await svc.reserve_source_sync_job(
        sqlite_db,
        source_id=source["id"],
        job_id="job-other",
    )

    stop_event = __import__("asyncio").Event()
    processed: list[tuple[int, int]] = []

    class _FakeJobManager:
        def __init__(self):
            self.failures: list[dict] = []
            self._calls = 0

        def acquire_next_job(self, *, domain, queue, lease_seconds, worker_id):
            self._calls += 1
            if self._calls == 1:
                return {
                    "id": 42,
                    "lease_id": "lease-1",
                    "payload": {"source_id": source["id"], "user_id": 7},
                }
            stop_event.set()
            return None

        def fail_job(self, job_id, *, error, retryable, worker_id, lease_id, completion_token=None, backoff_seconds=None):
            self.failures.append(
                {
                    "job_id": job_id,
                    "error": error,
                    "retryable": retryable,
                    "lease_id": lease_id,
                    "backoff_seconds": backoff_seconds,
                }
            )
            return True

    fake_jm = _FakeJobManager()

    async def _fake_process_import_job(_jm, jid, lease_id, worker_id, source_id, user_id):
        processed.append((source_id, user_id))

    async def _fake_get_db_pool():
        return _DummyPool(sqlite_db)

    monkeypatch.setattr(worker, "JobManager", lambda: fake_jm)
    monkeypatch.setattr(worker, "_process_import_job", _fake_process_import_job)
    monkeypatch.setattr("tldw_Server_API.app.core.AuthNZ.database.get_db_pool", _fake_get_db_pool)
    monkeypatch.setenv("CONNECTORS_POLL_INTERVAL_SECONDS", "0")

    await worker.run_connectors_worker(stop_event)

    assert processed == []
    assert len(fake_jm.failures) == 1
    assert fake_jm.failures[0]["job_id"] == 42
    assert fake_jm.failures[0]["retryable"] is True
    assert "active sync job" in fake_jm.failures[0]["error"].lower()
