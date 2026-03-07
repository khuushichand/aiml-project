from __future__ import annotations

import pytest

from tldw_Server_API.app.core.External_Sources.sync_adapter import FileSyncChange
from tldw_Server_API.app.core.External_Sources.sync_coordinator import SyncReconcileResult


@pytest.mark.asyncio
@pytest.mark.unit
async def test_worker_drive_incremental_sync_uses_delta_feed_and_advances_cursor(monkeypatch):
    import tldw_Server_API.app.services.connectors_worker as worker

    class FakeJM:
        def __init__(self):
            self.completed = None

        def renew_job_lease(self, *args, **kwargs):
            return None

        def complete_job(
            self,
            jid,
            result=None,
            worker_id=None,
            lease_id=None,
            completion_token=None,
        ):
            self.completed = {"jid": jid, "result": result}

    class FakeDriveConn:
        list_changes_calls: list[str | None] = []
        download_calls: list[dict[str, object]] = []

        async def list_files(self, *args, **kwargs):
            raise AssertionError("delta sync should not fall back to recursive traversal")

        async def list_changes(
            self,
            account,
            *,
            cursor: str | None = None,
            page_size: int = 100,
        ):
            type(self).list_changes_calls.append(cursor)
            assert account["tokens"]["access_token"] == "tok"
            assert page_size == 100
            return (
                [
                    FileSyncChange(
                        event_type="content_updated",
                        remote_id="file-1",
                        remote_name="quarterly.txt",
                        remote_parent_id="folder-1",
                        remote_path="/finance/quarterly.txt",
                        remote_revision="rev-2",
                        remote_hash="hash-2",
                        metadata={
                            "mime_type": "text/plain",
                            "size": 128,
                            "modified_at": "2026-03-06T12:00:00Z",
                        },
                    )
                ],
                None,
                "cursor-2",
            )

        async def download_or_export(self, account, remote_id, *, metadata=None):
            type(self).download_calls.append(
                {
                    "account": dict(account),
                    "remote_id": remote_id,
                    "metadata": dict(metadata or {}),
                }
            )
            return b"Updated drive sync body"

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

    async def _fake_get_source_by_id(db, user_id, source_id):
        assert user_id == 42
        assert source_id == 99
        return {
            "id": source_id,
            "provider": "drive",
            "account_id": 123,
            "remote_id": "root",
            "type": "folder",
            "path": "/",
            "options": {"recursive": True},
            "email": "sync@example.com",
        }

    async def _fake_get_account_tokens(db, user_id, account_id):
        assert user_id == 42
        assert account_id == 123
        return {"access_token": "tok"}

    async def _fake_get_source_sync_state(db, *, source_id):
        assert source_id == 99
        return {"source_id": source_id, "cursor": "cursor-1", "cursor_kind": "drive_start_page_token"}

    sync_state_updates: list[dict[str, object]] = []

    async def _fake_upsert_source_sync_state(db, *, source_id, **updates):
        payload = {"source_id": source_id, **updates}
        sync_state_updates.append(payload)
        return payload

    async def _fake_get_external_item_binding(db, *, source_id, provider, external_id):
        assert source_id == 99
        assert provider == "drive"
        assert external_id == "file-1"
        return {
            "id": 1,
            "source_id": source_id,
            "provider": provider,
            "external_id": external_id,
            "media_id": 77,
            "version": "rev-1",
            "hash": "hash-1",
            "sync_status": "active",
        }

    reconcile_calls: list[dict[str, object]] = []

    async def _fake_reconcile_file_change(
        connectors_db,
        media_db,
        *,
        source_id,
        provider,
        change,
        content=None,
        job_id=None,
    ):
        reconcile_calls.append(
            {
                "source_id": source_id,
                "provider": provider,
                "change": change,
                "content": content,
                "job_id": job_id,
                "media_db_type": type(media_db).__name__,
            }
        )
        return SyncReconcileResult(
            action="version_created",
            media_id=77,
            binding_id=1,
            current_version_number=2,
            sync_status="active",
        )

    class _FakeMDB:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    import tldw_Server_API.app.core.DB_Management.Media_DB_v2 as mdb_mod
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    import tldw_Server_API.app.core.External_Sources.connectors_service as svc
    import tldw_Server_API.app.core.External_Sources.sync_coordinator as sync_coordinator

    monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: FakeDriveConn())
    monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)
    monkeypatch.setattr(svc, "get_source_by_id", _fake_get_source_by_id)
    monkeypatch.setattr(svc, "get_account_tokens", _fake_get_account_tokens)
    monkeypatch.setattr(svc, "get_source_sync_state", _fake_get_source_sync_state)
    monkeypatch.setattr(svc, "upsert_source_sync_state", _fake_upsert_source_sync_state)
    monkeypatch.setattr(svc, "get_external_item_binding", _fake_get_external_item_binding)
    monkeypatch.setattr(sync_coordinator, "reconcile_file_change", _fake_reconcile_file_change)
    monkeypatch.setattr(mdb_mod, "MediaDatabase", _FakeMDB)
    monkeypatch.setattr(orgs, "list_memberships_for_user", lambda user_id: [])

    jm = FakeJM()

    await worker._process_import_job(
        jm,
        jid=1234,
        lease_id="lease-1",
        worker_id="worker-1",
        source_id=99,
        user_id=42,
    )

    assert jm.completed is not None
    assert jm.completed["result"]["processed"] == 1
    assert jm.completed["result"]["total"] == 1
    assert FakeDriveConn.list_changes_calls == ["cursor-1"]
    assert len(FakeDriveConn.download_calls) == 1
    assert FakeDriveConn.download_calls[0]["remote_id"] == "file-1"
    assert FakeDriveConn.download_calls[0]["metadata"] == {
        "mime_type": "text/plain",
        "size": 128,
        "modified_at": "2026-03-06T12:00:00Z",
    }
    assert len(reconcile_calls) == 1
    assert reconcile_calls[0]["source_id"] == 99
    assert reconcile_calls[0]["provider"] == "drive"
    assert reconcile_calls[0]["change"].remote_id == "file-1"
    assert reconcile_calls[0]["content"].text == "Updated drive sync body"
    assert reconcile_calls[0]["job_id"] == "1234"
    assert sync_state_updates[-1]["cursor"] == "cursor-2"
    assert sync_state_updates[-1]["cursor_kind"] == "drive_start_page_token"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_worker_drive_created_delta_without_binding_still_reconciles(monkeypatch):
    import tldw_Server_API.app.services.connectors_worker as worker

    class FakeJM:
        def __init__(self):
            self.completed = None

        def renew_job_lease(self, *args, **kwargs):
            return None

        def complete_job(
            self,
            jid,
            result=None,
            worker_id=None,
            lease_id=None,
            completion_token=None,
        ):
            self.completed = {"jid": jid, "result": result}

    class FakeDriveConn:
        async def list_files(self, *args, **kwargs):
            raise AssertionError("delta sync should not fall back to recursive traversal")

        async def list_changes(
            self,
            account,
            *,
            cursor: str | None = None,
            page_size: int = 100,
        ):
            assert account["tokens"]["access_token"] == "tok"
            return (
                [
                    FileSyncChange(
                        event_type="created",
                        remote_id="file-new",
                        remote_name="new-file.txt",
                        remote_parent_id="folder-1",
                        remote_path="/finance/new-file.txt",
                        remote_revision="rev-1",
                        remote_hash="hash-new",
                        metadata={
                            "mime_type": "text/plain",
                            "size": 64,
                            "modified_at": "2026-03-06T12:00:00Z",
                        },
                    )
                ],
                None,
                "cursor-2",
            )

        async def download_or_export(self, account, remote_id, *, metadata=None):
            assert remote_id == "file-new"
            return b"Brand new drive sync body"

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

    async def _fake_get_source_by_id(db, user_id, source_id):
        return {
            "id": source_id,
            "provider": "drive",
            "account_id": 123,
            "remote_id": "root",
            "type": "folder",
            "path": "/",
            "options": {"recursive": True},
            "email": "sync@example.com",
        }

    async def _fake_get_account_tokens(db, user_id, account_id):
        return {"access_token": "tok"}

    async def _fake_get_source_sync_state(db, *, source_id):
        return {"source_id": source_id, "cursor": "cursor-1", "cursor_kind": "drive_start_page_token"}

    async def _fake_upsert_source_sync_state(db, *, source_id, **updates):
        return {"source_id": source_id, **updates}

    async def _fake_get_external_item_binding(db, *, source_id, provider, external_id):
        assert external_id == "file-new"
        return None

    reconcile_calls: list[dict[str, object]] = []

    async def _fake_reconcile_file_change(
        connectors_db,
        media_db,
        *,
        source_id,
        provider,
        change,
        content=None,
        job_id=None,
    ):
        reconcile_calls.append(
            {
                "source_id": source_id,
                "provider": provider,
                "change": change,
                "content": content,
                "job_id": job_id,
            }
        )
        return SyncReconcileResult(
            action="created",
            media_id=88,
            binding_id=5,
            current_version_number=1,
            sync_status="active",
        )

    class _FakeMDB:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    import tldw_Server_API.app.core.DB_Management.Media_DB_v2 as mdb_mod
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    import tldw_Server_API.app.core.External_Sources.connectors_service as svc
    import tldw_Server_API.app.core.External_Sources.sync_coordinator as sync_coordinator

    monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: FakeDriveConn())
    monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)
    monkeypatch.setattr(svc, "get_source_by_id", _fake_get_source_by_id)
    monkeypatch.setattr(svc, "get_account_tokens", _fake_get_account_tokens)
    monkeypatch.setattr(svc, "get_source_sync_state", _fake_get_source_sync_state)
    monkeypatch.setattr(svc, "upsert_source_sync_state", _fake_upsert_source_sync_state)
    monkeypatch.setattr(svc, "get_external_item_binding", _fake_get_external_item_binding)
    monkeypatch.setattr(sync_coordinator, "reconcile_file_change", _fake_reconcile_file_change)
    monkeypatch.setattr(mdb_mod, "MediaDatabase", _FakeMDB)
    monkeypatch.setattr(orgs, "list_memberships_for_user", lambda user_id: [])

    jm = FakeJM()

    await worker._process_import_job(
        jm,
        jid=5678,
        lease_id="lease-1",
        worker_id="worker-1",
        source_id=99,
        user_id=42,
    )

    assert jm.completed is not None
    assert jm.completed["result"]["processed"] == 1
    assert len(reconcile_calls) == 1
    assert reconcile_calls[0]["change"].event_type == "created"
    assert reconcile_calls[0]["content"].text == "Brand new drive sync body"
    assert reconcile_calls[0]["job_id"] == "5678"
