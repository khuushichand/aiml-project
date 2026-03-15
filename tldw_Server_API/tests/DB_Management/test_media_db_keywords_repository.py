from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.media_db.repositories.keywords_repository import (
    KeywordsRepository,
)


def test_keywords_repository_replaces_keyword_set() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="keywords-repo")
    repo = KeywordsRepository.from_legacy_db(db)
    try:
        media_id, _, _ = db.add_media_with_keywords(
            title="Repo doc",
            media_type="text",
            content="body",
            keywords=["old"],
        )

        repo.replace_keywords(media_id, ["x", "y"])

        assert set(repo.fetch_for_media(media_id)) == {"x", "y"}
    finally:
        db.close_connection()


def test_keywords_repository_soft_delete_hides_keyword() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="keywords-repo-delete")
    repo = KeywordsRepository.from_legacy_db(db)
    try:
        repo.add("alpha")
        assert repo.soft_delete("alpha") is True

        media_id, _, _ = db.add_media_with_keywords(
            title="Delete doc",
            media_type="text",
            content="body",
            keywords=["beta"],
        )
        assert repo.fetch_for_media(media_id) == ["beta"]
    finally:
        db.close_connection()
