import pytest

from tldw_Server_API.app.api.v1.endpoints import (
    embeddings_v5_production_enhanced,
    media_embeddings,
)


@pytest.mark.asyncio
async def test_generate_embeddings_for_media_uses_user_scoped_chroma_manager(monkeypatch):
    async def fake_create_embeddings_batch_async(*, texts, provider, model_id, metadata):
        assert texts == ["hello world"]
        assert provider == "test-provider"
        assert model_id == "test-model"
        assert metadata.get("user_id") == "tenant-7"
        return [[0.1, 0.2, 0.3]]

    created: dict[str, object] = {}
    stored: dict[str, object] = {}

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
            stored["collection_name"] = collection_name
            stored["texts"] = texts
            stored["embeddings"] = embeddings
            stored["ids"] = ids
            stored["metadatas"] = metadatas
            stored["embedding_model_id_for_dim_check"] = embedding_model_id_for_dim_check

    monkeypatch.setattr(
        embeddings_v5_production_enhanced,
        "create_embeddings_batch_async",
        fake_create_embeddings_batch_async,
    )
    monkeypatch.setattr(
        media_embeddings,
        "chunk_media_content",
        lambda *_args, **_kwargs: [{"text": "hello world", "index": 0, "start": 0, "end": 11}],
    )
    monkeypatch.setattr(
        media_embeddings,
        "_user_embedding_config",
        lambda: {"USER_DB_BASE_DIR": "/tmp/test"},
    )
    monkeypatch.setattr(media_embeddings, "ChromaDBManager", FakeChromaDBManager)

    media_content = {
        "media_item": {"title": "Doc", "author": "Author", "metadata": {}},
        "content": {"content": "hello world"},
    }
    result = await media_embeddings.generate_embeddings_for_media(
        media_id=42,
        media_content=media_content,
        embedding_model="test-model",
        embedding_provider="test-provider",
        chunk_size=1000,
        chunk_overlap=200,
        user_id="tenant-7",
    )

    assert result["status"] == "success"
    assert result["embedding_count"] == 1
    assert created["user_id"] == "tenant-7"
    assert stored["collection_name"] == "user_tenant-7_media_embeddings"
    assert stored["ids"] == ["media_42_chunk_0"]
    assert stored["embedding_model_id_for_dim_check"] == "test-model"
