"""Tests for the database-backed retrieval helpers in the RAG service."""

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import (
    MediaDatabaseError,
    MediaDBRetriever,
    MultiDatabaseRetriever,
    RetrievalConfig,
    _derive_bounded_media_term_query,
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

    @pytest.mark.asyncio
    async def test_chunk_level_retrieval_falls_back_to_media_when_media_has_no_chunks(self, tmp_path: Path):
        db = _create_media_db(tmp_path)
        media_id, _, _ = db.add_media_with_keywords(
            title="weakness frieza saiyans chunk doc",
            media_type="transcript",
            content=(
                "This document includes the exact fallback phrase weakness frieza saiyans."
            ),
            keywords=["frieza", "weakness", "saiyans"],
        )

        retriever = MediaDBRetriever(
            db_path=str(db.db_path),
            config=RetrievalConfig(max_results=5, use_fts=True, use_vector=False, fts_level="chunk"),
            media_db=db,
            user_id="0",
        )

        docs = await retriever.retrieve("What weakness does Frieza reveal about the Saiyans?")

        assert docs
        assert docs[0].id == str(media_id)
        assert docs[0].metadata.get("media_type") == "transcript"
        assert docs[0].metadata.get("chunk_index") is None

    @pytest.mark.asyncio
    async def test_media_retrieval_retries_with_bounded_terms_after_strict_query_miss(self, tmp_path: Path, monkeypatch):
        db = _create_media_db(tmp_path)
        media_id, _, _ = db.add_media_with_keywords(
            title="weakness frieza saiyans doc",
            media_type="transcript",
            content=(
                "This document includes the exact fallback phrase weakness frieza saiyans."
            ),
            keywords=["frieza", "weakness", "saiyans"],
        )
        query = "What weakness does Frieza mention about the Saiyans during the fight?"
        expected_fallback_query = _derive_bounded_media_term_query(query)
        assert expected_fallback_query == "weakness frieza saiyans"

        retriever = MediaDBRetriever(
            db_path=str(db.db_path),
            config=RetrievalConfig(max_results=5, use_fts=True, use_vector=False),
            media_db=db,
            user_id="0",
        )

        calls: list[dict[str, object]] = []
        real_search_media_db = db.search_media_db

        def _spy_search_media_db(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            if len(calls) == 1:
                return [], 0
            return real_search_media_db(*args, **kwargs)

        monkeypatch.setattr(db, "search_media_db", _spy_search_media_db)

        docs = await retriever.retrieve(query)

        assert docs
        assert str(media_id) in {doc.id for doc in docs}
        assert any("weakness frieza saiyans" in doc.content.lower() for doc in docs)
        assert len(calls) == 2
        assert calls[0]["kwargs"]["search_query"] == query
        assert calls[1]["kwargs"]["search_query"] == expected_fallback_query

    @pytest.mark.asyncio
    async def test_media_retrieval_does_not_fallback_when_rows_exist_but_docs_are_filtered_out(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        db = _create_media_db(tmp_path)
        db.add_media_with_keywords(
            title="row-presence doc",
            media_type="transcript",
            content="This row exists but will be filtered out after retrieval.",
            keywords=["row", "presence"],
        )

        retriever = MediaDBRetriever(
            db_path=str(db.db_path),
            config=RetrievalConfig(max_results=5, use_fts=True, use_vector=False),
            media_db=db,
            user_id="0",
        )

        calls: list[dict[str, object]] = []

        def _spy_search_media_db(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return ([{
                "id": 1,
                "title": "row-presence doc",
                "content": "This row exists but will be filtered out after retrieval.",
                "type": "transcript",
                "url": None,
                "ingestion_date": None,
                "transcription_model": None,
                "last_modified": None,
                "relevance_score": 0.0,
            }], 1)

        monkeypatch.setattr(db, "search_media_db", _spy_search_media_db)
        monkeypatch.setattr(
            MediaDBRetriever,
            "_build_media_documents",
            lambda self, results, *, backend_type: [],
        )

        docs = await retriever.retrieve("What weakness does Frieza mention about the Saiyans during the fight?")

        assert docs == []
        assert len(calls) == 1
        assert calls[0]["kwargs"]["search_query"] == "What weakness does Frieza mention about the Saiyans during the fight?"

    @pytest.mark.asyncio
    async def test_media_fallback_respects_allowed_media_ids(self, tmp_path: Path, monkeypatch):
        db = _create_media_db(tmp_path)
        allowed_media_id, allowed_uuid, _ = db.add_media_with_keywords(
            title="weakness frieza saiyans allowed doc",
            media_type="transcript",
            content=(
                "This document includes the exact fallback phrase weakness frieza saiyans."
            ),
            keywords=["frieza", "weakness", "saiyans"],
        )
        blocked_media_id, _, _ = db.add_media_with_keywords(
            title="weakness frieza saiyans blocked doc",
            media_type="transcript",
            content=(
                "This document includes the exact fallback phrase weakness frieza saiyans "
                "with blocked-only extra details."
            ),
            keywords=["frieza", "weakness", "saiyans"],
        )
        query = "What weakness does Frieza mention about the Saiyans during the fight?"
        expected_fallback_query = _derive_bounded_media_term_query(query)
        assert expected_fallback_query == "weakness frieza saiyans"

        retriever = MediaDBRetriever(
            db_path=str(db.db_path),
            config=RetrievalConfig(max_results=10, use_fts=True, use_vector=False),
            media_db=db,
            user_id="0",
        )

        calls: list[dict[str, object]] = []
        real_search_media_db = db.search_media_db

        def _spy_search_media_db(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            if len(calls) == 1:
                return [], 0
            return real_search_media_db(*args, **kwargs)

        monkeypatch.setattr(db, "search_media_db", _spy_search_media_db)

        docs = await retriever.retrieve(
            query,
            allowed_media_ids=[allowed_uuid],
        )

        assert {doc.id for doc in docs} == {str(allowed_media_id)}
        assert str(blocked_media_id) not in {doc.id for doc in docs}
        assert len(calls) == 2
        assert calls[0]["kwargs"]["search_query"] == query
        assert calls[1]["kwargs"]["search_query"] == expected_fallback_query
        assert calls[0]["kwargs"]["media_ids_filter"] == [allowed_uuid]
        assert calls[1]["kwargs"]["media_ids_filter"] == [allowed_uuid]

    @pytest.mark.asyncio
    async def test_chunk_level_retrieval_does_not_fall_back_when_chunk_rows_exist_but_docs_are_filtered_out(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        db = _create_media_db(tmp_path)
        db.add_media_with_keywords(
            title="Chunk row presence doc",
            media_type="transcript",
            content="Chunk row exists but will be filtered out after retrieval.",
            keywords=["chunk", "presence"],
            chunks=[
                {
                    "text": "Chunk row exists but will be filtered out after retrieval.",
                    "start_char": 0,
                    "end_char": 59,
                    "chunk_type": "text",
                    "metadata": {"speaker": "Narrator"},
                }
            ],
        )

        retriever = MediaDBRetriever(
            db_path=str(db.db_path),
            config=RetrievalConfig(max_results=5, use_fts=True, use_vector=False, fts_level="chunk"),
            media_db=db,
            user_id="0",
        )

        monkeypatch.setattr(
            MediaDBRetriever,
            "_retrieve_chunk_fts_with_stats",
            lambda self, query, media_type, **kwargs: ([], 1),
        )
        monkeypatch.setattr(
            MediaDBRetriever,
            "_retrieve_via_backend",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Media fallback should not run")),
        )

        docs = await retriever.retrieve("Chunk row exists but will be filtered out after retrieval.")

        assert docs == []

    @pytest.mark.asyncio
    async def test_chunk_level_retrieval_still_returns_chunk_documents_when_chunks_exist(self, tmp_path: Path):
        db = _create_media_db(tmp_path)
        content = "Alpha scouting report.\n\nVegeta calls out Frieza's weakness."
        start = content.index("Vegeta")
        end = start + len("Vegeta calls out Frieza's weakness.")
        media_id, _, _ = db.add_media_with_keywords(
            title="Chunked Frieza Doc",
            media_type="transcript",
            content=content,
            keywords=["frieza"],
            chunks=[
                {
                    "text": "Alpha scouting report.",
                    "start_char": 0,
                    "end_char": len("Alpha scouting report."),
                    "chunk_type": "text",
                    "metadata": {"speaker": "Narrator"},
                },
                {
                    "text": content[start:end],
                    "start_char": start,
                    "end_char": end,
                    "chunk_type": "text",
                    "metadata": {"speaker": "Vegeta"},
                }
            ],
        )
        db.ensure_chunk_fts()
        db.maybe_rebuild_chunk_fts_if_empty()

        retriever = MediaDBRetriever(
            db_path=str(db.db_path),
            config=RetrievalConfig(max_results=5, use_fts=True, use_vector=False, fts_level="chunk"),
            media_db=db,
            user_id="0",
        )

        docs = await retriever.retrieve("Vegeta", media_type="transcript")

        assert docs
        assert docs[0].metadata.get("media_id") == str(media_id)
        assert docs[0].metadata.get("chunk_index") == 1

    @pytest.mark.asyncio
    async def test_chunk_level_retrieval_respects_uuid_allowed_media_ids_without_falling_back(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        db = _create_media_db(tmp_path)
        content = "Alpha scouting report.\n\nVegeta calls out Frieza's weakness."
        start = content.index("Vegeta")
        end = start + len("Vegeta calls out Frieza's weakness.")
        media_id, media_uuid, _ = db.add_media_with_keywords(
            title="Chunked Frieza UUID Doc",
            media_type="transcript",
            content=content,
            keywords=["frieza"],
            chunks=[
                {
                    "text": "Alpha scouting report.",
                    "start_char": 0,
                    "end_char": len("Alpha scouting report."),
                    "chunk_type": "text",
                    "metadata": {"speaker": "Narrator"},
                },
                {
                    "text": content[start:end],
                    "start_char": start,
                    "end_char": end,
                    "chunk_type": "text",
                    "metadata": {"speaker": "Vegeta"},
                },
            ],
        )
        db.ensure_chunk_fts()
        db.maybe_rebuild_chunk_fts_if_empty()

        retriever = MediaDBRetriever(
            db_path=str(db.db_path),
            config=RetrievalConfig(max_results=5, use_fts=True, use_vector=False, fts_level="chunk"),
            media_db=db,
            user_id="0",
        )

        monkeypatch.setattr(
            MediaDBRetriever,
            "_retrieve_via_backend",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Media fallback should not run")),
        )

        docs = await retriever.retrieve("Vegeta", allowed_media_ids=[media_uuid])

        assert docs
        assert all(doc.metadata.get("media_id") == str(media_id) for doc in docs)
        assert all(doc.metadata.get("chunk_index") == 1 for doc in docs)
        assert all(doc.id != str(media_id) for doc in docs)

    def test_attach_media_db_uses_shared_factory(self, monkeypatch, tmp_path):
        import tldw_Server_API.app.core.RAG.rag_service.database_retrievers as retr_mod

        events: list[tuple[str, object]] = []

        class _FakeDb:
            def close_connection(self):
                events.append(("close", None))

        def _fake_create_media_database(client_id, **kwargs):
            events.append(("create", client_id))
            events.append(("kwargs", kwargs))
            return _FakeDb()

        monkeypatch.setattr(retr_mod, "create_media_database", _fake_create_media_database)
        monkeypatch.setattr(retr_mod.MediaDBRetriever, "_initialize_vector_store", lambda self: None)

        retriever = retr_mod.MediaDBRetriever(str(tmp_path / "media.db"))

        try:
            assert retriever._own_media_db is True
            assert isinstance(retriever.media_db, _FakeDb)
            assert retriever._db_adapter is retriever.media_db
            assert events[:2] == [
                ("create", "rag_service"),
                ("kwargs", {"db_path": str((tmp_path / "media.db").resolve())}),
            ]
        finally:
            retriever.close()

        assert ("close", None) in events

    def test_attach_media_db_propagates_factory_configuration_errors(self, monkeypatch, tmp_path):
        import tldw_Server_API.app.core.RAG.rag_service.database_retrievers as retr_mod

        monkeypatch.setattr(
            retr_mod,
            "create_media_database",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(MediaDatabaseError("bad config")),
        )
        monkeypatch.setattr(retr_mod.MediaDBRetriever, "_initialize_vector_store", lambda self: None)

        with pytest.raises(MediaDatabaseError):
            retr_mod.MediaDBRetriever(str(tmp_path / "media.db"))


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


@pytest.mark.unit
def test_claims_retriever_attach_uses_shared_factory(monkeypatch, tmp_path):
    import tldw_Server_API.app.core.RAG.rag_service.database_retrievers as retr_mod

    events: list[tuple[str, object]] = []

    class _FakeDb:
        def close_connection(self):
            events.append(("close", None))

    def _fake_create_media_database(client_id, **kwargs):
        events.append(("create", client_id))
        events.append(("kwargs", kwargs))
        return _FakeDb()

    monkeypatch.setattr(retr_mod, "create_media_database", _fake_create_media_database)

    retriever = retr_mod.ClaimsRetriever(str(tmp_path / "claims.db"))

    try:
        assert retriever._own_media_db is True
        assert isinstance(retriever.media_db, _FakeDb)
        assert retriever._db_adapter is retriever.media_db
        assert events[:2] == [
            ("create", "rag_service"),
            ("kwargs", {"db_path": str((tmp_path / "claims.db").resolve())}),
        ]
    finally:
        retriever.close()

    assert ("close", None) in events


@pytest.mark.unit
def test_claims_retriever_attach_propagates_factory_configuration_errors(monkeypatch, tmp_path):
    import tldw_Server_API.app.core.RAG.rag_service.database_retrievers as retr_mod

    monkeypatch.setattr(
        retr_mod,
        "create_media_database",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad path")),
    )

    with pytest.raises(ValueError):
        retr_mod.ClaimsRetriever(str(tmp_path / "claims.db"))


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


def _create_media_db(tmp_path: Path) -> MediaDatabase:
    db_path = tmp_path / "media.db"
    db = MediaDatabase(db_path=str(db_path), client_id="pytest")
    db.initialize_db()
    return db
