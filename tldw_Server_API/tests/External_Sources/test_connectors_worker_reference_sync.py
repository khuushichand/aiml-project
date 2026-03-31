from __future__ import annotations

from contextlib import asynccontextmanager

import pytest


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


class _DummyPool:
    @asynccontextmanager
    async def transaction(self):
        yield object()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_worker_reference_manager_sync_uses_merged_account_loader_and_persists_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    import tldw_Server_API.app.core.External_Sources.connectors_service as svc
    import tldw_Server_API.app.services.connectors_worker as worker

    class _FakeZoteroConnector:
        pass

    pool = _DummyPool()
    sync_state_updates: list[dict[str, object]] = []
    sync_calls: list[dict[str, object]] = []

    async def _fake_get_db_pool():
        return pool

    async def _fake_get_source_by_id(db, user_id, source_id):
        assert user_id == 42
        assert source_id == 99
        return {
            "id": source_id,
            "provider": "zotero",
            "account_id": 123,
            "remote_id": "COLL1234",
            "type": "collection",
            "path": None,
            "options": {"recursive": False},
            "email": "researcher@example.com",
        }

    async def _fake_get_account_for_user(db, user_id, account_id):
        assert user_id == 42
        assert account_id == 123
        return {
            "id": account_id,
            "user_id": user_id,
            "provider": "zotero",
            "provider_user_id": "123456",
            "username": "researcher",
            "email": "researcher@example.com",
        }

    async def _fake_get_account_tokens(db, user_id, account_id):
        assert user_id == 42
        assert account_id == 123
        return {"access_token": "tok"}

    async def _fake_get_source_sync_state(db, *, source_id):
        assert source_id == 99
        return {"source_id": source_id, "sync_mode": "poll", "cursor": "cursor-0"}

    async def _fake_upsert_source_sync_state(db, *, source_id, **updates):
        payload = {"source_id": source_id, **updates}
        sync_state_updates.append(payload)
        return payload

    async def _fake_sync_reference_manager_source(
        *,
        connectors_pool,
        connector,
        account,
        source,
        sync_state,
        media_db,
        job_id,
        convert_bytes_to_text,
    ):
        sync_calls.append(
            {
                "connectors_pool": connectors_pool,
                "connector": connector,
                "account": dict(account),
                "source": dict(source),
                "sync_state": dict(sync_state or {}),
                "job_id": job_id,
                "media_db": media_db,
                "convert_bytes_to_text": convert_bytes_to_text,
            }
        )
        assert account["tokens"]["access_token"] == "tok"
        assert account["provider_user_id"] == "123456"
        assert account["username"] == "researcher"
        assert source["remote_id"] == "COLL1234"
        assert sync_state["cursor"] == "cursor-0"
        return {
            "processed": 2,
            "total": 2,
            "failed": 0,
            "imported": 1,
            "duplicates": 1,
            "metadata_only": 0,
            "cursor": "cursor-1",
        }

    class _FakeMDB:
        def __init__(self):
            self.closed = False

        def close_connection(self):
            self.closed = True

    created_media_db = _FakeMDB()

    monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)
    monkeypatch.setattr(orgs, "list_memberships_for_user", lambda user_id: [])
    monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: _FakeZoteroConnector())
    monkeypatch.setattr(svc, "get_source_by_id", _fake_get_source_by_id)
    monkeypatch.setattr(svc, "get_account_for_user", _fake_get_account_for_user, raising=False)
    monkeypatch.setattr(svc, "get_account_tokens", _fake_get_account_tokens)
    monkeypatch.setattr(svc, "get_source_sync_state", _fake_get_source_sync_state)
    monkeypatch.setattr(svc, "upsert_source_sync_state", _fake_upsert_source_sync_state)
    monkeypatch.setattr(
        worker,
        "_create_connector_media_db",
        lambda user_id: created_media_db,
        raising=False,
    )
    monkeypatch.setattr(
        worker,
        "_close_connector_media_db",
        lambda media_db: media_db.close_connection(),
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.External_Sources.reference_manager_import.sync_reference_manager_source",
        _fake_sync_reference_manager_source,
        raising=False,
    )

    jm = _FakeJM()
    await worker._process_import_job(
        jm,
        jid=1234,
        lease_id="lease-1",
        worker_id="worker-1",
        source_id=99,
        user_id=42,
    )

    assert len(sync_calls) == 1
    assert sync_state_updates[0]["last_sync_started_at"] is not None
    assert sync_state_updates[-1]["cursor"] == "cursor-1"
    assert sync_state_updates[-1]["last_sync_succeeded_at"] is not None
    assert jm.completed is not None
    assert jm.completed["result"]["processed"] == 2
    assert jm.completed["result"]["imported"] == 1
    assert jm.completed["result"]["duplicates"] == 1
    assert created_media_db.closed is True
