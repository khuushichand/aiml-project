"""Tests for the database-backed retrieval helpers in the RAG service."""

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Iterable

import pytest

from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import (
    MediaDBRetriever,
    MultiDatabaseRetriever,
    RetrievalConfig,
)
from tldw_Server_API.app.core.RAG.rag_service.types import DataSource, Document


@pytest.mark.unit
class TestRetrievalConfig:
    def test_defaults_match_expected_contract(self):
        cfg = RetrievalConfig()
        assert cfg.max_results == 20
        assert cfg.min_score == 0.0
        assert cfg.use_fts is True
        assert cfg.use_vector is True
        assert cfg.include_metadata is True

    def test_custom_configuration_preserves_values(self):

        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        cfg = RetrievalConfig(
            max_results=5,
            min_score=0.25,
            use_fts=False,
            use_vector=True,
            date_filter=(start, end),
            tags_filter=["tag-a"],
        )
        assert cfg.max_results == 5
        assert cfg.min_score == 0.25
        assert cfg.use_fts is False
        assert cfg.use_vector is True
        assert cfg.date_filter == (start, end)
        assert cfg.tags_filter == ["tag-a"]


@pytest.mark.unit
class TestMediaDBRetriever:
    def test_initializes_vector_store_from_default_factory_when_type_is_unset(self, monkeypatch):
        sentinel_store = object()
        factory_calls: list[tuple[dict, str]] = []

        def fake_factory(settings_dict: dict, user_id: str):
            factory_calls.append((settings_dict, user_id))
            return sentinel_store

        monkeypatch.setattr(
            "tldw_Server_API.app.core.config.settings",
            {"RAG": {}, "USER_DB_BASE_DIR": "/tmp"},
            raising=False,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.RAG.rag_service.database_retrievers.create_from_settings_for_user",
            fake_factory,
        )

        retriever = MediaDBRetriever(":memory:", user_id="user-7")

        assert retriever.vector_store is sentinel_store
        assert len(factory_calls) == 1
        assert factory_calls[0][1] == "user-7"

    @pytest.mark.asyncio
    async def test_vector_retrieval_uses_scoped_embedding_model_and_filter(self, monkeypatch):
        create_calls: list[dict[str, Any]] = []

        class FakeCollection:
            def __init__(self) -> None:
                self.last_get_kwargs: dict[str, Any] | None = None

            def get(self, **kwargs):
                self.last_get_kwargs = kwargs
                return {
                    "metadatas": [
                        {
                            "media_id": "10",
                            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                            "embedding_provider": "huggingface",
                        }
                    ]
                }

        class FakeManager:
            def __init__(self) -> None:
                self.collection = FakeCollection()

            def get_collection(self, _collection_name: str):
                return self.collection

        class FakeVectorStore:
            def __init__(self) -> None:
                self._initialized = True
                self.manager = FakeManager()
                self.search_calls: list[dict[str, Any]] = []

            async def initialize(self) -> None:
                self._initialized = True

            async def search(self, *, collection_name, query_vector, k, filter, include_metadata):
                self.search_calls.append(
                    {
                        "collection_name": collection_name,
                        "query_vector": query_vector,
                        "k": k,
                        "filter": filter,
                        "include_metadata": include_metadata,
                    }
                )
                return [
                    SimpleNamespace(
                        id="media_10_chunk_0",
                        content="Scoped vector match for media 10.",
                        metadata={"media_id": "10", "title": "Scoped Source"},
                        score=0.91,
                    )
                ]

        fake_vector_store = FakeVectorStore()

        def fake_factory(_settings_dict: dict, _user_id: str):
            return fake_vector_store

        def fake_create_embeddings_batch(texts, user_app_config, model_id_override=None):
            create_calls.append(
                {
                    "texts": list(texts),
                    "user_app_config": user_app_config,
                    "model_id_override": model_id_override,
                }
            )
            return [[0.12, 0.34, 0.56]]

        monkeypatch.setattr(
            "tldw_Server_API.app.core.config.settings",
            {"RAG": {}, "USER_DB_BASE_DIR": "/tmp"},
            raising=False,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.RAG.rag_service.database_retrievers.create_from_settings_for_user",
            fake_factory,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.get_embedding_config",
            lambda: {"embedding_config": {"default_model_id": None, "models": {}}},
            raising=True,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch",
            fake_create_embeddings_batch,
            raising=True,
        )

        retriever = MediaDBRetriever(":memory:", user_id="user-42")

        docs = await retriever._retrieve_vector(
            "what does the selected source say about evidence handling",
            allowed_media_ids=[10],
        )

        assert [doc.id for doc in docs] == ["10"]
        assert create_calls[0]["model_id_override"] == "huggingface:sentence-transformers/all-MiniLM-L6-v2"
        assert fake_vector_store.manager.collection.last_get_kwargs == {
            "where": {"media_id": "10"},
            "include": ["metadatas"],
            "limit": 5,
        }
        assert fake_vector_store.search_calls[0]["filter"] == {
            "$and": [{"media_id": "10"}, {"kind": "chunk"}]
        }

    @pytest.mark.asyncio
    async def test_vector_retrieval_falls_back_when_strict_collection_lookup_misses_scope(
        self,
        monkeypatch,
    ):
        create_calls: list[dict[str, Any]] = []

        class FakeCollection:
            def __init__(self) -> None:
                self.last_get_kwargs: dict[str, Any] | None = None

            def get(self, **kwargs):
                self.last_get_kwargs = kwargs
                return {
                    "metadatas": [
                        {
                            "media_id": "12",
                            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                            "embedding_provider": "huggingface",
                        }
                    ]
                }

        class FakeManager:
            def __init__(self) -> None:
                self.collection = FakeCollection()
                self.get_collection_calls = 0
                self.get_or_create_collection_calls = 0

            def get_collection(self, _collection_name: str):
                self.get_collection_calls += 1
                raise KeyError("Collection 'user_user-12_media_embeddings' does not exist")

            def get_or_create_collection(self, _collection_name: str):
                self.get_or_create_collection_calls += 1
                return self.collection

        class FakeVectorStore:
            def __init__(self) -> None:
                self._initialized = True
                self.manager = FakeManager()
                self.search_calls: list[dict[str, Any]] = []

            async def initialize(self) -> None:
                self._initialized = True

            async def search(self, *, collection_name, query_vector, k, filter, include_metadata):
                self.search_calls.append(
                    {
                        "collection_name": collection_name,
                        "query_vector": query_vector,
                        "k": k,
                        "filter": filter,
                        "include_metadata": include_metadata,
                    }
                )
                return [
                    SimpleNamespace(
                        id="media_12_chunk_0",
                        content="Scoped vector match for media 12.",
                        metadata={"media_id": "12", "title": "Scoped Source"},
                        score=0.88,
                    )
                ]

        fake_vector_store = FakeVectorStore()

        def fake_factory(_settings_dict: dict, _user_id: str):
            return fake_vector_store

        def fake_create_embeddings_batch(texts, user_app_config, model_id_override=None):
            create_calls.append(
                {
                    "texts": list(texts),
                    "user_app_config": user_app_config,
                    "model_id_override": model_id_override,
                }
            )
            return [[0.45, 0.67, 0.89]]

        monkeypatch.setattr(
            "tldw_Server_API.app.core.config.settings",
            {"RAG": {}, "USER_DB_BASE_DIR": "/tmp"},
            raising=False,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.RAG.rag_service.database_retrievers.create_from_settings_for_user",
            fake_factory,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.get_embedding_config",
            lambda: {"embedding_config": {"default_model_id": None, "models": {}}},
            raising=True,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch",
            fake_create_embeddings_batch,
            raising=True,
        )

        retriever = MediaDBRetriever(":memory:", user_id="user-12")

        docs = await retriever._retrieve_vector(
            "what does the selected source say about beta readiness",
            allowed_media_ids=[12],
        )

        assert [doc.id for doc in docs] == ["12"]
        assert create_calls[0]["model_id_override"] == "huggingface:sentence-transformers/all-MiniLM-L6-v2"
        assert fake_vector_store.manager.get_collection_calls == 1
        assert fake_vector_store.manager.get_or_create_collection_calls == 1
        assert fake_vector_store.manager.collection.last_get_kwargs == {
            "where": {"media_id": "12"},
            "include": ["metadatas"],
            "limit": 5,
        }

    @pytest.mark.asyncio
    async def test_retrieve_returns_documents_from_media_db(self, populated_media_db):
        retriever = MediaDBRetriever(str(populated_media_db.db_path))
        docs = await retriever.retrieve("retrieval")
        assert docs, "Expected at least one document for the seeded media database"
        _assert_documents(docs, expected_source=DataSource.MEDIA_DB)

    @pytest.mark.asyncio
    async def test_respects_max_results(self, populated_media_db):
        config = RetrievalConfig(max_results=1)
        retriever = MediaDBRetriever(str(populated_media_db.db_path), config=config)
        docs = await retriever.retrieve("retrieval")
        assert len(docs) == 1

    @pytest.mark.asyncio
    async def test_media_type_filter_applies(self, populated_media_db):
        retriever = MediaDBRetriever(str(populated_media_db.db_path))
        docs = await retriever.retrieve("vector", media_type="video")
        assert docs, "Fixture seeds a video entry containing the word 'vector'"
        assert all(doc.metadata.get("media_type") == "video" for doc in docs)


