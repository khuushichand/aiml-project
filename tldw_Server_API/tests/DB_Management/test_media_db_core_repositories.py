from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.media_db.repositories.chunks_repository import (
    ChunksRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories.document_versions_repository import (
    DocumentVersionsRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories.media_repository import (
    MediaRepository,
)


def test_media_database_add_media_with_keywords_delegates_to_media_repository(monkeypatch) -> None:
    db = MediaDatabase(db_path=":memory:", client_id="media-delegate")
    sentinel = (321, "repo-uuid", "delegated")
    captured: dict[str, object] = {}

    def fake_add_media_with_keywords(self, **kwargs):
        captured["session"] = self.session
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(
        MediaRepository,
        "add_media_with_keywords",
        fake_add_media_with_keywords,
        raising=False,
    )

    try:
        result = db.add_media_with_keywords(
            title="Delegated doc",
            content="delegate me",
            media_type="text",
            keywords=["alpha", "beta"],
            visibility="personal",
        )

        assert result == sentinel
        assert captured["session"] is db
        assert captured["kwargs"] == {
            "url": None,
            "title": "Delegated doc",
            "media_type": "text",
            "content": "delegate me",
            "keywords": ["alpha", "beta"],
            "prompt": None,
            "analysis_content": None,
            "safe_metadata": None,
            "source_hash": None,
            "transcription_model": None,
            "author": None,
            "ingestion_date": None,
            "overwrite": False,
            "chunk_options": None,
            "chunks": None,
            "visibility": "personal",
            "owner_user_id": None,
        }
    finally:
        db.close_connection()


def test_media_repository_add_text_media_creates_row() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="media-repo")
    repo = MediaRepository.from_legacy_db(db)
    try:
        media_id, media_uuid, message = repo.add_text_media(
            title="Repo doc",
            content="hello",
            media_type="text",
            keywords=["alpha"],
        )

        assert isinstance(media_id, int)
        assert isinstance(media_uuid, str)
        assert "added" in message.lower()
    finally:
        db.close_connection()


def test_document_versions_repository_returns_latest_version() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="doc-repo")
    media_repo = MediaRepository.from_legacy_db(db)
    versions_repo = DocumentVersionsRepository.from_legacy_db(db)
    try:
        media_id, _, _ = media_repo.add_text_media(
            title="Versioned doc",
            content="v1",
            media_type="text",
        )
        versions_repo.create(media_id=media_id, content="v2", prompt="p2", analysis_content="a2")

        latest = versions_repo.get(media_id=media_id, version_number=None, include_content=True)

        assert latest is not None
        assert latest["version_number"] == 2
        assert latest["content"] == "v2"
    finally:
        db.close_connection()


def test_chunks_repository_batch_insert_generates_unique_chunk_ids() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="chunk-repo")
    media_repo = MediaRepository.from_legacy_db(db)
    chunks_repo = ChunksRepository.from_legacy_db(db)
    try:
        media_id, _, _ = media_repo.add_text_media(
            title="Chunked doc",
            content="chunk source",
            media_type="text",
        )

        inserted = chunks_repo.batch_insert(
            media_id,
            [
                {"text": "chunk-1", "metadata": {"start_index": 0, "end_index": 5}},
                {"text": "chunk-2", "metadata": {"start_index": 6, "end_index": 11}},
            ],
        )

        assert inserted == 2

        rows = db.execute_query(
            "SELECT chunk_id FROM MediaChunks WHERE media_id = ? ORDER BY id",
            (media_id,),
        ).fetchall()
        chunk_ids = [row["chunk_id"] for row in rows]
        assert len(chunk_ids) == 2
        assert len(set(chunk_ids)) == 2
    finally:
        db.close_connection()
