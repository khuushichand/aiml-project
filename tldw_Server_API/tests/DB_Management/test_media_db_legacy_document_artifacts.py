from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.DB_Management.media_db.legacy_document_artifacts import (
    clear_specific_analysis,
    clear_specific_prompt,
    get_chunk_text,
    get_specific_analysis,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories.document_versions_repository import (
    DocumentVersionsRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories.media_repository import (
    MediaRepository,
)


def test_legacy_document_artifact_helpers_round_trip_analysis_prompt_and_chunk_text() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="legacy-document-artifacts")
    media_repo = MediaRepository.from_legacy_db(db)
    versions_repo = DocumentVersionsRepository.from_legacy_db(db)
    try:
        media_id, _media_uuid, _msg = media_repo.add_text_media(
            title="Artifact doc",
            content="artifact source",
            media_type="text",
        )
        version = versions_repo.create(
            media_id=media_id,
            content="v2",
            prompt="Prompt 2",
            analysis_content="Analysis 2",
        )
        db.process_unvectorized_chunks(
            media_id,
            [{"text": "chunk body", "chunk_index": 0}],
        )

        initial_analysis = get_specific_analysis(db, version["uuid"])
        cleared_analysis = clear_specific_analysis(db, version["uuid"])
        cleared_prompt = clear_specific_prompt(db, version["uuid"])
        chunk_uuid_row = db.execute_query(
            "SELECT uuid FROM UnvectorizedMediaChunks WHERE media_id = ? ORDER BY id DESC LIMIT 1",
            (media_id,),
        ).fetchone()
        current_version_row = db.execute_query(
            "SELECT analysis_content, prompt, version, client_id FROM DocumentVersions WHERE uuid = ?",
            (version["uuid"],),
        ).fetchone()
        sync_row = db.execute_query(
            """
            SELECT entity, operation, version, client_id
            FROM sync_log
            WHERE entity = 'DocumentVersions' AND entity_uuid = ?
            ORDER BY change_id DESC
            LIMIT 1
            """,
            (version["uuid"],),
        ).fetchone()
        chunk_text = get_chunk_text(db, chunk_uuid_row["uuid"])
        final_analysis = get_specific_analysis(db, version["uuid"])

        assert initial_analysis == "Analysis 2"
        assert cleared_analysis is True
        assert cleared_prompt is True
        assert chunk_text == "chunk body"
        assert final_analysis is None
        assert current_version_row is not None
        assert current_version_row["analysis_content"] is None
        assert current_version_row["prompt"] is None
        assert current_version_row["version"] == 3
        assert current_version_row["client_id"] == "legacy-document-artifacts"
        assert sync_row is not None
        assert sync_row["entity"] == "DocumentVersions"
        assert sync_row["operation"] == "update"
        assert sync_row["version"] == 3
        assert sync_row["client_id"] == "legacy-document-artifacts"
    finally:
        db.close_connection()
