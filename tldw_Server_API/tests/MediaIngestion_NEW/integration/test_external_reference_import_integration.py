from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
import pytest

from tldw_Server_API.app.core.DB_Management.media_db.api import get_document_version
from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.External_Sources import connectors_service as svc
from tldw_Server_API.app.core.External_Sources.reference_manager_types import (
    NormalizedReferenceItem,
    ReferenceAttachmentCandidate,
)


pytestmark = pytest.mark.integration


class _FakeJM:
    def __init__(self) -> None:
        self.completed: dict[str, object] | None = None

    def renew_job_lease(self, *args, **kwargs):
        return None

    def complete_job(
        self,
        jid,
        result=None,
        worker_id=None,
        lease_id=None,
        completion_token=None,
    ) -> None:
        self.completed = {"jid": jid, "result": result}


class _SqlitePool:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    @asynccontextmanager
    async def transaction(self):
        yield self._db


class _FakeZoteroConnector:
    def __init__(
        self,
        *,
        pages: dict[str | None, tuple[list[NormalizedReferenceItem], str | None]],
        attachments: dict[str, list[ReferenceAttachmentCandidate]],
        downloads: dict[str, bytes],
    ) -> None:
        self._pages = pages
        self._attachments = attachments
        self._downloads = downloads
        self.list_collection_calls: list[str | None] = []
        self.list_item_attachment_calls: list[str] = []
        self.download_calls: list[str] = []

    async def list_collection_items(
        self,
        account,
        collection_key: str,
        *,
        cursor: str | None = None,
        page_size: int = 100,
    ):
        assert account["tokens"]["access_token"] == "tok"
        assert account["provider_user_id"] == "123456"
        assert collection_key == "COLL1234"
        assert page_size == 100
        self.list_collection_calls.append(cursor)
        return self._pages.get(cursor, ([], None))

    async def list_item_attachments(self, account, provider_item_key: str):
        assert account["tokens"]["access_token"] == "tok"
        self.list_item_attachment_calls.append(provider_item_key)
        return list(self._attachments.get(provider_item_key, []))

    async def download_file(self, account, file_id: str, **kwargs):
        assert account["tokens"]["access_token"] == "tok"
        self.download_calls.append(file_id)
        return self._downloads[file_id]


def _reference_item(
    *,
    provider_item_key: str,
    doi: str | None,
    title: str,
    authors: str,
    year: str,
    journal: str,
    abstract: str,
    provider_version: str,
) -> NormalizedReferenceItem:
    return NormalizedReferenceItem(
        provider="zotero",
        provider_item_key=provider_item_key,
        provider_library_id="123456",
        collection_key="COLL1234",
        collection_name="Language Models",
        doi=doi,
        title=title,
        authors=authors,
        publication_date=f"{year}-01-01",
        year=year,
        journal=journal,
        abstract=abstract,
        source_url=f"https://www.zotero.org/users/123456/items/{provider_item_key}",
        attachments=[],
        metadata={"provider_version": provider_version},
    )


def _attachment(*, provider_item_key: str, attachment_key: str) -> ReferenceAttachmentCandidate:
    return ReferenceAttachmentCandidate(
        provider="zotero",
        provider_item_key=provider_item_key,
        attachment_key=attachment_key,
        title=f"{provider_item_key}.pdf",
        source_url=f"https://www.zotero.org/users/123456/items/{attachment_key}",
        mime_type="application/pdf",
        size_bytes=128,
        metadata={"filename": f"{provider_item_key}.pdf"},
    )