@pytest.mark.unit
class TestMultiDatabaseRetriever:
    @pytest.mark.asyncio
    async def test_retrieve_uses_media_db_when_present(self, populated_media_db):
        db_paths = {"media_db": str(populated_media_db.db_path)}
        retriever = MultiDatabaseRetriever(db_paths, user_id="test-user")
        config = RetrievalConfig(max_results=3, use_fts=True, use_vector=False, include_metadata=True)
        docs = await retriever.retrieve("retrieval", sources=[DataSource.MEDIA_DB], config=config)
        assert docs
        _assert_documents(docs, expected_source=DataSource.MEDIA_DB)
        scores = [doc.score for doc in docs]
        assert scores == sorted(scores, reverse=True)
        assert len(docs) <= 3

    @pytest.mark.asyncio
    async def test_retrieve_ignores_unknown_sources(self, populated_media_db):
        db_paths = {"media_db": str(populated_media_db.db_path)}
        retriever = MultiDatabaseRetriever(db_paths, user_id="test-user")
        docs = await retriever.retrieve("retrieval", sources=["nonexistent_source"])  # type: ignore[arg-type]
        assert docs == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_documents(docs: Iterable[Document], *, expected_source: DataSource) -> None:
    for doc in docs:
        assert isinstance(doc, Document)
        assert doc.source == expected_source
        assert isinstance(doc.content, str) and doc.content
        assert isinstance(doc.metadata, dict)
        assert isinstance(doc.score, float)
