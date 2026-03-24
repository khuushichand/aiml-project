import asyncio
from contextlib import contextmanager

import pytest

from tldw_Server_API.app.api.v1.endpoints import embeddings_v5_production_enhanced
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
from tldw_Server_API.app.core.Embeddings.services import jobs_worker
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK


@pytest.mark.asyncio
async def test_embeddings_worker_retryable_backoff_from_result(monkeypatch):
    async def fake_generate_embeddings_for_media(**_kwargs):
        return {
            "status": "error",
            "error": "rate limited",
            "retryable": True,
            "backoff_seconds": 12,
        }

    monkeypatch.setattr(jobs_worker, "generate_embeddings_for_media", fake_generate_embeddings_for_media)
    monkeypatch.setattr(jobs_worker, "_resolve_model_provider", lambda *_: ("test-model", "test-provider"))

    job = {
        "job_type": "content_embeddings",
        "payload": {
            "item_id": 123,
            "content": "example content",
        },
    }

    with pytest.raises(jobs_worker.EmbeddingsJobError) as excinfo:
        await jobs_worker._handle_job(job)

    assert excinfo.value.retryable is True
    assert getattr(excinfo.value, "backoff_seconds", None) == 12


def test_load_media_content_uses_managed_media_database(monkeypatch):
    class _Db:
        def __init__(self) -> None:
            self.closed = False

        def get_media_by_id(
            self,
            media_id,
            include_deleted: bool = False,
            include_trash: bool = False,
        ):
            assert media_id == 42
            return {"id": media_id, "content": "hello embeddings", "title": "Doc"}

        def close_connection(self) -> None:
            self.closed = True

    db = _Db()
    managed_calls: list[dict[str, object]] = []

    @contextmanager
    def _fake_managed_media_database(client_id, *, initialize=True, **kwargs):
        managed_calls.append(
            {
                "client_id": client_id,
                "initialize": initialize,
                "kwargs": kwargs,
            }
        )
        try:
            yield db
        finally:
            db.close_connection()

    monkeypatch.setattr(jobs_worker, "get_user_media_db_path", lambda user_id: f"/tmp/{user_id}.db")
    monkeypatch.setattr(jobs_worker, "managed_media_database", _fake_managed_media_database, raising=False)
    monkeypatch.setattr(
        jobs_worker,
        "create_media_database",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("legacy raw factory should not be used")),
        raising=False,
    )

    result = jobs_worker._load_media_content(42, "user-42")

    assert result == {
        "media_item": {"id": 42, "content": "hello embeddings", "title": "Doc"},
        "content": {"id": 42, "content": "hello embeddings", "title": "Doc"},
    }
    assert db.closed is True
    assert managed_calls == [
        {
            "client_id": "embeddings_jobs_worker",
            "initialize": False,
            "kwargs": {"db_path": "/tmp/user-42.db"},
        }
    ]


@pytest.mark.asyncio
async def test_embeddings_worker_smoke_queue_to_retrieval(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)

    job = jm.create_job(
        domain="embeddings",
        queue="default",
        job_type="content_embeddings",
        payload={
            "item_id": 321,
            "content": "hello embeddings",
            "title": "Hello",
        },
        owner_user_id="user1",
    )

    embedding_config = {
        "USER_DB_BASE_DIR": str(tmp_path / "chroma"),
        "embedding_config": {"default_model_id": "test-model"},
        "chroma_client_settings": {"backend": "stub", "use_in_memory_stub": True},
    }
    manager = ChromaDBManager(user_id="user1", user_embedding_config=embedding_config)
    collection_name = "user_user1_media_embeddings"

    async def fake_generate_embeddings_for_media(*, media_id, **_kwargs):
        texts = ["hello embeddings"]
        embeddings = [[0.1, 0.2, 0.3]]
        ids = [f"media_{media_id}_chunk_0"]
        metadatas = [
            {
                "media_id": str(media_id),
                "embedding_model": "test-model",
                "embedding_provider": "test-provider",
            }
        ]
        manager.store_in_chroma(collection_name, texts, embeddings, ids, metadatas)
        return {"status": "success", "embedding_count": 1, "chunks_processed": 1}

    monkeypatch.setattr(jobs_worker, "generate_embeddings_for_media", fake_generate_embeddings_for_media)
    monkeypatch.setattr(jobs_worker, "_resolve_model_provider", lambda *_: ("test-model", "test-provider"))

    cfg = WorkerConfig(
        domain="embeddings",
        queue="default",
        worker_id="worker-test",
        lease_seconds=10,
        renew_threshold_seconds=1,
        renew_jitter_seconds=0,
    )
    sdk = WorkerSDK(jm, cfg)

    async def handler(job_row):
        result = await jobs_worker._handle_job(job_row)
        sdk.stop()
        return result

    await asyncio.wait_for(sdk.run(handler=handler), timeout=1)

    stored = jm.get_job(int(job["id"]))
    assert stored["status"] == "completed"
    assert stored["result"]["embedding_count"] == 1

    collection = manager.get_or_create_collection(collection_name)
    data = collection.get(where={"media_id": "321"}, include=["embeddings"])
    assert data.get("ids")
    assert len(data.get("embeddings") or []) == 1


