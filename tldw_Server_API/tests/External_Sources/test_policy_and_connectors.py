import asyncio
import os
import types
import pytest


@pytest.mark.unit
def test_policy_is_file_type_allowed_cases():
    from tldw_Server_API.app.core.External_Sources.policy import is_file_type_allowed

    # Empty allowlist allows all
    assert is_file_type_allowed(name="doc.pdf", mime="application/pdf", allowed=None) is True
    # Extension
    assert is_file_type_allowed(name="notes.md", mime="text/markdown", allowed=["md"]) is True
    assert is_file_type_allowed(name="notes.txt", mime="text/plain", allowed=["md"]) is False
    # Dot extension
    assert is_file_type_allowed(name="a.txt", mime="text/plain", allowed=[".txt"]) is True
    # Full mime
    assert is_file_type_allowed(name="a.bin", mime="application/pdf", allowed=["application/pdf"]) is True
    # Mime prefix
    assert is_file_type_allowed(name="a.txt", mime="text/plain", allowed=["text/"]) is True
    assert is_file_type_allowed(name="a.bin", mime="application/octet-stream", allowed=["text/"]) is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_notion_download_renders_nested_blocks(monkeypatch):
    from tldw_Server_API.app.core.External_Sources.notion import NotionConnector

    # Fake aiohttp session/response for Notion blocks children
    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status = 200

        async def json(self):
            return self._payload

        def raise_for_status(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _Session:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None, params=None, timeout=None):
            # Return a single page of blocks containing nested items
            # Construct a minimal realistic Notion blocks payload
            page_blocks = {
                "results": [
                    {"object": "block", "id": "h1", "type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title"}]}},
                    {"object": "block", "id": "li1", "type": "bulleted_list_item", "has_children": True,
                     "bulleted_list_item": {"rich_text": [{"plain_text": "Item"}]}},
                    {"object": "block", "id": "tbl1", "type": "table", "has_children": True, "table": {"table_width": 2}},
                ],
                "has_more": False,
                "next_cursor": None,
            }
            # Children for list item and table rows
            if url.endswith("/blocks/li1/children"):
                # One code child
                payload = {"results": [{"object": "block", "id": "c1", "type": "code", "code": {"language": "python", "rich_text": [{"plain_text": "print('x')"}]}}], "has_more": False, "next_cursor": None}
            elif url.endswith("/blocks/tbl1/children"):
                # First row is header, second is value
                payload = {
                    "results": [
                        {"object": "block", "type": "table_row", "table_row": {"cells": [[{"plain_text": "H1"}], [{"plain_text": "H2"}]]}},
                        {"object": "block", "type": "table_row", "table_row": {"cells": [[{"plain_text": "V1"}], [{"plain_text": "V2"}]]}},
                    ],
                    "has_more": False,
                    "next_cursor": None,
                }
            else:
                payload = page_blocks
            return _Resp(payload)

    # Patch aiohttp in module
    import tldw_Server_API.app.core.External_Sources.notion as notion_mod
    monkeypatch.setattr(notion_mod, "aiohttp", types.SimpleNamespace(ClientSession=_Session))

    nc = NotionConnector(client_id="x", client_secret="y", redirect_base="http://localhost")
    md_bytes = await nc.download_file({"tokens": {"access_token": "tok"}}, file_id="page123")
    out = md_bytes.decode("utf-8")

    # Heading
    assert "# Title" in out
    # Bullet + code block
    assert "- Item" in out
    assert "```python" in out and "print('x')" in out
    # Table header row and separator
    assert "| H1 | H2 |" in out
    assert "| --- | --- |" in out
    # Table body
    assert "| V1 | V2 |" in out


