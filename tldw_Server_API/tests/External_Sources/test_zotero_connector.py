from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from tldw_Server_API.app.core.External_Sources.zotero import ZoteroConnector
from tldw_Server_API.app.core.External_Sources.reference_manager_types import (
    ReferenceAttachmentCandidate,
)


class _Resp:
    def __init__(self, payload, headers: dict[str, str] | None = None, content: bytes | None = None):
        self._payload = payload
        self.headers = headers or {}
        self.content = content or b""

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None

    async def aclose(self):
        return None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_zotero_collection_browsing_returns_collection_records_not_file_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        {
            "key": "COLL1234",
            "version": 7,
            "data": {
                "key": "COLL1234",
                "name": "Language Models",
                "parentCollection": False,
            },
            "links": {
                "alternate": {
                    "href": "https://www.zotero.org/users/123456/collections/COLL1234",
                }
            },
        }
    ]

    async def _fake_afetch(*, method, url, headers=None, params=None, timeout=None):
        assert method == "GET"
        assert url == "https://api.zotero.org/users/123456/collections"
        assert headers["Zotero-API-Version"] == "3"
        assert headers["Zotero-API-Key"] == "api-key"
        assert params == {"format": "json", "limit": 25, "start": 0}
        return _Resp(payload)

    import tldw_Server_API.app.core.External_Sources.zotero as zotero_mod

    monkeypatch.setattr(zotero_mod, "afetch", _fake_afetch)

    connector = ZoteroConnector(client_id="client-id", client_secret="client-secret", redirect_base="http://localhost")
    collections, next_cursor = await connector.list_collections(
        {
            "provider": "zotero",
            "provider_user_id": "123456",
            "tokens": {"access_token": "api-key"},
        },
        cursor=None,
        page_size=25,
    )

    assert next_cursor is None
    assert len(collections) == 1
    assert collections[0].provider == "zotero"
    assert collections[0].collection_key == "COLL1234"
    assert collections[0].collection_name == "Language Models"
    assert collections[0].source_url == "https://www.zotero.org/users/123456/collections/COLL1234"
    assert "mime_type" not in collections[0].metadata


