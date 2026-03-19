from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.media_db.legacy_content_queries import (
    fetch_keywords_for_media,
    fetch_keywords_for_media_batch,
    get_all_content_from_database,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories.media_repository import (
    MediaRepository,
)


def test_legacy_content_queries_round_trip_content_and_keyword_views() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="legacy-content-queries")
    media_repo = MediaRepository.from_legacy_db(db)
    try:
        first_id, first_uuid, _ = media_repo.add_text_media(
            title="First doc",
            content="alpha body",
            media_type="text",
            keywords=["beta", "alpha"],
        )
        second_id, second_uuid, _ = media_repo.add_text_media(
            title="Second doc",
            content="plain body",
            media_type="text",
        )

        content_rows = get_all_content_from_database(db)
        first_keywords = fetch_keywords_for_media(first_id, db)
        batch_keywords = fetch_keywords_for_media_batch([first_id, second_id], db)

        returned_ids = {row["id"] for row in content_rows}
        row_by_id = {row["id"]: row for row in content_rows}

        assert returned_ids == {first_id, second_id}
        assert row_by_id[first_id]["uuid"] == first_uuid
        assert row_by_id[first_id]["title"] == "First doc"
        assert row_by_id[first_id]["type"] == "text"
        assert row_by_id[second_id]["uuid"] == second_uuid
        assert row_by_id[second_id]["content"] == "plain body"
        assert first_keywords == ["alpha", "beta"]
        assert batch_keywords == {
            first_id: ["alpha", "beta"],
            second_id: [],
        }
    finally:
        db.close_connection()
