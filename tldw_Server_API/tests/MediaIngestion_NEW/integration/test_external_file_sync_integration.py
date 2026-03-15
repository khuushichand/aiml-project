from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    MediaDatabase,
    get_document_version,
)
from tldw_Server_API.app.core.External_Sources import connectors_service as svc
from tldw_Server_API.app.core.External_Sources.sync_adapter import FileSyncChange


pytestmark = pytest.mark.integration


class _FakeJM:
    def __init__(self) -> None:
        self.completed: dict[str, object] | None = None

    def renew_job_lease(self, *args, **kwargs):
        return None

    def complete_job(
        self,
        jid,
        result=None,
        worker_id=None,
        lease_id=None,
        completion_token=None,
    ) -> None:
        self.completed = {"jid": jid, "result": result}


class _SqlitePool:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    @asynccontextmanager
    async def transaction(self):
        yield self._db


class _FakeDriveConnector:
    def __init__(self) -> None:
        self.list_files_calls: list[str] = []
        self.list_changes_calls: list[str | None] = []
        self.download_file_calls: list[str] = []
        self.download_or_export_calls: list[str] = []

    async def list_files(
        self,
        account,
        parent_remote_id: str,
        *,
        page_size: int = 50,
        cursor: str | None = None,
    ):
        self.list_files_calls.append(parent_remote_id)
        assert account["tokens"]["access_token"] == "tok"
        assert parent_remote_id == "root"
        assert cursor is None
        return (
            [
                {
                    "id": "file-1",
                    "name": "quarterly.txt",
                    "mimeType": "text/plain",
                    "size": 128,
                    "modifiedTime": "2026-03-07T01:00:00Z",
                    "md5Checksum": "hash-bootstrap",
                    "is_folder": False,
                }
            ],
            None,
        )

    async def download_file(self, account, remote_id, *, mime_type=None, export_mime=None):
        self.download_file_calls.append(remote_id)
        assert account["tokens"]["access_token"] == "tok"
        assert remote_id == "file-1"
        return b"Initial drive body"

    async def get_start_page_token(self, account):
        assert account["tokens"]["access_token"] == "tok"
        return "cursor-1"

    async def list_changes(
        self,
        account,
        *,
        cursor: str | None = None,
        page_size: int = 100,
    ):
        self.list_changes_calls.append(cursor)
        assert account["tokens"]["access_token"] == "tok"
        assert cursor == "cursor-1"
        return (
            [
                FileSyncChange(
                    event_type="content_updated",
                    remote_id="file-1",
                    remote_name="quarterly.txt",
                    remote_parent_id="root",
                    remote_path="/quarterly.txt",
                    remote_revision="rev-2",
                    remote_hash="hash-rev-2",
                    metadata={
                        "mime_type": "text/plain",
                        "size": 128,
                        "modified_at": "2026-03-07T02:00:00Z",
                    },
                )
            ],
            None,
            "cursor-2",
        )

    async def download_or_export(self, account, remote_id, *, metadata=None):
        self.download_or_export_calls.append(remote_id)
        assert account["tokens"]["access_token"] == "tok"
        assert remote_id == "file-1"
        return b"Updated drive body"


class _FakeDriveDeleteConnector(_FakeDriveConnector):
    async def list_changes(
        self,
        account,
        *,
        cursor: str | None = None,
        page_size: int = 100,
    ):
        self.list_changes_calls.append(cursor)
        assert account["tokens"]["access_token"] == "tok"
        assert cursor == "cursor-1"
        return (
            [
                FileSyncChange(
                    event_type="deleted",
                    remote_id="file-1",
                    remote_name="quarterly.txt",
                    metadata={},
                )
            ],
            None,
            "cursor-2",
        )


class _FakeDriveFailingUpdateConnector(_FakeDriveConnector):
    async def download_or_export(self, account, remote_id, *, metadata=None):
        self.download_or_export_calls.append(remote_id)
        assert account["tokens"]["access_token"] == "tok"
        raise ValueError("unsupported remote revision")