@pytest.mark.asyncio
@pytest.mark.unit
async def test_zotero_collection_item_listing_is_flat_for_selected_collection_in_v1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        {
            "key": "ITEM1234",
            "version": 11,
            "data": {
                "key": "ITEM1234",
                "itemType": "journalArticle",
                "title": "Attention Is All You Need",
                "DOI": "10.1000/example",
                "date": "2017-06-12",
                "publicationTitle": "NeurIPS",
                "abstractNote": "Transformers.",
                "collections": ["COLL1234"],
                "creators": [
                    {"creatorType": "author", "firstName": "Ashish", "lastName": "Vaswani"},
                    {"creatorType": "author", "firstName": "Noam", "lastName": "Shazeer"},
                ],
            },
            "links": {
                "alternate": {
                    "href": "https://www.zotero.org/users/123456/items/ITEM1234",
                }
            },
        },
        {
            "key": "ATTACH5678",
            "version": 12,
            "data": {
                "key": "ATTACH5678",
                "itemType": "attachment",
                "parentItem": "ITEM1234",
                "title": "Attention Is All You Need.pdf",
                "linkMode": "imported_file",
                "contentType": "application/pdf",
            },
        },
    ]

    async def _fake_afetch(*, method, url, headers=None, params=None, timeout=None):
        assert method == "GET"
        assert url == "https://api.zotero.org/users/123456/collections/COLL1234/items/top"
        assert headers["Zotero-API-Key"] == "api-key"
        assert params == {"format": "json", "limit": 50, "start": 0}
        return _Resp(payload)

    import tldw_Server_API.app.core.External_Sources.zotero as zotero_mod

    monkeypatch.setattr(zotero_mod, "afetch", _fake_afetch)

    connector = ZoteroConnector(client_id="client-id", client_secret="client-secret", redirect_base="http://localhost")
    items, next_cursor = await connector.list_collection_items(
        {
            "provider": "zotero",
            "provider_user_id": "123456",
            "tokens": {"access_token": "api-key"},
        },
        "COLL1234",
        collection_name="Language Models",
        cursor=None,
        page_size=50,
    )

    assert next_cursor is None
    assert [item.provider_item_key for item in items] == ["ITEM1234"]
    assert items[0].provider == "zotero"
    assert items[0].provider_library_id == "123456"
    assert items[0].collection_key == "COLL1234"
    assert items[0].collection_name == "Language Models"
    assert items[0].doi == "10.1000/example"
    assert items[0].title == "Attention Is All You Need"
    assert items[0].authors == "Ashish Vaswani, Noam Shazeer"
    assert items[0].attachments == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_zotero_normalize_reference_item_prefers_importable_pdf_attachments_and_metadata_only_fallback() -> None:
    connector = ZoteroConnector(client_id="client-id", client_secret="client-secret", redirect_base="http://localhost")
    raw_item = {
        "key": "ITEM1234",
        "version": 11,
        "data": {
            "key": "ITEM1234",
            "itemType": "journalArticle",
            "title": "Attention Is All You Need",
            "DOI": "10.1000/example",
            "date": "2017-06-12",
            "publicationTitle": "NeurIPS",
            "abstractNote": "Transformers.",
            "collections": ["COLL1234"],
            "creators": [
                {"creatorType": "author", "firstName": "Ashish", "lastName": "Vaswani"},
                {"creatorType": "author", "firstName": "Noam", "lastName": "Shazeer"},
            ],
        },
        "meta": {
            "creatorSummary": "Ashish Vaswani and Noam Shazeer",
        },
        "links": {
            "alternate": {
                "href": "https://www.zotero.org/users/123456/items/ITEM1234",
            }
        },
    }
    raw_attachments = [
        {
            "key": "ATTACH9999",
            "data": {
                "key": "ATTACH9999",
                "itemType": "attachment",
                "title": "Landing Page",
                "parentItem": "ITEM1234",
                "linkMode": "linked_url",
                "contentType": "text/html",
                "url": "https://example.com/article",
            },
        },
        {
            "key": "ATTACH5678",
            "links": {
                "alternate": {
                    "href": "https://www.zotero.org/users/123456/items/ATTACH5678",
                }
            },
            "data": {
                "key": "ATTACH5678",
                "itemType": "attachment",
                "title": "Attention Is All You Need.pdf",
                "parentItem": "ITEM1234",
                "linkMode": "imported_file",
                "contentType": "application/pdf",
                "filename": "attention.pdf",
            },
        },
    ]

    item = await connector.normalize_reference_item(raw_item, raw_attachments)
    metadata_only_item = await connector.normalize_reference_item(raw_item, [])

    assert item.provider == "zotero"
    assert item.collection_key == "COLL1234"
    assert item.attachments[0].attachment_key == "ATTACH5678"
    assert item.attachments[0].mime_type == "application/pdf"
    assert item.attachments[0].title == "Attention Is All You Need.pdf"
    assert metadata_only_item.provider_item_key == "ITEM1234"
    assert metadata_only_item.attachments == []
    assert metadata_only_item.title == "Attention Is All You Need"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_zotero_normalize_reference_item_extracts_year_from_free_form_dates() -> None:
    connector = ZoteroConnector(client_id="client-id", client_secret="client-secret", redirect_base="http://localhost")
    raw_item = {
        "key": "ITEM5678",
        "data": {
            "key": "ITEM5678",
            "itemType": "journalArticle",
            "title": "Scaling Laws for Neural Language Models",
            "date": "May 2017",
            "creators": [
                {"creatorType": "author", "firstName": "Jared", "lastName": "Kaplan"},
            ],
        },
    }

    item = await connector.normalize_reference_item(raw_item, [])

    assert item.publication_date == "May 2017"
    assert item.year == "2017"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_zotero_normalize_reference_item_ignores_invalid_doi() -> None:
    connector = ZoteroConnector(client_id="client-id", client_secret="client-secret", redirect_base="http://localhost")
    raw_item = {
        "key": "ITEM-BAD-DOI",
        "data": {
            "key": "ITEM-BAD-DOI",
            "itemType": "journalArticle",
            "title": "Paper With Malformed DOI",
            "DOI": "definitely-not-a-doi",
            "date": "2024",
        },
    }

    item = await connector.normalize_reference_item(raw_item, [])

    assert item.provider_item_key == "ITEM-BAD-DOI"
    assert item.title == "Paper With Malformed DOI"
    assert item.doi is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_zotero_exchange_code_parses_access_token_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_afetch(*, method, url, headers=None, params=None, timeout=None, data=None):
        assert method == "POST"
        assert url == "https://www.zotero.org/oauth/access"
        assert params is None
        assert timeout == 30
        assert headers["Authorization"].startswith("OAuth ")
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        return _Resp(
            None,
            content=b"oauth_token=request-token&oauth_token_secret=api-key-123&userID=123456&username=testuser",
        )

    import tldw_Server_API.app.core.External_Sources.zotero as zotero_mod

    monkeypatch.setattr(zotero_mod, "afetch", _fake_afetch)

    connector = ZoteroConnector(client_id="client-id", client_secret="client-secret", redirect_base="http://localhost")
    result = await connector.exchange_code(
        json.dumps(
            {
                "oauth_token": "request-token",
                "oauth_token_secret": "temporary-secret",
                "oauth_verifier": "verifier-123",
            }
        ),
        "http://localhost/api/v1/connectors/providers/zotero/callback",
    )

    assert result["provider"] == "zotero"
    assert result["access_token"] == "api-key-123"
    assert result["provider_user_id"] == "123456"
    assert result["username"] == "testuser"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_zotero_resolve_attachment_download_uses_attachment_file_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_afetch(*, method, url, headers=None, params=None, timeout=None, **kwargs):
        assert method == "GET"
        assert url == "https://api.zotero.org/users/123456/items/ATTACH5678/file"
        assert headers["Zotero-API-Key"] == "api-key"
        assert headers["Zotero-API-Version"] == "3"
        assert params is None
        assert timeout == 60
        assert kwargs == {}
        return _Resp(None, content=b"%PDF-1.7 test payload")

    import tldw_Server_API.app.core.External_Sources.zotero as zotero_mod

    monkeypatch.setattr(zotero_mod, "afetch", _fake_afetch)

    connector = ZoteroConnector(client_id="client-id", client_secret="client-secret", redirect_base="http://localhost")
    payload = await connector.resolve_attachment_download(
        {
            "provider": "zotero",
            "provider_user_id": "123456",
            "tokens": {"access_token": "api-key"},
        },
        ReferenceAttachmentCandidate(
            provider="zotero",
            provider_item_key="ITEM1234",
            attachment_key="ATTACH5678",
            title="Attention Is All You Need.pdf",
            mime_type="application/pdf",
        ),
    )

    assert payload == b"%PDF-1.7 test payload"


@pytest.mark.unit
def test_zotero_authorize_url_requires_request_token_and_builds_authorize_url() -> None:
    connector = ZoteroConnector(client_id="client-id", client_secret="client-secret", redirect_base="http://localhost")

    with pytest.raises(ValueError, match="oauth_token"):
        connector.authorize_url(state="state-123", scopes=None)

    auth_url = connector.authorize_url(
        state="state-123",
        scopes=["oauth_token=request-token-123", "notes_access=0"],
    )
    parsed = urlparse(auth_url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.zotero.org"
    assert parsed.path == "/oauth/authorize"
    assert params["oauth_token"] == ["request-token-123"]
    assert params["state"] == ["state-123"]