@pytest.mark.asyncio
@pytest.mark.unit
async def test_worker_drive_recursive_traversal(monkeypatch):
    # Arrange worker and patch dependencies to avoid real DB/network
    import tldw_Server_API.app.services.connectors_worker as worker

    class FakeJM:
        def __init__(self):
            self.completed = None
            self.renewed = []

        def renew_job_lease(self, *a, **kw):
            self.renewed.append((a, kw))

        def complete_job(self, jid, result=None, worker_id=None, lease_id=None, completion_token=None):
            self.completed = {"jid": jid, "result": result}

    # Fake connector that returns a folder structure:
    # root -> [folder F, doc A]; F -> [doc B]
    class FakeDriveConn:
        name = "drive"
        def authorize_url(self, *a, **kw):
            return ""
        async def exchange_code(self, *a, **kw):
            return {}
        async def list_files(self, account, parent_remote_id, *, page_size=50, cursor=None):
            if parent_remote_id in ("root", "r1"):
                return ([{"id": "F", "name": "Folder", "mimeType": "application/vnd.google-apps.folder", "is_folder": True},
                         {"id": "A", "name": "DocA.txt", "mimeType": "text/plain", "size": 10}], None)
            if parent_remote_id == "F":
                return ([{"id": "B", "name": "DocB.txt", "mimeType": "text/plain", "size": 12}], None)
            return ([], None)
        async def download_file(self, account, file_id, *, mime_type=None, export_mime=None):
            return f"content-{file_id}".encode()

    # Patch connector lookup on the package that worker imports from
    import tldw_Server_API.app.core.External_Sources as ext_pkg
    monkeypatch.setattr(ext_pkg, "get_connector_by_name", lambda name: FakeDriveConn())

    # Patch DB-related functions referenced inside worker module
    async def _fake_get_source_by_id(db, user_id, source_id):
        return {"id": source_id, "provider": "drive", "account_id": 123, "remote_id": "r1", "type": "folder", "path": "/", "options": {"recursive": True}}

    async def _fake_get_account_tokens(db, user_id, account_id):
        return {"access_token": "tok"}

    async def _fake_should_ingest_item(db, **kwargs):
        return True

    async def _fake_record_ingested_item(db, **kwargs):
        return None

    import tldw_Server_API.app.core.External_Sources.connectors_service as svc
    monkeypatch.setattr(svc, "get_source_by_id", _fake_get_source_by_id)
    monkeypatch.setattr(svc, "get_account_tokens", _fake_get_account_tokens)
    monkeypatch.setattr(svc, "should_ingest_item", _fake_should_ingest_item)
    monkeypatch.setattr(svc, "record_ingested_item", _fake_record_ingested_item)

    # Patch DB pool transaction context manager to yield a dummy object
    class _DummyTx:
        async def __aenter__(self):
            return object()
        async def __aexit__(self, exc_type, exc, tb):
            return False
    class _DummyPool:
        def transaction(self):
            return _DummyTx()
    async def _fake_get_db_pool():
        return _DummyPool()
    import tldw_Server_API.app.core.AuthNZ.database as dbmod
    monkeypatch.setattr(dbmod, "get_db_pool", _fake_get_db_pool)

    # Avoid org membership DB access by returning empty list
    import tldw_Server_API.app.core.AuthNZ.orgs_teams as orgs
    async def _fake_list_memberships_for_user(user_id: int):
        return []
    monkeypatch.setattr(orgs, "list_memberships_for_user", _fake_list_memberships_for_user)

    # Patch Media DB write
    class _FakeMDB:
        def __init__(self, *a, **kw):
            self.records = []
        def add_media_with_keywords(self, *, url, title, media_type, content, keywords, overwrite=False):
            self.records.append((url, title, content))
            return 1, "uuid", "ok"
    import tldw_Server_API.app.core.DB_Management.Media_DB_v2 as mdb_mod
    monkeypatch.setattr(mdb_mod, "MediaDatabase", _FakeMDB)

    # Policy defaults in env (allow txt)
    os.environ.setdefault("ORG_CONNECTORS_ALLOWED_EXPORT_FORMATS", "md,txt,pdf")

    jm = FakeJM()
    # Act
    await worker._process_import_job(jm, jid=1, lease_id="L", worker_id="W", source_id=99, user_id=42)

    # Assert: processed 2 documents (A, B), total includes folder + docs (3)
    assert jm.completed is not None
    res = jm.completed["result"]
    assert res["processed"] == 2
    assert res["total"] == 3
