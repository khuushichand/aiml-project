from __future__ import annotations

import hashlib
import json
from pathlib import Path

import aiosqlite
import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase, get_document_version
from tldw_Server_API.app.core.External_Sources import connectors_service as svc
from tldw_Server_API.app.core.External_Sources.sync_adapter import FileSyncChange
from tldw_Server_API.app.core.External_Sources.sync_coordinator import (
    FileSyncContentPayload,
    reconcile_file_change,
)


@pytest.fixture
async def connectors_db(tmp_path: Path):
    db = await aiosqlite.connect(tmp_path / "connectors.sqlite3")
    db.row_factory = aiosqlite.Row
    db._is_sqlite = True
    try:
        yield db
    finally:
        await db.close()


@pytest.fixture
def media_db(tmp_path: Path) -> MediaDatabase:
    return MediaDatabase(db_path=str(tmp_path / "media.sqlite3"), client_id="sync-test")


async def _create_account_and_source(db: aiosqlite.Connection) -> tuple[dict, dict]:
    return await _create_account_and_source_for_provider(db, provider="drive")


async def _create_account_and_source_for_provider(
    db: aiosqlite.Connection,
    *,
    provider: str,
) -> tuple[dict, dict]:
    account = await svc.create_account(
        db,
        user_id=11,
        provider=provider,
        display_name=provider.title(),
        email="sync@example.com",
        tokens={"access_token": "token"},
    )
    source = await svc.create_source(
        db,
        account_id=account["id"],
        provider=provider,
        remote_id="root",
        type_="folder",
        path="/",
        options={"recursive": True},
    )
    return account, source


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reconcile_created_change_creates_media_binding_and_initial_version(
    connectors_db: aiosqlite.Connection,
    media_db: MediaDatabase,
) -> None:
    _, source = await _create_account_and_source(connectors_db)

    result = await reconcile_file_change(
        connectors_db,
        media_db,
        source_id=source["id"],
        provider="drive",
        change=FileSyncChange(
            event_type="created",
            remote_id="file-created",
            remote_name="created.txt",
            remote_parent_id="folder-1",
            remote_path="/finance/created.txt",
            remote_revision="rev-1",
            remote_hash="remote-hash-created",
            metadata={
                "mime_type": "text/plain",
                "size": 64,
                "modified_at": "2026-03-06T12:00:00Z",
                "remote_url": "https://drive.google.com/file/d/file-created/view",
            },
        ),
        content=FileSyncContentPayload(
            text="Brand new synced body",
            prompt="Initial sync import",
            analysis_content="Imported from external delta",
            safe_metadata={"export_mime": "text/plain"},
        ),
        job_id="job-sync-created",
    )

    media_id = int(result.media_id or 0)
    media_row = media_db.get_media_by_id(media_id)
    latest_version = get_document_version(media_db, media_id)
    binding = await svc.get_external_item_binding(
        connectors_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-created",
    )
    event_rows = await (await connectors_db.execute(
        "SELECT event_type, payload_json FROM external_item_events ORDER BY id ASC"
    )).fetchall()

    assert result.action == "created"
    assert media_id > 0
    assert media_row is not None
    assert media_row["title"] == "created.txt"
    assert media_row["content"] == "Brand new synced body"
    assert media_row["version"] == 1
    assert latest_version is not None
    assert latest_version["version_number"] == 1
    assert latest_version["content"] == "Brand new synced body"
    assert json.loads(latest_version["safe_metadata"]) == {
        "export_mime": "text/plain",
        "provider": "drive",
        "remote_hash": "remote-hash-created",
        "remote_id": "file-created",
        "remote_path": "/finance/created.txt",
        "remote_revision": "rev-1",
        "source_id": source["id"],
        "sync_job_id": "job-sync-created",
        "sync_kind": "created",
    }
    assert binding is not None
    assert binding["media_id"] == media_id
    assert binding["name"] == "created.txt"
    assert binding["version"] == "rev-1"
    assert binding["hash"] == "remote-hash-created"
    assert binding["sync_status"] == "active"
    assert binding["current_version_number"] == 1
    assert len(event_rows) == 1
    assert event_rows[0]["event_type"] == "created"
    assert json.loads(event_rows[0]["payload_json"])["remote_revision"] == "rev-1"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reconcile_content_update_updates_media_fts_versions_and_binding(
    connectors_db: aiosqlite.Connection,
    media_db: MediaDatabase,
) -> None:
    _, source = await _create_account_and_source(connectors_db)
    media_id, _, _ = media_db.add_media_with_keywords(
        title="Quarterly Report",
        content="Original sync body",
        media_type="document",
    )
    await svc.upsert_external_item_binding(
        connectors_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-1",
        media_id=media_id,
        name="quarterly.txt",
        sync_status="active",
        current_version_number=1,
        version="rev-1",
        content_hash="remote-hash-1",
    )

    result = await reconcile_file_change(
        connectors_db,
        media_db,
        source_id=source["id"],
        provider="drive",
        change=FileSyncChange(
            event_type="content_updated",
            remote_id="file-1",
            remote_name="quarterly.txt",
            remote_parent_id="folder-1",
            remote_path="/finance/quarterly.txt",
            remote_revision="rev-2",
            remote_hash="remote-hash-2",
            metadata={
                "mime_type": "text/plain",
                "size": 128,
                "modified_at": "2026-03-06T12:00:00Z",
                "remote_url": "https://drive.google.com/file/d/file-1/view",
            },
        ),
        content=FileSyncContentPayload(
            text="Updated sync body",
            prompt="Sync refresh",
            analysis_content="Latest upstream revision",
            safe_metadata={"export_mime": "text/plain"},
        ),
        job_id="job-sync-1",
    )

    media_row = media_db.get_media_by_id(media_id)
    latest_version = get_document_version(media_db, media_id)
    binding = await svc.get_external_item_binding(
        connectors_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-1",
    )
    event_rows = await (await connectors_db.execute(
        "SELECT event_type, payload_json FROM external_item_events ORDER BY id ASC"
    )).fetchall()
    updated_results, updated_total = MediaDatabase.search_media_db(
        media_db,
        search_query='"Updated"',
        search_fields=["content"],
    )
    original_results, original_total = MediaDatabase.search_media_db(
        media_db,
        search_query='"Original"',
        search_fields=["content"],
    )

    assert result.action == "version_created"
    assert result.media_id == media_id
    assert media_row is not None
    assert media_row["content"] == "Updated sync body"
    assert media_row["content_hash"] == hashlib.sha256("Updated sync body".encode()).hexdigest()
    assert media_row["version"] == 2
    assert latest_version is not None
    assert latest_version["version_number"] == 2
    assert latest_version["content"] == "Updated sync body"
    assert latest_version["prompt"] == "Sync refresh"
    assert latest_version["analysis_content"] == "Latest upstream revision"
    assert json.loads(latest_version["safe_metadata"]) == {
        "export_mime": "text/plain",
        "provider": "drive",
        "remote_hash": "remote-hash-2",
        "remote_id": "file-1",
        "remote_path": "/finance/quarterly.txt",
        "remote_revision": "rev-2",
        "source_id": source["id"],
        "sync_job_id": "job-sync-1",
        "sync_kind": "content_updated",
    }
    assert binding is not None
    assert binding["media_id"] == media_id
    assert binding["version"] == "rev-2"
    assert binding["hash"] == "remote-hash-2"
    assert binding["remote_path"] == "/finance/quarterly.txt"
    assert binding["current_version_number"] == 2
    assert binding["sync_status"] == "active"
    assert binding["last_content_sync_at"] is not None
    assert binding["last_metadata_sync_at"] is not None
    assert len(event_rows) == 1
    assert event_rows[0]["event_type"] == "content_updated"
    assert json.loads(event_rows[0]["payload_json"])["remote_revision"] == "rev-2"
    assert updated_total == 1
    assert updated_results[0]["id"] == media_id
    assert original_total == 0
    assert original_results == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reconcile_created_change_uses_provider_modified_timestamp_aliases(
    connectors_db: aiosqlite.Connection,
    media_db: MediaDatabase,
) -> None:
    _, source = await _create_account_and_source_for_provider(connectors_db, provider="onedrive")

    await reconcile_file_change(
        connectors_db,
        media_db,
        source_id=source["id"],
        provider="onedrive",
        change=FileSyncChange(
            event_type="created",
            remote_id="item-22",
            remote_name="alias.txt",
            remote_revision="etag-2",
            metadata={
                "mime_type": "text/plain",
                "size": 33,
                "last_modified": "2026-03-06T12:00:00Z",
            },
        ),
        content=FileSyncContentPayload(text="alias timestamp body"),
        job_id="job-sync-alias",
    )

    binding = await svc.get_external_item_binding(
        connectors_db,
        source_id=source["id"],
        provider="onedrive",
        external_id="item-22",
    )

    assert binding is not None
    assert binding["modified_at"] == "2026-03-06T12:00:00Z"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reconcile_deleted_change_archives_media_and_binding(
    connectors_db: aiosqlite.Connection,
    media_db: MediaDatabase,
) -> None:
    _, source = await _create_account_and_source(connectors_db)
    media_id, _, _ = media_db.add_media_with_keywords(
        title="Archive Me",
        content="Archive body",
        media_type="document",
    )
    await svc.upsert_external_item_binding(
        connectors_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-archive",
        media_id=media_id,
        name="archive.txt",
        sync_status="active",
    )

    result = await reconcile_file_change(
        connectors_db,
        media_db,
        source_id=source["id"],
        provider="drive",
        change=FileSyncChange(
            event_type="deleted",
            remote_id="file-archive",
            remote_name="archive.txt",
        ),
        job_id="job-sync-archive",
    )

    active_row = media_db.get_media_by_id(media_id)
    trashed_row = media_db.get_media_by_id(media_id, include_trash=True)
    binding = await svc.get_external_item_binding(
        connectors_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-archive",
    )
    event_rows = await (await connectors_db.execute(
        "SELECT event_type, payload_json FROM external_item_events ORDER BY id ASC"
    )).fetchall()

    assert result.action == "archived"
    assert result.media_id == media_id
    assert active_row is None
    assert trashed_row is not None
    assert trashed_row["is_trash"] == 1
    assert binding is not None
    assert binding["sync_status"] == "archived_upstream_removed"
    assert binding["remote_deleted_at"] is not None
    assert binding["last_metadata_sync_at"] is not None
    assert len(event_rows) == 1
    assert event_rows[0]["event_type"] == "deleted_upstream"
    assert json.loads(event_rows[0]["payload_json"])["sync_status"] == "archived_upstream_removed"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reconcile_restored_change_restores_media_and_binding(
    connectors_db: aiosqlite.Connection,
    media_db: MediaDatabase,
) -> None:
    _, source = await _create_account_and_source(connectors_db)
    media_id, _, _ = media_db.add_media_with_keywords(
        title="Restore Me",
        content="Restore body",
        media_type="document",
    )
    media_db.mark_as_trash(media_id)
    await svc.upsert_external_item_binding(
        connectors_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-restore",
        media_id=media_id,
        name="restore.txt",
        sync_status="archived_upstream_removed",
        remote_deleted_at="2026-03-05T00:00:00Z",
    )

    result = await reconcile_file_change(
        connectors_db,
        media_db,
        source_id=source["id"],
        provider="drive",
        change=FileSyncChange(
            event_type="restored",
            remote_id="file-restore",
            remote_name="restore-renamed.txt",
            remote_parent_id="folder-restore",
            remote_path="/restored/restore-renamed.txt",
            remote_revision="rev-3",
        ),
        job_id="job-sync-restore",
    )

    media_row = media_db.get_media_by_id(media_id)
    binding = await svc.get_external_item_binding(
        connectors_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-restore",
    )
    event_rows = await (await connectors_db.execute(
        "SELECT event_type, payload_json FROM external_item_events ORDER BY id ASC"
    )).fetchall()

    assert result.action == "restored"
    assert result.media_id == media_id
    assert media_row is not None
    assert media_row["is_trash"] == 0
    assert binding is not None
    assert binding["sync_status"] == "active"
    assert binding["name"] == "restore-renamed.txt"
    assert binding["version"] == "rev-3"
    assert binding["remote_parent_id"] == "folder-restore"
    assert binding["remote_path"] == "/restored/restore-renamed.txt"
    assert binding["remote_deleted_at"] is None
    assert binding["access_revoked_at"] is None
    assert binding["last_metadata_sync_at"] is not None
    assert len(event_rows) == 1
    assert event_rows[0]["event_type"] == "restored_upstream"
    assert json.loads(event_rows[0]["payload_json"])["sync_status"] == "active"