@pytest.mark.asyncio
async def test_reference_manager_sync_imports_new_items_merges_duplicate_metadata_and_tracks_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    import tldw_Server_API.app.core.DB_Management.db_path_utils as db_paths_mod
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    import tldw_Server_API.app.services.connectors_worker as worker

    connectors_db = await aiosqlite.connect(tmp_path / "connectors.sqlite3")
    connectors_db.row_factory = aiosqlite.Row
    connectors_db._is_sqlite = True

    try:
        media_root = tmp_path / "user_dbs"
        monkeypatch.setenv("USER_DB_BASE_DIR", str(media_root))
        monkeypatch.setitem(db_paths_mod.settings, "USER_DB_BASE_DIR", str(media_root))
        media_db_path = db_paths_mod.DatabasePaths.get_media_db_path(1)

        fake_conn = _FakeZoteroConnector(
            pages={
                None: (
                    [
                        _reference_item(
                            provider_item_key="ITEM-NEW",
                            doi="10.1000/new",
                            title="Attention Is All You Need",
                            authors="Ashish Vaswani, Noam Shazeer",
                            year="2017",
                            journal="NeurIPS",
                            abstract="Transformer paper.",
                            provider_version="1",
                        ),
                        _reference_item(
                            provider_item_key="ITEM-DUP",
                            doi="10.2000/duplicate",
                            title="Provider Duplicate Title",
                            authors="Duplicate Author",
                            year="2024",
                            journal="Journal of Duplicates",
                            abstract="Duplicate metadata should enrich only missing fields.",
                            provider_version="4",
                        ),
                        _reference_item(
                            provider_item_key="ITEM-META",
                            doi="10.3000/metadata-only",
                            title="Metadata Only Entry",
                            authors="Metadata Author",
                            year="2025",
                            journal="Metadata Journal",
                            abstract="No attachment available.",
                            provider_version="2",
                        ),
                    ],
                    "cursor-1",
                ),
            },
            attachments={
                "ITEM-NEW": [_attachment(provider_item_key="ITEM-NEW", attachment_key="ATT-NEW")],
                "ITEM-DUP": [_attachment(provider_item_key="ITEM-DUP", attachment_key="ATT-DUP")],
                "ITEM-META": [],
            },
            downloads={
                "ATT-NEW": b"Imported attachment body",
                "ATT-DUP": b"Duplicate attachment body",
            },
        )

        pool = _SqlitePool(connectors_db)

        async def _fake_get_db_pool():
            return pool

        async def _fake_list_memberships_for_user(_user_id: int):
            return []

        monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)
        monkeypatch.setattr(orgs, "list_memberships_for_user", _fake_list_memberships_for_user)
        monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: fake_conn)
        async def _fake_convert_document_bytes_to_text(raw, name, effective_mime):
            return raw.decode("utf-8")

        monkeypatch.setattr(
            worker,
            "_convert_document_bytes_to_text",
            _fake_convert_document_bytes_to_text,
            raising=False,
        )

        account = await svc.create_account(
            connectors_db,
            user_id=1,
            provider="zotero",
            display_name="Zotero",
            email="researcher@example.com",
            tokens={
                "access_token": "tok",
                "provider_user_id": "123456",
                "username": "researcher",
            },
        )
        source = await svc.create_source(
            connectors_db,
            account_id=int(account["id"]),
            provider="zotero",
            remote_id="COLL1234",
            type_="collection",
            path=None,
            options={},
        )
        await svc.upsert_source_sync_state(
            connectors_db,
            source_id=int(source["id"]),
            sync_mode="poll",
        )

        media_db = MediaDatabase(db_path=str(media_db_path), client_id="1")
        existing_media_id, _, _ = media_db.add_media_with_keywords(
            url="seed://duplicate",
            title="Existing Local Title",
            media_type="document",
            content="Existing local content",
            keywords=[],
            safe_metadata=json.dumps(
                {
                    "doi": "10.2000/duplicate",
                    "title": "Existing Local Title",
                }
            ),
            overwrite=False,
        )

        jm = _FakeJM()
        await worker._process_import_job(
            jm,
            jid=9101,
            lease_id="lease-reference",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        imported_binding = await svc.get_reference_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="zotero",
            provider_item_key="ITEM-NEW",
        )
        duplicate_binding = await svc.get_reference_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="zotero",
            provider_item_key="ITEM-DUP",
        )
        metadata_only_binding = await svc.get_reference_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="zotero",
            provider_item_key="ITEM-META",
        )
        binding_health = await svc.get_source_binding_health(
            connectors_db,
            source_id=int(source["id"]),
        )
        sync_state = await svc.get_source_sync_state(
            connectors_db,
            source_id=int(source["id"]),
        )

        assert jm.completed is not None
        assert jm.completed["result"]["processed"] == 3
        assert jm.completed["result"]["imported"] == 1
        assert jm.completed["result"]["duplicates"] == 1
        assert jm.completed["result"]["metadata_only"] == 1
        assert fake_conn.list_collection_calls == [None]
        assert sync_state is not None
        assert sync_state["cursor"] == "cursor-1"

        assert imported_binding is not None
        assert imported_binding["media_id"] is not None
        assert imported_binding["dedupe_match_reason"] is None
        imported_version = get_document_version(
            media_db,
            media_id=int(imported_binding["media_id"]),
            version_number=1,
        )
        imported_safe_metadata = json.loads(imported_version["safe_metadata"])
        assert imported_version["content"] == "Imported attachment body"
        assert imported_safe_metadata == {
            "provider": "zotero",
            "import_mode": "reference_manager",
            "provider_item_key": "ITEM-NEW",
            "provider_library_id": "123456",
            "collection_key": "COLL1234",
            "collection_name": "Language Models",
            "source_url": "https://www.zotero.org/users/123456/items/ITEM-NEW",
            "doi": "10.1000/new",
            "title": "Attention Is All You Need",
            "authors": "Ashish Vaswani, Noam Shazeer",
            "publication_date": "2017-01-01",
            "year": "2017",
            "journal": "NeurIPS",
            "abstract": "Transformer paper.",
        }

        assert duplicate_binding is not None
        assert int(duplicate_binding["media_id"]) == int(existing_media_id)
        assert duplicate_binding["dedupe_match_reason"] == "doi"
        duplicate_version = get_document_version(
            media_db,
            media_id=int(existing_media_id),
            version_number=1,
        )
        duplicate_safe_metadata = json.loads(duplicate_version["safe_metadata"])
        duplicate_version_count = media_db.execute_query(
            "SELECT COUNT(*) AS c FROM DocumentVersions WHERE media_id = ? AND deleted = 0",
            (int(existing_media_id),),
        ).fetchone()["c"]
        assert duplicate_version["content"] == "Existing local content"
        assert duplicate_version_count == 1
        assert duplicate_safe_metadata["title"] == "Existing Local Title"
        assert duplicate_safe_metadata["authors"] == "Duplicate Author"
        assert duplicate_safe_metadata["journal"] == "Journal of Duplicates"
        assert duplicate_safe_metadata["year"] == "2024"

        assert metadata_only_binding is not None
        assert metadata_only_binding["media_id"] is None
        assert metadata_only_binding["dedupe_match_reason"] == "metadata_only"
        assert binding_health == {
            "tracked_item_count": 3,
            "degraded_item_count": 0,
            "duplicate_count": 1,
            "metadata_only_count": 1,
        }

        media_count = media_db.execute_query(
            "SELECT COUNT(*) AS c FROM Media WHERE deleted = 0",
            (),
        ).fetchone()["c"]
        assert media_count == 2
    finally:
        await connectors_db.close()


