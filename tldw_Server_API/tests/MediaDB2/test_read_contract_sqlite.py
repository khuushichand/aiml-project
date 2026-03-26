from __future__ import annotations

from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api
from tldw_Server_API.app.core.DB_Management.scope_context import scoped_context


def test_search_media_contract_filters_scope_visibility_sqlite(memory_db_factory):
    from tldw_Server_API.app.core.DB_Management.media_db.repositories.media_search_repository import (
        MediaSearchRepository,
    )

    db = memory_db_factory("search_contract_sqlite")

    with scoped_context(user_id=101, org_ids=[], team_ids=[], is_admin=False):
        personal_id, _, _ = db.add_media_with_keywords(
            title="Personal Contract Doc",
            content="scope contract content personal",
            media_type="text",
            keywords=[],
            owner_user_id=101,
        )

    with scoped_context(user_id=303, org_ids=[], team_ids=[77], is_admin=False):
        team_id, _, _ = db.add_media_with_keywords(
            title="Team Contract Doc",
            content="scope contract content team",
            media_type="text",
            keywords=[],
            visibility="team",
            owner_user_id=303,
        )

    with scoped_context(user_id=606, org_ids=[12], team_ids=[], is_admin=False):
        org_id, _, _ = db.add_media_with_keywords(
            title="Org Contract Doc",
            content="scope contract content org",
            media_type="text",
            keywords=[],
            visibility="org",
            owner_user_id=606,
        )

    with scoped_context(user_id=202, org_ids=[], team_ids=[], is_admin=False):
        hidden_id, _, _ = db.add_media_with_keywords(
            title="Hidden Contract Doc",
            content="scope contract content hidden",
            media_type="text",
            keywords=[],
            owner_user_id=202,
        )

    repo = MediaSearchRepository.from_legacy_db(db)

    with scoped_context(user_id=101, org_ids=[12], team_ids=[77], is_admin=False):
        rows, total = repo.search(
            search_query=None,
            search_fields=[],
            page=1,
            results_per_page=20,
        )

    row_ids = {row["id"] for row in rows}
    assert total == 3
    assert row_ids == {personal_id, team_id, org_id}
    assert hidden_id not in row_ids


def test_search_media_contract_media_db_v2_delegates_to_api(monkeypatch, memory_db_factory):
    db = memory_db_factory("search_contract_delegate")
    called: dict[str, object] = {}

    def _fake_search_media(_db, search_query, **kwargs):
        called["db"] = _db
        called["search_query"] = search_query
        called["kwargs"] = kwargs
        return ([{"id": 77, "title": "Delegated"}], 1)

    monkeypatch.setattr(
        media_db_api,
        "search_media",
        _fake_search_media,
    )

    rows, total = db.search_media_db(
        search_query="delegated",
        search_fields=["title"],
        page=2,
        results_per_page=5,
    )

    assert called["db"] is db
    assert called["search_query"] == "delegated"
    assert called["kwargs"] == {
        "search_fields": ["title"],
        "media_types": None,
        "date_range": None,
        "must_have_keywords": None,
        "must_not_have_keywords": None,
        "sort_by": "last_modified_desc",
        "boost_fields": None,
        "media_ids_filter": None,
        "page": 2,
        "results_per_page": 5,
        "include_trash": False,
        "include_deleted": False,
    }
    assert rows == [{"id": 77, "title": "Delegated"}]
    assert total == 1
