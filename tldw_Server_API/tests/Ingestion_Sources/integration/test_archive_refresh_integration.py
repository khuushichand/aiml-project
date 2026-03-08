from __future__ import annotations

from contextlib import asynccontextmanager
import io
import json

import aiosqlite
import pytest
import zipfile


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
@pytest.mark.integration
async def test_archive_sync_failure_marks_staged_snapshot_failed_and_preserves_previous_success(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    import hashlib
    import json

    import tldw_Server_API.app.services.ingestion_sources_worker as worker
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        create_source,
        create_source_snapshot,
        ensure_ingestion_sources_schema,
        upsert_source_item,
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

        notes_db = CharactersRAGDB(
            db_path=str(DatabasePaths.get_chacha_db_path(1)),
            client_id="1",
        )
        note_id = notes_db.add_note(title="Alpha", content="previous body")
        note = notes_db.get_note_by_id(note_id=note_id)
        assert note is not None

        await upsert_source_item(
            db,
            source_id=int(source["id"]),
            normalized_relative_path="alpha.md",
            content_hash=hashlib.sha256("previous body".encode("utf-8")).hexdigest(),
            sync_status="sync_managed",
            binding={
                "note_id": note_id,
                "sync_status": "sync_managed",
                "current_version": int(note["version"]),
            },
            present_in_source=True,
        )

        previous_snapshot = await create_source_snapshot(
            db,
            source_id=int(source["id"]),
            snapshot_kind="archive_snapshot",
            status="success",
            summary={"status": "completed", "current_item_count": 1},
        )
        await db.execute(
            "UPDATE ingestion_source_state SET last_successful_snapshot_id = ? WHERE source_id = ?",
            (int(previous_snapshot["id"]), int(source["id"])),
        )

        staged_text = "# Alpha\n\nnew archive body\n"
        staged_snapshot = await create_source_snapshot(
            db,
            source_id=int(source["id"]),
            snapshot_kind="archive_snapshot",
            status="staged",
            summary={
                "filename": "notes-v2.zip",
                "items": {
                    "alpha.md": {
                        "relative_path": "alpha.md",
                        "content_hash": hashlib.sha256(staged_text.encode("utf-8")).hexdigest(),
                        "text": staged_text,
                        "source_format": "markdown",
                        "raw_metadata": {},
                    }
                },
            },
        )

        async def _fake_get_db_pool():
            return _SQLitePool(db)

        def _explode_apply_notes_change(*args, **kwargs):
            raise ValueError("simulated archive apply failure")

        monkeypatch.setattr(worker, "get_db_pool", _fake_get_db_pool, raising=False)
        monkeypatch.setattr(worker, "apply_notes_change", _explode_apply_notes_change)

        jm = _FakeJobManager()
        await worker._process_sync_job(
            jm,
            jid=91,
            lease_id="lease-91",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        assert jm.completed is None
        assert jm.failed is not None
        assert "simulated archive apply failure" in str(jm.failed["error"])

        state_cur = await db.execute(
            "SELECT last_successful_snapshot_id, last_sync_status, active_job_id "
            "FROM ingestion_source_state WHERE source_id = ?",
            (int(source["id"]),),
        )
        state_row = await state_cur.fetchone()
        assert state_row["last_successful_snapshot_id"] == int(previous_snapshot["id"])
        assert state_row["last_sync_status"] == "failure"
        assert state_row["active_job_id"] is None

        snapshot_cur = await db.execute(
            "SELECT status, summary_json FROM ingestion_source_snapshots WHERE id = ?",
            (int(staged_snapshot["id"]),),
        )
        snapshot_row = await snapshot_cur.fetchone()
        assert snapshot_row["status"] == "failed"
        assert "simulated archive apply failure" in json.loads(snapshot_row["summary_json"])["error"]

        item_cur = await db.execute(
            "SELECT sync_status, binding_json FROM ingestion_source_items "
            "WHERE source_id = ? AND normalized_relative_path = ?",
            (int(source["id"]), "alpha.md"),
        )
        item_row = await item_cur.fetchone()
        assert item_row["sync_status"] == "sync_managed"
        assert json.loads(item_row["binding_json"])["note_id"] == note_id

        updated_note = notes_db.get_note_by_id(note_id=note_id)
        assert updated_note is not None
        assert updated_note["content"] == "previous body"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_archive_sync_rebuilds_items_from_persisted_artifact_when_snapshot_summary_has_no_items(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    import tldw_Server_API.app.services.ingestion_sources_worker as worker
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.Ingestion_Sources.archive_snapshot import persist_archive_artifact
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        create_source,
        create_source_snapshot,
        ensure_ingestion_sources_schema,
        get_source_snapshot_by_id,
    )

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("export/alpha.md", "# Alpha\n\nfrom artifact\n")
    archive_bytes = archive_buffer.getvalue()

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
        staged_snapshot = await create_source_snapshot(
            db,
            source_id=int(source["id"]),
            snapshot_kind="archive_snapshot",
            status="staged",
            summary={"filename": "notes-v1.zip"},
        )
        artifact = await persist_archive_artifact(
            db,
            user_id=1,
            source_id=int(source["id"]),
            snapshot_id=int(staged_snapshot["id"]),
            filename="notes-v1.zip",
            archive_bytes=archive_bytes,
        )
        await db.execute(
            "UPDATE ingestion_source_snapshots SET summary_json = ? WHERE id = ?",
            (
                json.dumps(
                    {
                        "filename": "notes-v1.zip",
                        "artifact_id": int(artifact["id"]),
                        "item_count": 1,
                    }
                ),
                int(staged_snapshot["id"]),
            ),
        )

        async def _fake_get_db_pool():
            return _SQLitePool(db)

        monkeypatch.setattr(worker, "get_db_pool", _fake_get_db_pool, raising=False)

        jm = _FakeJobManager()
        await worker._process_sync_job(
            jm,
            jid=92,
            lease_id="lease-92",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        assert jm.failed is None
        assert jm.completed is not None
        assert jm.completed["result"]["processed"] == 1

        notes_db = CharactersRAGDB(
            db_path=str(DatabasePaths.get_chacha_db_path(1)),
            client_id="1",
        )
        notes = notes_db.list_notes(limit=10, offset=0)
        assert len(notes) == 1
        assert notes[0]["title"] == "Alpha"
        assert str(notes[0]["content"]).rstrip("\n") == "# Alpha\n\nfrom artifact"

        updated_snapshot = await get_source_snapshot_by_id(db, snapshot_id=int(staged_snapshot["id"]))
        assert updated_snapshot is not None
        assert updated_snapshot["status"] == "success"

        artifact_cur = await db.execute(
            "SELECT status FROM ingestion_source_artifacts WHERE id = ?",
            (int(artifact["id"]),),
        )
        artifact_row = await artifact_cur.fetchone()
        assert artifact_row is not None
        assert artifact_row["status"] == "active"
