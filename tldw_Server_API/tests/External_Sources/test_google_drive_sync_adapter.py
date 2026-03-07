from __future__ import annotations

import pytest

from tldw_Server_API.app.core.External_Sources.google_drive import GoogleDriveConnector


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload
        self.content = b""

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None

    async def aclose(self):
        return None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_drive_changes_list_returns_normalized_page_token(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "changes": [
            {
                "fileId": "file-1",
                "time": "2026-03-01T00:00:00Z",
                "file": {
                    "id": "file-1",
                    "name": "report.pdf",
                    "mimeType": "application/pdf",
                    "modifiedTime": "2026-03-01T00:00:00Z",
                    "md5Checksum": "md5-1",
                    "size": "42",
                    "parents": ["folder-1"],
                    "version": "7",
                    "webViewLink": "https://drive.google.com/file/d/file-1/view",
                    "trashed": False,
                },
            },
            {
                "fileId": "file-2",
                "removed": True,
                "time": "2026-03-01T01:00:00Z",
            },
        ],
        "nextPageToken": "page-2",
        "newStartPageToken": "new-start-token",
    }

    async def _fake_afetch(*, method, url, headers=None, params=None, timeout=None):
        assert method == "GET"
        assert url.endswith("/drive/v3/changes")
        assert params["pageToken"] == "start-token"
        return _Resp(payload)

    import tldw_Server_API.app.core.External_Sources.google_drive as drive_mod

    monkeypatch.setattr(drive_mod, "afetch", _fake_afetch)

    connector = GoogleDriveConnector(client_id="x", client_secret="y", redirect_base="http://localhost")
    changes, next_cursor, cursor_hint = await connector.list_changes(
        {"tokens": {"access_token": "token"}},
        cursor="start-token",
    )

    assert changes[0].remote_id == "file-1"
    assert changes[0].event_type == "content_updated"
    assert changes[0].remote_name == "report.pdf"
    assert changes[1].remote_id == "file-2"
    assert changes[1].event_type == "deleted"
    assert next_cursor == "page-2"
    assert cursor_hint == "new-start-token"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_drive_resolve_shared_link_returns_canonical_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = GoogleDriveConnector(client_id="x", client_secret="y", redirect_base="http://localhost")

    async def _fake_get_item_metadata(account, remote_id):
        assert remote_id == "file-123"
        return {
            "remote_id": remote_id,
            "remote_name": "shared.pdf",
            "mime_type": "application/pdf",
        }

    monkeypatch.setattr(connector, "get_item_metadata", _fake_get_item_metadata)

    resolved = await connector.resolve_shared_link(
        {"tokens": {"access_token": "token"}},
        "https://drive.google.com/file/d/file-123/view?usp=sharing",
    )

    assert resolved is not None
    assert resolved["remote_id"] == "file-123"
    assert resolved["remote_name"] == "shared.pdf"
