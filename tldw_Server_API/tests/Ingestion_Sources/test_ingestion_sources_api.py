from __future__ import annotations

import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def ingestion_sources_client():
    os.environ.setdefault("TEST_MODE", "true")
    os.environ.setdefault("ROUTES_STABLE_ONLY", "false")
    os.environ["ROUTES_ENABLE"] = "ingestion-sources"
    os.environ.setdefault("AUTH_MODE", "single_user")
    os.environ.setdefault("TESTING", "true")

    from tldw_Server_API.app.api.v1.endpoints import ingestion_sources as ingestion_sources_router
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    from tldw_Server_API.app.main import app

    paths = {route.path for route in app.routes}
    if "/api/v1/ingestion-sources/{source_id}/sync" not in paths:
        app.include_router(ingestion_sources_router.router, prefix="/api/v1", tags=["ingestion-sources"])

    api_key = get_settings().SINGLE_USER_API_KEY
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    client = TestClient(app)
    return client, headers


@pytest.mark.integration
def test_manual_sync_endpoint_enqueues_job(ingestion_sources_client, monkeypatch):
    client, auth_headers = ingestion_sources_client

    import tldw_Server_API.app.api.v1.endpoints.ingestion_sources as ep

    queued_jobs: list[dict[str, object]] = []

    class _FakeTx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakePool:
        def transaction(self):
            return _FakeTx()

    async def _fake_get_db_pool():
        return _FakePool()

    async def _fake_ensure_schema(_db):
        return None

    async def _fake_get_source_by_id(_db, *, source_id, user_id=None):
        return {
            "id": source_id,
            "user_id": 1 if user_id is None else user_id,
            "enabled": True,
        }

    def _fake_enqueue_ingestion_source_job(*, user_id, source_id, job_type="sync", idempotency_key=None, payload=None):
        queued_jobs.append(
            {
                "user_id": user_id,
                "source_id": source_id,
                "job_type": job_type,
                "idempotency_key": idempotency_key,
            }
        )
        return {"id": "job-17", "status": "queued"}

    monkeypatch.setattr(ep, "get_db_pool", _fake_get_db_pool)
    monkeypatch.setattr(ep, "ensure_ingestion_sources_schema", _fake_ensure_schema)
    monkeypatch.setattr(ep, "get_source_by_id", _fake_get_source_by_id)
    monkeypatch.setattr(ep, "enqueue_ingestion_source_job", _fake_enqueue_ingestion_source_job)

    response = client.post(
        "/api/v1/ingestion-sources/17/sync",
        headers=auth_headers,
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["source_id"] == 17
    assert payload["job_id"] == "job-17"
    assert queued_jobs[0]["source_id"] == 17


@pytest.mark.integration
def test_archive_upload_endpoint_stages_snapshot_and_enqueues_job(tmp_path, ingestion_sources_client, monkeypatch):
    client, auth_headers = ingestion_sources_client

    import aiosqlite
    import tldw_Server_API.app.api.v1.endpoints.ingestion_sources as ep
    from tldw_Server_API.app.core.Ingestion_Sources.service import (
        create_source,
        ensure_ingestion_sources_schema,
    )

    queued_jobs: list[dict[str, object]] = []

    class _FakePool:
        def __init__(self, db):
            self._db = db

        class _Tx:
            def __init__(self, db):
                self._db = db

            async def __aenter__(self):
                return self._db

            async def __aexit__(self, exc_type, exc, tb):
                return False

        def transaction(self):
            return self._Tx(self._db)

    async def _run_test() -> None:
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

            async def _fake_get_db_pool():
                return _FakePool(db)

            def _fake_enqueue_ingestion_source_job(*, user_id, source_id, job_type="sync", idempotency_key=None, payload=None):
                queued_jobs.append(
                    {
                        "user_id": user_id,
                        "source_id": source_id,
                        "job_type": job_type,
                        "idempotency_key": idempotency_key,
                    }
                )
                return {"id": "job-29", "status": "queued"}

            monkeypatch.setattr(ep, "get_db_pool", _fake_get_db_pool)
            monkeypatch.setattr(ep, "enqueue_ingestion_source_job", _fake_enqueue_ingestion_source_job)

            archive_buffer = io.BytesIO()
            with zipfile.ZipFile(archive_buffer, "w") as archive:
                archive.writestr("export/alpha.md", "# Alpha\n\nzip body\n")

            response = client.post(
                f"/api/v1/ingestion-sources/{int(source['id'])}/archive",
                headers={"X-API-KEY": auth_headers["X-API-KEY"]},
                files={"archive": ("notes.zip", archive_buffer.getvalue(), "application/zip")},
            )

            assert response.status_code == 202, response.text
            payload = response.json()
            assert payload["status"] == "queued"
            assert payload["source_id"] == int(source["id"])
            assert payload["job_id"] == "job-29"
            assert payload["snapshot_status"] == "staged"

            snapshot_cur = await db.execute(
                "SELECT status, snapshot_kind, summary_json FROM ingestion_source_snapshots WHERE source_id = ?",
                (int(source["id"]),),
            )
            snapshot_row = await snapshot_cur.fetchone()
            assert snapshot_row["status"] == "staged"
            assert snapshot_row["snapshot_kind"] == "archive_snapshot"
            assert "notes.zip" in snapshot_row["summary_json"]
            assert queued_jobs[0]["source_id"] == int(source["id"])

    import asyncio

    asyncio.run(_run_test())
