from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase, upsert_transcript
from tldw_Server_API.app.core.DB_Management.media_db.legacy_wrappers import (
    get_document_version,
    import_obsidian_note_to_db,
    ingest_article_to_db_new,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_reads import (
    get_latest_transcription,
    get_media_prompts,
    get_media_transcripts,
    get_specific_prompt,
    get_specific_transcript,
)
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


def test_ingest_article_wrapper_uses_media_repository(monkeypatch) -> None:
    db = MediaDatabase(db_path=":memory:", client_id="article-wrapper")
    sentinel = (98, "article-uuid", "article delegated")
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
    monkeypatch.setattr(
        db,
        "add_media_with_keywords",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy shim should not be used")),
    )

    try:
        result = ingest_article_to_db_new(
            db,
            url="https://example.com/article",
            title="Example Article",
            content="Article body",
            author="Author",
            keywords=["alpha"],
            summary="Summary",
            ingestion_date="2024-01-02T03:04:05Z",
            custom_prompt="Prompt",
            overwrite=True,
        )

        assert result == sentinel
        assert captured["session"] is db
        assert captured["kwargs"] == {
            "url": "https://example.com/article",
            "title": "Example Article",
            "media_type": "article",
            "content": "Article body",
            "keywords": ["alpha"],
            "prompt": "Prompt",
            "analysis_content": "Summary",
            "author": "Author",
            "ingestion_date": "2024-01-02T03:04:05Z",
            "overwrite": True,
        }
    finally:
        db.close_connection()


def test_import_obsidian_note_wrapper_uses_media_repository(monkeypatch) -> None:
    db = MediaDatabase(db_path=":memory:", client_id="obsidian-wrapper")
    sentinel = (77, "obsidian-uuid", "obsidian delegated")
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
    monkeypatch.setattr(
        db,
        "add_media_with_keywords",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy shim should not be used")),
    )

    try:
        result = import_obsidian_note_to_db(
            db,
            {
                "title": "Daily Note",
                "content": "Note body",
                "tags": ["tag-a", 7, None],
                "frontmatter": {"author": "Jane", "status": "draft"},
                "file_created_date": "2024-01-02T03:04:05Z",
                "overwrite": True,
            },
        )

        assert result == sentinel
        assert captured["session"] is db
        assert captured["kwargs"]["url"] == "obsidian://note/Daily Note"
        assert captured["kwargs"]["title"] == "Daily Note"
        assert captured["kwargs"]["media_type"] == "obsidian_note"
        assert captured["kwargs"]["content"] == "Note body"
        assert captured["kwargs"]["keywords"] == ["tag-a", "7"]
        assert captured["kwargs"]["author"] == "Jane"
        assert captured["kwargs"]["prompt"] == "Obsidian Frontmatter"
        assert "author: Jane" in str(captured["kwargs"]["analysis_content"])
        assert captured["kwargs"]["ingestion_date"] == "2024-01-02T03:04:05Z"
        assert captured["kwargs"]["overwrite"] is True
    finally:
        db.close_connection()


def test_get_document_version_wrapper_uses_document_versions_repository(monkeypatch) -> None:
    db = MediaDatabase(db_path=":memory:", client_id="version-wrapper")
    sentinel = {"media_id": 11, "version_number": 2, "content": "delegated"}
    captured: dict[str, object] = {}

    def fake_get(self, *, media_id, version_number=None, include_content=True):
        captured["session"] = self.session
        captured["kwargs"] = {
            "media_id": media_id,
            "version_number": version_number,
            "include_content": include_content,
        }
        return sentinel

    monkeypatch.setattr(
        DocumentVersionsRepository,
        "get",
        fake_get,
        raising=False,
    )

    try:
        result = get_document_version(
            db,
            media_id=11,
            version_number=2,
            include_content=False,
        )

        assert result == sentinel
        assert captured["session"] is db
        assert captured["kwargs"] == {
            "media_id": 11,
            "version_number": 2,
            "include_content": False,
        }
    finally:
        db.close_connection()


def test_legacy_read_wrappers_round_trip_transcripts_and_prompts() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="legacy-read-wrappers")
    media_repo = MediaRepository.from_legacy_db(db)
    versions_repo = DocumentVersionsRepository.from_legacy_db(db)
    try:
        media_id, _media_uuid, _msg = media_repo.add_text_media(
            title="Prompted doc",
            content="v1",
            media_type="text",
        )
        version = versions_repo.create(
            media_id=media_id,
            content="v2",
            prompt="Prompt 2",
            analysis_content="Analysis 2",
        )
        transcript = upsert_transcript(
            db,
            media_id=media_id,
            transcription='{"text": "Transcript text"}',
            whisper_model="base",
        )

        prompts = get_media_prompts(db, media_id)
        transcripts = get_media_transcripts(db, media_id)
        latest_transcript = get_latest_transcription(db, media_id)
        specific_prompt = get_specific_prompt(db, version["uuid"])
        specific_transcript = get_specific_transcript(db, transcript["uuid"])

        assert [item["content"] for item in prompts] == ["Prompt 2"]
        assert len(transcripts) == 1
        assert transcripts[0]["uuid"] == transcript["uuid"]
        assert latest_transcript == "Transcript text"
        assert specific_prompt == "Prompt 2"
        assert specific_transcript is not None
        assert specific_transcript["uuid"] == transcript["uuid"]
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