@pytest.mark.asyncio
async def test_embeddings_worker_custom_content_stores_in_chroma(monkeypatch, tmp_path):
    async def fake_create_embeddings_batch_async(*, texts, provider, model_id, metadata):
        assert texts == ["hello kanban"]
        assert provider == "test-provider"
        assert model_id == "test-model"
        assert metadata.get("user_id") == "1"
        return [[0.1, 0.2, 0.3]]

    stored: dict[str, object] = {}
    created: dict[str, object] = {}

    class FakeChromaDBManager:
        def __init__(self, *, user_id, user_embedding_config):
            created["user_id"] = user_id
            created["user_embedding_config"] = user_embedding_config

        def store_in_chroma(
            self,
            collection_name,
            texts,
            embeddings,
            ids,
            metadatas,
            embedding_model_id_for_dim_check=None,
        ):
            stored["texts"] = texts
            stored["embeddings"] = embeddings
            stored["ids"] = ids
            stored["metadatas"] = metadatas
            stored["collection_name"] = collection_name
            stored["embedding_model_id_for_dim_check"] = embedding_model_id_for_dim_check

    monkeypatch.setattr(
        embeddings_v5_production_enhanced,
        "create_embeddings_batch_async",
        fake_create_embeddings_batch_async,
    )
    monkeypatch.setattr(jobs_worker, "_resolve_model_provider", lambda *_: ("test-model", "test-provider"))
    monkeypatch.setattr(jobs_worker, "_kanban_card_indexable", lambda **_: True)
    monkeypatch.setattr(
        jobs_worker,
        "_embedding_config_for_user",
        lambda: {"USER_DB_BASE_DIR": str(tmp_path / "test")},
    )
    monkeypatch.setattr(jobs_worker, "ChromaDBManager", FakeChromaDBManager)

    job = {
        "job_type": "content_embeddings",
        "owner_user_id": "1",
        "payload": {
            "item_id": 55,
            "content": "hello kanban",
            "collection_name": "kanban_user_1",
            "document_id": "card_55",
            "metadata": {"card_id": 55, "board_id": 1, "list_id": 2},
            "request_source": "kanban",
            "card_id": 55,
            "card_version": 3,
        },
    }

    result = await jobs_worker._handle_job(job)

    assert result["embedding_count"] == 1
    assert created["user_id"] == "1"
    assert stored["collection_name"] == "kanban_user_1"
    assert stored["ids"] == ["card_55"]
    assert stored["metadatas"][0]["card_id"] == 55
    assert stored["embedding_model_id_for_dim_check"] == "test-model"


@pytest.mark.asyncio
async def test_embeddings_worker_storage_uses_user_scoped_chroma_manager(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = artifact_dir / "chunks.json"
    embeddings_path = artifact_dir / "embeddings.json"

    chunks_path.write_text(
        '[{"text": "hello embeddings", "index": 0, "start": 0, "end": 16}]',
        encoding="utf-8",
    )
    embeddings_path.write_text(
        '{"embeddings": [[0.1, 0.2, 0.3]], "embedding_model": "test-model", "embedding_provider": "test-provider"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(jobs_worker, "_artifact_dir", lambda *_, **__: artifact_dir)
    monkeypatch.setattr(
        jobs_worker,
        "_load_media_content",
        lambda *_: {"media_item": {"title": "Doc", "author": "A"}, "content": {"content": "hello embeddings"}},
    )
    monkeypatch.setattr(jobs_worker, "invalidate_rag_caches", lambda *_, **__: None)
    monkeypatch.setattr(jobs_worker, "_embedding_config_for_user", lambda: {"USER_DB_BASE_DIR": str(tmp_path)})

    captured: dict[str, object] = {}

    class FakeChromaDBManager:
        def __init__(self, *, user_id, user_embedding_config):
            captured["user_id"] = user_id
            captured["user_embedding_config"] = user_embedding_config

        def store_in_chroma(
            self,
            collection_name,
            texts,
            embeddings,
            ids,
            metadatas,
            embedding_model_id_for_dim_check=None,
        ):
            captured["collection_name"] = collection_name
            captured["texts"] = texts
            captured["embeddings"] = embeddings
            captured["ids"] = ids
            captured["metadatas"] = metadatas
            captured["embedding_model_id_for_dim_check"] = embedding_model_id_for_dim_check

    monkeypatch.setattr(jobs_worker, "ChromaDBManager", FakeChromaDBManager)

    result = await jobs_worker._handle_storage_job(
        job={"id": 1, "uuid": "job-1"},
        payload={},
        media_id=42,
        user_id="user-42",
        embedding_model="test-model",
        embedding_provider="test-provider",
        root_uuid=None,
    )

    assert result["embedding_count"] == 1
    assert captured["user_id"] == "user-42"
    assert captured["collection_name"] == "user_user-42_media_embeddings"
    assert captured["ids"] == ["media_42_chunk_0"]
    assert captured["embedding_model_id_for_dim_check"] == "test-model"


@pytest.mark.asyncio
async def test_embeddings_worker_storage_rejects_malformed_idempotent_artifact(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    storage_path = artifact_dir / "storage.json"
    storage_path.write_text('["bad-shape"]', encoding="utf-8")

    monkeypatch.setattr(jobs_worker, "_artifact_dir", lambda *_, **__: artifact_dir)

    with pytest.raises(jobs_worker.EmbeddingsJobError) as excinfo:
        await jobs_worker._handle_storage_job(
            job={"id": 2, "uuid": "job-2"},
            payload={},
            media_id=77,
            user_id="user-77",
            embedding_model="test-model",
            embedding_provider="test-provider",
            root_uuid=None,
        )

    assert "Storage artifact invalid for idempotent reuse" in str(excinfo.value)
    assert excinfo.value.retryable is False
