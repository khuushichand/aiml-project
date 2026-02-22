from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _test_env(monkeypatch, tmp_path):
    base_dir = tmp_path / "test_user_dbs_collections_fts"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    yield


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _upsert_watchlist_item(
    db: CollectionsDatabase,
    *,
    url: str,
    title: str,
    summary: str,
    tags: list[str],
) -> int:
    row = db.upsert_content_item(
        origin="watchlist",
        origin_type="rss",
        origin_id=1,
        url=url,
        canonical_url=url,
        domain="example.com",
        title=title,
        summary=summary,
        notes=None,
        content_hash=_digest(f"{title}|{summary}"),
        word_count=len(summary.split()),
        published_at=datetime.now(timezone.utc).isoformat(),
        status="new",
        favorite=False,
        metadata={"source": "test"},
        media_id=None,
        job_id=1,
        run_id=1,
        source_id=1,
        read_at=None,
        tags=tags,
    )
    return int(row.id)


def test_contentless_fts_handles_upsert_update_and_delete():
    db = CollectionsDatabase.for_user(641)

    item_id = _upsert_watchlist_item(
        db,
        url="https://example.com/a",
        title="Alpha release",
        summary="Alpha summary",
        tags=["alpha"],
    )

    alpha_rows, alpha_total = db.list_content_items(origin="watchlist", q="Alpha", size=50)
    assert alpha_total == 1
    assert any(row.id == item_id for row in alpha_rows)

    # Update the same canonical URL so upsert executes the update path.
    _upsert_watchlist_item(
        db,
        url="https://example.com/a",
        title="Beta release",
        summary="Beta summary",
        tags=["beta"],
    )

    alpha_rows_after, alpha_total_after = db.list_content_items(origin="watchlist", q="Alpha", size=50)
    assert alpha_total_after == 0
    assert alpha_rows_after == []

    beta_rows, beta_total = db.list_content_items(origin="watchlist", q="Beta", size=50)
    assert beta_total == 1
    assert any(row.id == item_id for row in beta_rows)

    db.delete_content_item(item_id)
    beta_rows_after_delete, beta_total_after_delete = db.list_content_items(origin="watchlist", q="Beta", size=50)
    assert beta_total_after_delete == 0
    assert beta_rows_after_delete == []