@pytest.mark.asyncio
async def test_drive_bootstrap_import_then_incremental_sync_creates_versioned_media(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    import tldw_Server_API.app.core.DB_Management.db_path_utils as db_paths_mod
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    import tldw_Server_API.app.services.connectors_worker as worker

    connectors_db = await aiosqlite.connect(tmp_path / "connectors.sqlite3")
    connectors_db.row_factory = aiosqlite.Row
    connectors_db._is_sqlite = True

    try:
        media_root = tmp_path / "user_dbs"
        monkeypatch.setenv("USER_DB_BASE_DIR", str(media_root))
        monkeypatch.setitem(db_paths_mod.settings, "USER_DB_BASE_DIR", str(media_root))
        media_db_path = db_paths_mod.DatabasePaths.get_media_db_path(1)

        pool = _SqlitePool(connectors_db)
        fake_conn = _FakeDriveConnector()

        async def _fake_get_db_pool():
            return pool

        async def _fake_list_memberships_for_user(_user_id: int):
            return []

        monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)
        monkeypatch.setattr(orgs, "list_memberships_for_user", _fake_list_memberships_for_user)
        monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: fake_conn)

        account = await svc.create_account(
            connectors_db,
            user_id=1,
            provider="drive",
            display_name="Drive",
            email="sync@example.com",
            tokens={"access_token": "tok", "refresh_token": "refresh"},
        )
        source = await svc.create_source(
            connectors_db,
            account_id=int(account["id"]),
            provider="drive",
            remote_id="root",
            type_="folder",
            path="/",
            options={"recursive": True},
        )

        bootstrap_jm = _FakeJM()
        await worker._process_import_job(
            bootstrap_jm,
            jid=9001,
            lease_id="lease-bootstrap",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        binding_after_bootstrap = await svc.get_external_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="drive",
            external_id="file-1",
        )
        sync_state_after_bootstrap = await svc.get_source_sync_state(
            connectors_db,
            source_id=int(source["id"]),
        )

        assert bootstrap_jm.completed is not None
        assert bootstrap_jm.completed["result"]["processed"] == 1
        assert binding_after_bootstrap is not None
        assert binding_after_bootstrap["media_id"] is not None
        assert binding_after_bootstrap["current_version_number"] == 1
        assert sync_state_after_bootstrap is not None
        assert sync_state_after_bootstrap["cursor"] == "cursor-1"
        assert sync_state_after_bootstrap["last_bootstrap_at"] is not None

        media_id = int(binding_after_bootstrap["media_id"])
        media_db = MediaDatabase(db_path=str(media_db_path), client_id="1")
        version_one = get_document_version(media_db, media_id=media_id, version_number=1)
        version_count = media_db.execute_query(
            "SELECT COUNT(*) AS c FROM DocumentVersions WHERE media_id = ? AND deleted = 0",
            (media_id,),
        ).fetchone()["c"]

        assert version_one is not None
        assert version_one["content"] == "Initial drive body"
        assert version_count == 1

        incremental_jm = _FakeJM()
        await worker._process_import_job(
            incremental_jm,
            jid=9002,
            lease_id="lease-incremental",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
            job_type="incremental_sync",
        )

        binding_after_incremental = await svc.get_external_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="drive",
            external_id="file-1",
        )
        sync_state_after_incremental = await svc.get_source_sync_state(
            connectors_db,
            source_id=int(source["id"]),
        )
        version_two = get_document_version(media_db, media_id=media_id, version_number=2)
        media_row = media_db.execute_query(
            "SELECT content FROM Media WHERE id = ? AND deleted = 0",
            (media_id,),
        ).fetchone()
        version_count_after_incremental = media_db.execute_query(
            "SELECT COUNT(*) AS c FROM DocumentVersions WHERE media_id = ? AND deleted = 0",
            (media_id,),
        ).fetchone()["c"]

        assert incremental_jm.completed is not None
        assert incremental_jm.completed["result"]["processed"] == 1
        assert fake_conn.list_changes_calls == ["cursor-1"]
        assert binding_after_incremental is not None
        assert binding_after_incremental["current_version_number"] == 2
        assert sync_state_after_incremental is not None
        assert sync_state_after_incremental["cursor"] == "cursor-2"
        assert version_two is not None
        assert version_two["content"] == "Updated drive body"
        assert media_row["content"] == "Updated drive body"
        assert version_count_after_incremental == 2
    finally:
        await connectors_db.close()