@pytest.mark.asyncio
async def test_reference_manager_repeat_sync_keeps_existing_media_non_destructive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    import tldw_Server_API.app.core.DB_Management.db_path_utils as db_paths_mod
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    import tldw_Server_API.app.services.connectors_worker as worker

    connectors_db = await aiosqlite.connect(tmp_path / "connectors.sqlite3")
    connectors_db.row_factory = aiosqlite.Row
    connectors_db._is_sqlite = True

    try:
        media_root = tmp_path / "user_dbs"
        monkeypatch.setenv("USER_DB_BASE_DIR", str(media_root))
        monkeypatch.setitem(db_paths_mod.settings, "USER_DB_BASE_DIR", str(media_root))
        media_db_path = db_paths_mod.DatabasePaths.get_media_db_path(1)

        fake_conn = _FakeZoteroConnector(
            pages={
                None: (
                    [
                        _reference_item(
                            provider_item_key="ITEM-NEW",
                            doi="10.5555/reference",
                            title="Original Imported Title",
                            authors="First Author",
                            year="2023",
                            journal="Original Journal",
                            abstract="Original abstract.",
                            provider_version="1",
                        ),
                    ],
                    "cursor-1",
                ),
                "cursor-1": (
                    [
                        _reference_item(
                            provider_item_key="ITEM-NEW",
                            doi="10.5555/reference",
                            title="Changed Upstream Title",
                            authors="Changed Author",
                            year="2024",
                            journal="Changed Journal",
                            abstract="Changed abstract.",
                            provider_version="2",
                        ),
                    ],
                    "cursor-2",
                ),
            },
            attachments={
                "ITEM-NEW": [_attachment(provider_item_key="ITEM-NEW", attachment_key="ATT-NEW")],
            },
            downloads={
                "ATT-NEW": b"Original imported body",
            },
        )

        pool = _SqlitePool(connectors_db)

        async def _fake_get_db_pool():
            return pool

        async def _fake_list_memberships_for_user(_user_id: int):
            return []

        monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)
        monkeypatch.setattr(orgs, "list_memberships_for_user", _fake_list_memberships_for_user)
        monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: fake_conn)
        async def _fake_convert_document_bytes_to_text(raw, name, effective_mime):
            return raw.decode("utf-8")

        monkeypatch.setattr(
            worker,
            "_convert_document_bytes_to_text",
            _fake_convert_document_bytes_to_text,
            raising=False,
        )

        account = await svc.create_account(
            connectors_db,
            user_id=1,
            provider="zotero",
            display_name="Zotero",
            email="researcher@example.com",
            tokens={
                "access_token": "tok",
                "provider_user_id": "123456",
                "username": "researcher",
            },
        )
        source = await svc.create_source(
            connectors_db,
            account_id=int(account["id"]),
            provider="zotero",
            remote_id="COLL1234",
            type_="collection",
            path=None,
            options={},
        )
        await svc.upsert_source_sync_state(
            connectors_db,
            source_id=int(source["id"]),
            sync_mode="poll",
        )

        first_jm = _FakeJM()
        await worker._process_import_job(
            first_jm,
            jid=9201,
            lease_id="lease-reference-1",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        first_binding = await svc.get_reference_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="zotero",
            provider_item_key="ITEM-NEW",
        )
        assert first_binding is not None
        media_id = int(first_binding["media_id"])

        second_jm = _FakeJM()
        await worker._process_import_job(
            second_jm,
            jid=9202,
            lease_id="lease-reference-2",
            worker_id="worker-1",
            source_id=int(source["id"]),
            user_id=1,
        )

        media_db = MediaDatabase(db_path=str(media_db_path), client_id="1")
        latest_version = get_document_version(media_db, media_id=media_id, version_number=1)
        version_count = media_db.execute_query(
            "SELECT COUNT(*) AS c FROM DocumentVersions WHERE media_id = ? AND deleted = 0",
            (media_id,),
        ).fetchone()["c"]
        final_binding = await svc.get_reference_item_binding(
            connectors_db,
            source_id=int(source["id"]),
            provider="zotero",
            provider_item_key="ITEM-NEW",
        )
        sync_state = await svc.get_source_sync_state(
            connectors_db,
            source_id=int(source["id"]),
        )

        assert first_jm.completed is not None
        assert first_jm.completed["result"]["imported"] == 1
        assert second_jm.completed is not None
        assert second_jm.completed["result"]["duplicates"] == 1
        assert version_count == 1
        assert latest_version["content"] == "Original imported body"
        assert json.loads(latest_version["safe_metadata"])["title"] == "Original Imported Title"
        assert final_binding is not None
        assert final_binding["provider_version"] == "2"
        assert final_binding["dedupe_match_reason"] == "same_provider_item"
        assert sync_state is not None
        assert sync_state["cursor"] == "cursor-2"
    finally:
        await connectors_db.close()
