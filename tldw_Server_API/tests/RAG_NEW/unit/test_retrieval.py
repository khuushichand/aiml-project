"""Tests for the database-backed retrieval helpers in the RAG service."""

from datetime import datetime
from typing import Iterable

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
