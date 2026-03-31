from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.connectors import ConnectorSourceCreateRequest, SyncOptions
from tldw_Server_API.app.core.External_Sources import connectors_service as svc
from tldw_Server_API.app.core.External_Sources.reference_manager_adapter import ReferenceManagerAdapter
from tldw_Server_API.app.core.External_Sources.reference_manager_types import (
    NormalizedReferenceCollection,
    NormalizedReferenceItem,
    ReferenceAttachmentCandidate,
)


class _ReferenceManagerStub:
    async def list_collections(self, account, *, cursor=None, page_size=100):  # pragma: no cover - contract stub
        return []

    async def list_collection_items(self, account, collection_key, *, cursor=None, page_size=100):  # pragma: no cover - contract stub
        return []

    async def list_item_attachments(self, account, provider_item_key):  # pragma: no cover - contract stub
        return []

    async def resolve_attachment_download(self, account, attachment):  # pragma: no cover - contract stub
        return b""


@pytest.fixture
async def sqlite_db(tmp_path: Path):
    db = await aiosqlite.connect(tmp_path / "reference_manager_contract.sqlite3")
    db.row_factory = aiosqlite.Row
    db._is_sqlite = True
    try:
        yield db
    finally:
        await db.close()


@pytest.mark.unit
def test_reference_manager_adapter_protocol_accepts_collection_item_attachment_and_download_methods() -> None:
    assert isinstance(_ReferenceManagerStub(), ReferenceManagerAdapter)


@pytest.mark.unit
def test_reference_manager_types_expose_canonical_v1_fields() -> None:
    collection = NormalizedReferenceCollection(
        provider="zotero",
        provider_library_id="123456",
        collection_key="COLL1234",
        collection_name="Language Models",
        source_url="https://www.zotero.org/users/123456/collections/COLL1234",
    )
    item = NormalizedReferenceItem(
        provider="zotero",
        provider_item_key="ABCD1234",
        provider_library_id="123456",
        collection_key="COLL1234",
        collection_name="Language Models",
        doi="10.1000/example",
        title="Attention Is All You Need",
        authors="Ashish Vaswani, Noam Shazeer",
        publication_date="2017-06-12",
        year="2017",
        journal="NeurIPS",
        abstract="...",
        source_url="https://www.zotero.org/users/123456/items/ABCD1234",
        attachments=[],
    )
    attachment = ReferenceAttachmentCandidate(
        provider="zotero",
        provider_item_key="ABCD1234",
        attachment_key="ATTACH5678",
        title="Supplemental PDF",
        source_url="https://www.zotero.org/users/123456/items/ATTACH5678",
    )

    assert collection.collection_name == "Language Models"
    assert collection.collection_key == "COLL1234"
    assert collection.import_mode == "reference_manager"
    assert item.collection_name == "Language Models"
    assert item.doi == "10.1000/example"
    assert item.import_mode == "reference_manager"
    assert item.provider_item_key == "ABCD1234"
    assert item.attachments == []
    assert attachment.attachment_key == "ATTACH5678"
    assert attachment.provider_item_key == "ABCD1234"


@pytest.mark.unit
def test_connector_source_request_accepts_zotero_collection_sources() -> None:
    payload = ConnectorSourceCreateRequest(
        account_id=1,
        provider="zotero",
        remote_id="COLL1234",
        type="collection",
        options={},
    )

    assert payload.provider == "zotero"
    assert payload.type == "collection"
    assert payload.options == {}


@pytest.mark.unit
def test_connector_source_request_rejects_invalid_provider_type_pairs() -> None:
    with pytest.raises(ValidationError, match="only supported for provider 'zotero'"):
        ConnectorSourceCreateRequest(
            account_id=1,
            provider="drive",
            remote_id="COLL1234",
            type="collection",
            options={},
        )

    with pytest.raises(ValidationError, match="Zotero sources must use type 'collection'"):
        ConnectorSourceCreateRequest(
            account_id=1,
            provider="zotero",
            remote_id="ABCD1234",
            type="folder",
            options={},
        )


@pytest.mark.unit
def test_connectors_service_recognizes_zotero_provider() -> None:
    assert svc.get_connector_by_name("zotero").name == "zotero"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reference_manager_sources_are_flat_by_default(sqlite_db: aiosqlite.Connection) -> None:
    account = await svc.create_account(
        sqlite_db,
        user_id=7,
        provider="zotero",
        display_name="Zotero",
        email="researcher@example.com",
        tokens={"access_token": "token"},
    )
    source = await svc.create_source(
        sqlite_db,
        account_id=account["id"],
        provider="zotero",
        remote_id="COLL1234",
        type_="collection",
        path=None,
        options={},
    )
    forced_recursive = await svc.create_source(
        sqlite_db,
        account_id=account["id"],
        provider="zotero",
        remote_id="COLL5678",
        type_="collection",
        path=None,
        options={"recursive": True},
    )

    assert source["type"] == "collection"
    assert source["options"]["recursive"] is False
    assert forced_recursive["options"]["recursive"] is False
    assert SyncOptions(recursive=True).recursive is True
