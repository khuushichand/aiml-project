from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from tldw_Server_API.app.core.External_Sources import connectors_service as svc


@pytest.fixture
async def sqlite_db(tmp_path: Path):
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


@pytest.mark.asyncio
@pytest.mark.unit
async def test_external_items_upgrade_preserves_legacy_row_and_adds_binding_fields(
    sqlite_db: aiosqlite.Connection,
) -> None:
    await sqlite_db.execute(
        """
        CREATE TABLE external_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at TEXT,
            scopes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await sqlite_db.execute(
        """
        CREATE TABLE external_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            remote_id TEXT NOT NULL,
            type TEXT NOT NULL,
            path TEXT,
            options TEXT,
            enabled INTEGER DEFAULT 1,
            last_synced_at TEXT
        )
        """
    )
    await sqlite_db.execute(
        """
        CREATE TABLE external_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            external_id TEXT NOT NULL,
            name TEXT,
            mime TEXT,
            size INTEGER,
            modified_at TEXT,
            version TEXT,
            hash TEXT,
            last_ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, provider, external_id)
        )
        """
    )
    await sqlite_db.execute(
        """
        INSERT INTO external_accounts (id, user_id, provider, display_name, email, access_token)
        VALUES (1, 7, 'drive', 'Drive', 'user@example.com', 'token')
        """
    )
    await sqlite_db.execute(
        """
        INSERT INTO external_sources (id, account_id, provider, remote_id, type, path, options, enabled)
        VALUES (1, 1, 'drive', 'root', 'folder', '/', '{}', 1)
        """
    )
    await sqlite_db.execute(
        """
        INSERT INTO external_items (source_id, provider, external_id, name, version, hash)
        VALUES (1, 'drive', 'legacy-file', 'legacy.pdf', 'v1', 'h1')
        """
    )
    await sqlite_db.commit()

    state = await svc.upsert_source_sync_state(
        sqlite_db,
        source_id=1,
        sync_mode="hybrid",
    )
    legacy_binding = await svc.get_external_item_binding(
        sqlite_db,
        source_id=1,
        provider="drive",
        external_id="legacy-file",
    )
    binding = await svc.upsert_external_item_binding(
        sqlite_db,
        source_id=1,
        provider="drive",
        external_id="file-1",
        media_id=99,
        sync_status="active",
    )

    pragma = await sqlite_db.execute("PRAGMA table_info(external_items)")
    columns = {row["name"] for row in await pragma.fetchall()}

    assert legacy_binding is not None
    assert legacy_binding["external_id"] == "legacy-file"
    assert legacy_binding["media_id"] is None
    assert state["sync_mode"] == "hybrid"
    assert state["needs_full_rescan"] is True
    assert binding["external_id"] == "file-1"
    assert binding["media_id"] == 99
    assert {"media_id", "sync_status", "remote_path"} <= columns


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_tables_does_not_commit_sqlite_transaction(sqlite_db: aiosqlite.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _unexpected_commit() -> None:
        raise AssertionError("_ensure_tables must not commit an outer sqlite transaction")

    monkeypatch.setattr(sqlite_db, "commit", _unexpected_commit)

    await svc._ensure_tables(sqlite_db)

    state = await svc.get_source_sync_state(sqlite_db, source_id=999)
    assert state is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_sync_storage_helpers_track_bindings_events_and_archive_state(
    sqlite_db: aiosqlite.Connection,
) -> None:
    _, source = await _create_account_and_source(sqlite_db)

    state = await svc.upsert_source_sync_state(
        sqlite_db,
        source_id=source["id"],
        sync_mode="hybrid",
        cursor="delta-token",
        cursor_kind="drive_start_page_token",
        webhook_subscription_id="drive-chan-1",
        webhook_metadata={
            "resourceId": "drive-resource-1",
            "clientState": "drive-state-123",
            "pageToken": "delta-token",
        },
    )
    binding = await svc.upsert_external_item_binding(
        sqlite_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-1",
        media_id=55,
        sync_status="active",
        remote_path="/folder/file-1.pdf",
        version="v2",
        content_hash="hash-2",
    )
    event = await svc.record_item_event(
        sqlite_db,
        external_item_id=binding["id"],
        event_type="content_updated",
        job_id="job-123",
        payload={"remote_revision": "v2"},
    )
    archived = await svc.mark_external_item_archived(
        sqlite_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-1",
        sync_status="archived_upstream_removed",
    )
    webhook_source = await svc.get_source_by_webhook_subscription(
        sqlite_db,
        provider="drive",
        subscription_id="drive-chan-1",
    )
    fetched = await svc.get_external_item_binding(
        sqlite_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-1",
    )
    items = await svc.list_external_items_for_source(sqlite_db, source_id=source["id"])

    assert state["cursor"] == "delta-token"
    assert state["cursor_kind"] == "drive_start_page_token"
    assert state["webhook_metadata"]["resourceId"] == "drive-resource-1"
    assert binding["media_id"] == 55
    assert event["event_type"] == "content_updated"
    assert archived["sync_status"] == "archived_upstream_removed"
    assert archived["remote_deleted_at"] is not None
    assert webhook_source is not None
    assert webhook_source["id"] == source["id"]
    assert webhook_source["webhook_metadata"]["clientState"] == "drive-state-123"
    assert fetched is not None
    assert fetched["sync_status"] == "archived_upstream_removed"
    assert len(items) == 1
    assert items[0]["external_id"] == "file-1"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_source_binding_health_counts_tracked_and_degraded_items(
    sqlite_db: aiosqlite.Connection,
) -> None:
    _, source = await _create_account_and_source(sqlite_db)

    await svc.upsert_external_item_binding(
        sqlite_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-active",
        media_id=11,
        sync_status="active",
    )
    await svc.upsert_external_item_binding(
        sqlite_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-degraded",
        media_id=12,
        sync_status="degraded",
    )
    await svc.upsert_external_item_binding(
        sqlite_db,
        source_id=source["id"],
        provider="drive",
        external_id="file-archived",
        media_id=13,
        sync_status="archived_upstream_removed",
    )

    health = await svc.get_source_binding_health(sqlite_db, source_id=source["id"])

    assert health["tracked_item_count"] == 3
    assert health["degraded_item_count"] == 1
