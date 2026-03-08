from __future__ import annotations

import json
from contextlib import asynccontextmanager

import aiosqlite
import pytest


class _FakeJobManager:
    def __init__(self) -> None:
        self.completed: dict[str, object] | None = None
        self.failed: dict[str, object] | None = None

    def renew_job_lease(self, *args, **kwargs) -> None:
        return None

    def complete_job(
        self,
        jid: int,
        *,
        result: dict[str, object] | None = None,
        worker_id: str | None = None,
        lease_id: str | None = None,
        completion_token: str | None = None,
    ) -> None:
        self.completed = {
            "jid": jid,
            "result": result or {},
            "worker_id": worker_id,
            "lease_id": lease_id,
            "completion_token": completion_token,
        }

    def fail_job(
        self,
        jid: int,
        *,
        error: str,
        retryable: bool,
        worker_id: str | None = None,
        lease_id: str | None = None,
        completion_token: str | None = None,
        backoff_seconds: int | None = None,
    ) -> None:
        self.failed = {
            "jid": jid,
            "error": error,
            "retryable": retryable,
            "worker_id": worker_id,
            "lease_id": lease_id,
            "completion_token": completion_token,
            "backoff_seconds": backoff_seconds,
        }


class _SQLitePool:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    @asynccontextmanager
    async def transaction(self):
        yield self._db


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_sync_job_local_directory_notes_source_creates_binding_and_snapshot(
    tmp_path,
    monkeypatch,
):
    source_root = tmp_path / "allowed" / "docs"
    source_root.mkdir(parents=True)
    source_file = source_root / "alpha.md"
    source_file.write_text("# Alpha\n\nfirst body\n", encoding="utf-8")

    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("INGESTION_SOURCE_ALLOWED_ROOTS", str(tmp_path / "allowed"))
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    import tldw_Server_API.app.services.ingestion_sources_worker as worker
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        create_source,
        ensure_ingestion_sources_schema,
    )

    meta_db_path = tmp_path / "ingestion_sources.sqlite3"
    async with aiosqlite.connect(str(meta_db_path)) as db:
        db.row_factory = aiosqlite.Row
        await ensure_ingestion_sources_schema(db)
        source = await create_source(
            db,
            user_id=1,
            payload={
                "source_type": "local_directory",
                "sink_type": "notes",
                "policy": "canonical",
                "config": {"path": str(source_root)},
            },
        )

        async def _fake_get_db_pool():
            return _SQLitePool(db)

        monkeypatch.setattr(worker, "get_db_pool", _fake_get_db_pool, raising=False)

        jm = _FakeJobManager()
        await worker._process_sync_job(
            jm,
            jid=41,
            lease_id="lease-1",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        assert jm.failed is None
        assert jm.completed is not None
        assert jm.completed["result"]["status"] == "completed"
        assert jm.completed["result"]["processed"] == 1
        assert jm.completed["result"]["created"] == 1
        assert jm.completed["result"]["changed"] == 0
        assert jm.completed["result"]["deleted"] == 0

        state_cur = await db.execute(
            "SELECT last_successful_snapshot_id, last_sync_status, active_job_id "
            "FROM ingestion_source_state WHERE source_id = ?",
            (int(source["id"]),),
        )
        state_row = await state_cur.fetchone()
        assert state_row["last_sync_status"] == "success"
        assert state_row["active_job_id"] is None
        assert state_row["last_successful_snapshot_id"] is not None

        snapshot_cur = await db.execute(
            "SELECT snapshot_kind, status, summary_json FROM ingestion_source_snapshots WHERE source_id = ?",
            (int(source["id"]),),
        )
        snapshot_row = await snapshot_cur.fetchone()
        assert snapshot_row["snapshot_kind"] == "local_directory"
        assert snapshot_row["status"] == "success"
        snapshot_summary = json.loads(snapshot_row["summary_json"])
        assert snapshot_summary["current_item_count"] == 1
        assert snapshot_summary["created"] == 1

        item_cur = await db.execute(
            "SELECT normalized_relative_path, content_hash, sync_status, binding_json, present_in_source "
            "FROM ingestion_source_items WHERE source_id = ?",
            (int(source["id"]),),
        )
        item_row = await item_cur.fetchone()
        assert item_row["normalized_relative_path"] == "alpha.md"
        assert item_row["content_hash"]
        assert item_row["sync_status"] == "sync_managed"
        assert item_row["present_in_source"] == 1

        binding = json.loads(item_row["binding_json"])
        note_id = binding["note_id"]
        assert binding["sync_status"] == "sync_managed"
        assert int(binding["current_version"]) >= 1

        notes_db = CharactersRAGDB(db_path=str(DatabasePaths.get_chacha_db_path(1)), client_id="1")
        note = notes_db.get_note_by_id(note_id=note_id)
        assert note is not None
        assert note["title"] == "Alpha"
        assert "first body" in note["content"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_sync_job_marks_detached_note_on_version_conflict(tmp_path, monkeypatch):
    source_root = tmp_path / "allowed" / "docs"
    source_root.mkdir(parents=True)
    source_file = source_root / "alpha.md"
    source_file.write_text("# Alpha\n\ninitial sync body\n", encoding="utf-8")

    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("INGESTION_SOURCE_ALLOWED_ROOTS", str(tmp_path / "allowed"))
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    import tldw_Server_API.app.services.ingestion_sources_worker as worker
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        create_source,
        ensure_ingestion_sources_schema,
    )

    meta_db_path = tmp_path / "ingestion_sources.sqlite3"
    async with aiosqlite.connect(str(meta_db_path)) as db:
        db.row_factory = aiosqlite.Row
        await ensure_ingestion_sources_schema(db)
        source = await create_source(
            db,
            user_id=1,
            payload={
                "source_type": "local_directory",
                "sink_type": "notes",
                "policy": "canonical",
                "config": {"path": str(source_root)},
            },
        )

        async def _fake_get_db_pool():
            return _SQLitePool(db)

        monkeypatch.setattr(worker, "get_db_pool", _fake_get_db_pool, raising=False)

        first_job = _FakeJobManager()
        await worker._process_sync_job(
            first_job,
            jid=41,
            lease_id="lease-1",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )
        assert first_job.failed is None

        item_cur = await db.execute(
            "SELECT binding_json FROM ingestion_source_items WHERE source_id = ? AND normalized_relative_path = ?",
            (int(source["id"]), "alpha.md"),
        )
        item_row = await item_cur.fetchone()
        binding = json.loads(item_row["binding_json"])
        note_id = binding["note_id"]
        current_version = int(binding["current_version"])

        notes_db = CharactersRAGDB(db_path=str(DatabasePaths.get_chacha_db_path(1)), client_id="1")
        notes_db.update_note(
            note_id,
            {"title": "Alpha local edit", "content": "manual local edit"},
            expected_version=current_version,
        )

        source_file.write_text("# Alpha\n\nupstream changed body\n", encoding="utf-8")

        second_job = _FakeJobManager()
        await worker._process_sync_job(
            second_job,
            jid=42,
            lease_id="lease-2",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        assert second_job.failed is None
        assert second_job.completed is not None
        assert second_job.completed["result"]["detached_conflicts"] == 1

        updated_item_cur = await db.execute(
            "SELECT sync_status, binding_json, present_in_source FROM ingestion_source_items "
            "WHERE source_id = ? AND normalized_relative_path = ?",
            (int(source["id"]), "alpha.md"),
        )
        updated_item = await updated_item_cur.fetchone()
        updated_binding = json.loads(updated_item["binding_json"])
        assert updated_item["sync_status"] == "conflict_detached"
        assert updated_item["present_in_source"] == 1
        assert updated_binding["sync_status"] == "conflict_detached"
        assert updated_binding["note_id"] == note_id

        note = notes_db.get_note_by_id(note_id=note_id)
        assert note is not None
        assert note["title"] == "Alpha local edit"
        assert note["content"] == "manual local edit"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_sync_job_archive_snapshot_notes_source_consumes_staged_snapshot(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    import hashlib

    import tldw_Server_API.app.services.ingestion_sources_worker as worker
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        create_source,
        ensure_ingestion_sources_schema,
    )

    meta_db_path = tmp_path / "ingestion_sources.sqlite3"
    async with aiosqlite.connect(str(meta_db_path)) as db:
        db.row_factory = aiosqlite.Row
        await ensure_ingestion_sources_schema(db)
        source = await create_source(
            db,
            user_id=1,
            payload={
                "source_type": "archive_snapshot",
                "sink_type": "notes",
                "policy": "canonical",
                "config": {},
            },
        )

        archive_text = "# Alpha\n\narchive body\n"
        await db.execute(
            """
            INSERT INTO ingestion_source_snapshots (
                source_id,
                snapshot_kind,
                status,
                summary_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(source["id"]),
                "archive_snapshot",
                "staged",
                json.dumps(
                    {
                        "filename": "notes.zip",
                        "items": {
                            "alpha.md": {
                                "relative_path": "alpha.md",
                                "content_hash": hashlib.sha256(archive_text.encode("utf-8")).hexdigest(),
                                "text": archive_text,
                                "source_format": "markdown",
                                "raw_metadata": {},
                            }
                        },
                    }
                ),
                "2026-03-08 12:00:00",
            ),
        )

        async def _fake_get_db_pool():
            return _SQLitePool(db)

        monkeypatch.setattr(worker, "get_db_pool", _fake_get_db_pool, raising=False)

        jm = _FakeJobManager()
        await worker._process_sync_job(
            jm,
            jid=77,
            lease_id="lease-77",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        assert jm.failed is None
        assert jm.completed is not None
        assert jm.completed["result"]["created"] == 1

        snapshot_cur = await db.execute(
            "SELECT status FROM ingestion_source_snapshots WHERE source_id = ?",
            (int(source["id"]),),
        )
        snapshot_row = await snapshot_cur.fetchone()
        assert snapshot_row["status"] == "success"

        item_cur = await db.execute(
            "SELECT binding_json, sync_status FROM ingestion_source_items WHERE source_id = ? AND normalized_relative_path = ?",
            (int(source["id"]), "alpha.md"),
        )
        item_row = await item_cur.fetchone()
        binding = json.loads(item_row["binding_json"])
        assert item_row["sync_status"] == "sync_managed"

        notes_db = CharactersRAGDB(db_path=str(DatabasePaths.get_chacha_db_path(1)), client_id="1")
        note = notes_db.get_note_by_id(note_id=binding["note_id"])
        assert note is not None
        assert note["title"] == "Alpha"
        assert note["content"] == archive_text


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_sync_job_continues_after_sink_apply_failure_for_other_items(
    tmp_path,
    monkeypatch,
):
    source_root = tmp_path / "allowed" / "docs"
    source_root.mkdir(parents=True)
    (source_root / "alpha.md").write_text("# Alpha\n\nfirst body\n", encoding="utf-8")
    (source_root / "beta.md").write_text("# Beta\n\nsecond body\n", encoding="utf-8")

    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("INGESTION_SOURCE_ALLOWED_ROOTS", str(tmp_path / "allowed"))
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    import tldw_Server_API.app.services.ingestion_sources_worker as worker
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        create_source,
        ensure_ingestion_sources_schema,
    )

    meta_db_path = tmp_path / "ingestion_sources.sqlite3"
    async with aiosqlite.connect(str(meta_db_path)) as db:
        db.row_factory = aiosqlite.Row
        await ensure_ingestion_sources_schema(db)
        source = await create_source(
            db,
            user_id=1,
            payload={
                "source_type": "local_directory",
                "sink_type": "notes",
                "policy": "canonical",
                "config": {"path": str(source_root)},
            },
        )

        async def _fake_get_db_pool():
            return _SQLitePool(db)

        real_apply_notes_change = worker.apply_notes_change

        def _sometimes_fail_apply_notes_change(notes_db, *, binding, change, policy):
            if change.get("relative_path") == "alpha.md":
                raise ValueError("simulated note apply failure")
            return real_apply_notes_change(notes_db, binding=binding, change=change, policy=policy)

        monkeypatch.setattr(worker, "get_db_pool", _fake_get_db_pool, raising=False)
        monkeypatch.setattr(worker, "apply_notes_change", _sometimes_fail_apply_notes_change)

        jm = _FakeJobManager()
        await worker._process_sync_job(
            jm,
            jid=88,
            lease_id="lease-88",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        assert jm.failed is None
        assert jm.completed is not None
        assert jm.completed["result"]["status"] == "completed"
        assert jm.completed["result"]["created"] == 2
        assert jm.completed["result"]["degraded_items"] == 1
        assert jm.completed["result"]["sink_failed_items"] == 1
        assert jm.completed["result"]["processed"] == 1

        alpha_cur = await db.execute(
            "SELECT content_hash, sync_status, binding_json, present_in_source "
            "FROM ingestion_source_items WHERE source_id = ? AND normalized_relative_path = ?",
            (int(source["id"]), "alpha.md"),
        )
        alpha_row = await alpha_cur.fetchone()
        assert alpha_row["content_hash"] is None
        assert alpha_row["sync_status"] == "degraded_sink_error"
        assert json.loads(alpha_row["binding_json"]) == {}
        assert alpha_row["present_in_source"] == 1

        beta_cur = await db.execute(
            "SELECT sync_status, binding_json, present_in_source "
            "FROM ingestion_source_items WHERE source_id = ? AND normalized_relative_path = ?",
            (int(source["id"]), "beta.md"),
        )
        beta_row = await beta_cur.fetchone()
        beta_binding = json.loads(beta_row["binding_json"])
        assert beta_row["sync_status"] == "sync_managed"
        assert beta_row["present_in_source"] == 1

        notes_db = CharactersRAGDB(db_path=str(DatabasePaths.get_chacha_db_path(1)), client_id="1")
        beta_note = notes_db.get_note_by_id(note_id=beta_binding["note_id"])
        assert beta_note is not None
        assert beta_note["title"] == "Beta"
        assert "second body" in beta_note["content"]