@pytest.mark.asyncio
async def test_drive_incremental_delete_archives_existing_media(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    import tldw_Server_API.app.core.DB_Management.db_path_utils as db_paths_mod
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    import tldw_Server_API.app.services.connectors_worker as worker

    connectors_db = await aiosqlite.connect(tmp_path / "connectors.sqlite3")
    connectors_db.row_factory = aiosqlite.Row
    connectors_db._is_sqlite = True

    try:
        media_root = tmp_path / "user_dbs"
        monkeypatch.setenv("USER_DB_BASE_DIR", str(media_root))
        monkeypatch.setitem(db_paths_mod.settings, "USER_DB_BASE_DIR", str(media_root))
        media_db_path = db_paths_mod.DatabasePaths.get_media_db_path(1)

        pool = _SqlitePool(connectors_db)
        fake_conn = _FakeDriveDeleteConnector()

        async def _fake_get_db_pool():
            return pool

        async def _fake_list_memberships_for_user(_user_id: int):
            return []

        monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)
        monkeypatch.setattr(orgs, "list_memberships_for_user", _fake_list_memberships_for_user)
        monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: fake_conn)

        account = await svc.create_account(
            connectors_db,
            user_id=1,
            provider="drive",
            display_name="Drive",
            email="sync@example.com",
            tokens={"access_token": "tok", "refresh_token": "refresh"},
        )
        source = await svc.create_source(
            connectors_db,
            account_id=int(account["id"]),
            provider="drive",
            remote_id="root",
            type_="folder",
            path="/",
            options={"recursive": True},
        )

        bootstrap_jm = _FakeJM()
        await worker._process_import_job(
            bootstrap_jm,
            jid=9101,
            lease_id="lease-bootstrap",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        binding_after_bootstrap = await svc.get_external_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="drive",
            external_id="file-1",
        )
        media_id = int(binding_after_bootstrap["media_id"])

        delete_jm = _FakeJM()
        await worker._process_import_job(
            delete_jm,
            jid=9102,
            lease_id="lease-delete",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
            job_type="incremental_sync",
        )

        archived_binding = await svc.get_external_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="drive",
            external_id="file-1",
        )
        media_db = MediaDatabase(db_path=str(media_db_path), client_id="1")
        media_row = media_db.execute_query(
            "SELECT is_trash FROM Media WHERE id = ? AND deleted = 0",
            (media_id,),
        ).fetchone()

        assert delete_jm.completed is not None
        assert delete_jm.completed["result"]["processed"] == 1
        assert archived_binding is not None
        assert archived_binding["sync_status"] == "archived_upstream_removed"
        assert archived_binding["remote_deleted_at"] is not None
        assert media_row["is_trash"] == 1
    finally:
        await connectors_db.close()


@pytest.mark.asyncio
async def test_drive_incremental_ingest_failure_keeps_last_good_version_and_marks_binding_degraded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import json

    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    import tldw_Server_API.app.core.DB_Management.db_path_utils as db_paths_mod
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    import tldw_Server_API.app.services.connectors_worker as worker

    connectors_db = await aiosqlite.connect(tmp_path / "connectors.sqlite3")
    connectors_db.row_factory = aiosqlite.Row
    connectors_db._is_sqlite = True

    try:
        media_root = tmp_path / "user_dbs"
        monkeypatch.setenv("USER_DB_BASE_DIR", str(media_root))
        monkeypatch.setitem(db_paths_mod.settings, "USER_DB_BASE_DIR", str(media_root))
        media_db_path = db_paths_mod.DatabasePaths.get_media_db_path(1)

        pool = _SqlitePool(connectors_db)
        fake_conn = _FakeDriveFailingUpdateConnector()

        async def _fake_get_db_pool():
            return pool

        async def _fake_list_memberships_for_user(_user_id: int):
            return []

        monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)
        monkeypatch.setattr(orgs, "list_memberships_for_user", _fake_list_memberships_for_user)
        monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: fake_conn)

        account = await svc.create_account(
            connectors_db,
            user_id=1,
            provider="drive",
            display_name="Drive",
            email="sync@example.com",
            tokens={"access_token": "tok", "refresh_token": "refresh"},
        )
        source = await svc.create_source(
            connectors_db,
            account_id=int(account["id"]),
            provider="drive",
            remote_id="root",
            type_="folder",
            path="/",
            options={"recursive": True},
        )

        bootstrap_jm = _FakeJM()
        await worker._process_import_job(
            bootstrap_jm,
            jid=9201,
            lease_id="lease-bootstrap",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        binding_after_bootstrap = await svc.get_external_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="drive",
            external_id="file-1",
        )
        media_id = int(binding_after_bootstrap["media_id"])

        failed_jm = _FakeJM()
        await worker._process_import_job(
            failed_jm,
            jid=9202,
            lease_id="lease-failing-update",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
            job_type="incremental_sync",
        )

        degraded_binding = await svc.get_external_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="drive",
            external_id="file-1",
        )
        media_db = MediaDatabase(db_path=str(media_db_path), client_id="1")
        latest_version = get_document_version(media_db, media_id=media_id)
        version_count = media_db.execute_query(
            "SELECT COUNT(*) AS c FROM DocumentVersions WHERE media_id = ? AND deleted = 0",
            (media_id,),
        ).fetchone()["c"]
        event_rows = await (
            await connectors_db.execute(
                "SELECT event_type, payload_json FROM external_item_events ORDER BY id ASC"
            )
        ).fetchall()

        assert failed_jm.completed is not None
        assert failed_jm.completed["result"]["processed"] == 0
        assert failed_jm.completed["result"]["failed"] == 1
        assert failed_jm.completed["result"]["degraded"] == 1
        assert degraded_binding is not None
        assert degraded_binding["sync_status"] == "degraded"
        assert degraded_binding["current_version_number"] == 1
        assert latest_version is not None
        assert latest_version["version_number"] == 1
        assert latest_version["content"] == "Initial drive body"
        assert version_count == 1
        assert [row["event_type"] for row in event_rows] == ["created", "ingest_failed"]
        assert json.loads(event_rows[-1]["payload_json"])["error"] == "unsupported remote revision"
    finally:
        await connectors_db.close()
