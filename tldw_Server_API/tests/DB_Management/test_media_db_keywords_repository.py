from contextlib import contextmanager

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


def test_keywords_repository_replace_keywords_uses_single_transaction_connection(monkeypatch) -> None:
    db = MediaDatabase(db_path=":memory:", client_id="keywords-repo-transaction")
    repo = KeywordsRepository.from_legacy_db(db)
    try:
        media_id, _, _ = db.add_media_with_keywords(
            title="Repo doc",
            media_type="text",
            content="body",
            keywords=["old"],
        )
        original_add = KeywordsRepository.add
        original_transaction = db.transaction
        seen_conns: list[object] = []
        tx_state: dict[str, object] = {"count": 0, "conn": None}

        def _tracking_add(self, keyword: str, conn=None):
            seen_conns.append(conn)
            return original_add(self, keyword, conn=conn)

        @contextmanager
        def _tracking_transaction():
            tx_state["count"] = int(tx_state["count"]) + 1
            with original_transaction() as conn:
                tx_state["conn"] = conn
                yield conn

        monkeypatch.setattr(KeywordsRepository, "add", _tracking_add)
        monkeypatch.setattr(db, "transaction", _tracking_transaction)

        repo.replace_keywords(media_id, ["x", "y"])

        assert tx_state["count"] == 1
        assert tx_state["conn"] is not None
        assert seen_conns == [tx_state["conn"], tx_state["conn"]]
    finally:
        db.close_connection()
