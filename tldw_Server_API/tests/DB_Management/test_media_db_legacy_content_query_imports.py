import importlib

import pytest

from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api

pytestmark = pytest.mark.unit


def test_legacy_content_query_callers_no_longer_depend_on_media_db_v2_exports(
    monkeypatch,
) -> None:
    media_item = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media.item"
    )
    media_listing = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media.listing"
    )
    items_endpoint = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.items"
    )
    outputs_templates = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.outputs_templates"
    )

    assert media_item.fetch_keywords_for_media is media_db_api.fetch_keywords_for_media
    assert (
        media_listing.fetch_keywords_for_media_batch is media_db_api.fetch_keywords_for_media_batch
    )

    monkeypatch.setattr(
        media_db_api,
        "fetch_keywords_for_media",
        lambda db, media_id: ["alpha", "beta"],
    )
    monkeypatch.setattr(
        media_db_api,
        "get_document_version",
        lambda *args, **kwargs: {
            "analysis_content": "summary",
            "safe_metadata": {"published_at": "2024-01-01"},
        },
    )

    item = items_endpoint._media_row_to_item(
        {
            "id": 7,
            "title": "Tagged item",
            "url": "https://example.com/story",
            "content": "body",
            "type": "article",
        },
        db=object(),
        domain_filter=None,
    )
    assert item is not None
    assert item.tags == ["alpha", "beta"]

    class StubMediaDb:
        def search_media_db(self, **kwargs):
            assert kwargs["media_ids_filter"] == [7]
            return (
                [
                    {
                        "id": 7,
                        "title": "Tagged item",
                        "url": "https://example.com/story",
                        "content": "body",
                        "type": "article",
                        "ingestion_date": "2024-01-02T00:00:00Z",
                    }
                ],
                1,
            )

    items_context = outputs_templates._build_items_context_from_media_ids(
        StubMediaDb(),
        [7],
        5,
    )
    assert items_context[0]["tags"] == ["alpha", "beta"]
