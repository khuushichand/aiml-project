import importlib

import pytest

from tldw_Server_API.app.core.DB_Management.media_db import legacy_content_queries
from tldw_Server_API.app.core.DB_Management.media_db import legacy_wrappers


@pytest.mark.asyncio
async def test_legacy_document_version_callers_use_extracted_wrapper(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    items_endpoint = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.items"
    )
    outputs_templates = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.outputs_templates"
    )
    media_embeddings = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media_embeddings"
    )
    jobs_worker = importlib.import_module(
        "tldw_Server_API.app.core.Embeddings.services.jobs_worker"
    )

    def _shim_should_not_be_used(*args, **kwargs):
        raise AssertionError("Media_DB_v2.get_document_version should not be used here")

    monkeypatch.setattr(media_db_v2, "get_document_version", _shim_should_not_be_used)
    monkeypatch.setattr(
        legacy_content_queries,
        "fetch_keywords_for_media",
        lambda media_id, db_instance: ["alpha"],
    )

    def _fake_get_document_version(db_instance, media_id, version_number=None, include_content=False):
        return {
            "content": "document body",
            "analysis_content": f"summary-{media_id}",
            "safe_metadata": {"published_at": "2024-01-01"},
        }

    monkeypatch.setattr(
        legacy_wrappers,
        "get_document_version",
        _fake_get_document_version,
    )

    item = items_endpoint._media_row_to_item(
        {
            "id": 7,
            "title": "Tagged item",
            "url": "https://example.com/story",
            "content": "",
            "type": "article",
        },
        db=object(),
        domain_filter=None,
    )
    assert item is not None
    assert item.summary == "summary-7"
    assert item.published_at == "2024-01-01"

    class StubMediaDb:
        def search_media_db(self, **kwargs):
            assert kwargs["media_ids_filter"] == [7]
            return (
                [
                    {
                        "id": 7,
                        "title": "Tagged item",
                        "url": "https://example.com/story",
                        "content": "",
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
    assert items_context[0]["summary"] == "summary-7"

    class StubDb:
        def get_media_by_id(self, media_id: int):
            return {"id": media_id, "content": "", "title": "Doc"}

    content_payload = await media_embeddings.get_media_content(7, StubDb())
    assert content_payload["media_item"]["content"] == "document body"

    monkeypatch.setattr(jobs_worker, "get_user_media_db_path", lambda user_id: "/tmp/fake.db")
    monkeypatch.setattr(jobs_worker, "create_media_database", lambda client_id, db_path: StubDb())

    jobs_payload = jobs_worker._load_media_content(7, "user-1")
    assert jobs_payload["media_item"]["content"] == "document body"


def test_media_module_imports_document_version_from_legacy_wrappers(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    media_module_impl = importlib.import_module(
        "tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError("media_module should not bind get_document_version from Media_DB_v2")

    monkeypatch.setattr(
        media_db_v2,
        "get_document_version",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(media_module_impl)
    assert reloaded.get_document_version is legacy_wrappers.get_document_version


def test_navigation_endpoint_imports_document_version_from_legacy_wrappers(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    navigation_endpoint = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media.navigation"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError("navigation should not bind get_document_version from Media_DB_v2")

    monkeypatch.setattr(
        media_db_v2,
        "get_document_version",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(navigation_endpoint)
    assert reloaded.get_document_version is legacy_wrappers.get_document_version


def test_versions_endpoint_imports_document_version_from_legacy_wrappers(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    versions_endpoint = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media.versions"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError("versions endpoint should not bind get_document_version from Media_DB_v2")

    monkeypatch.setattr(
        media_db_v2,
        "get_document_version",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(versions_endpoint)
    assert reloaded.get_document_version is legacy_wrappers.get_document_version
