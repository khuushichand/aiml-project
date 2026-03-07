from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.schemas.connectors import ConnectorSourceCreateRequest
from tldw_Server_API.app.core.External_Sources.onedrive import OneDriveConnector


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
async def test_onedrive_delta_returns_drive_and_item_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "value": [
            {
                "id": "item-1",
                "name": "report.pdf",
                "size": 128,
                "eTag": "etag-1",
                "lastModifiedDateTime": "2026-03-01T00:00:00Z",
                "webUrl": "https://onedrive.example/item-1",
                "parentReference": {
                    "driveId": "drive-123",
                    "id": "parent-1",
                    "path": "/drive/root:/Reports",
                },
                "file": {"mimeType": "application/pdf", "hashes": {"quickXorHash": "hash-1"}},
            }
        ],
        "@odata.deltaLink": "https://graph.microsoft.com/delta-token",
    }

    async def _fake_afetch(*, method, url, headers=None, params=None, timeout=None):
        assert method == "GET"
        assert url == "https://graph.microsoft.com/v1.0/me/drive/root/delta"
        return _Resp(payload)

    import tldw_Server_API.app.core.External_Sources.onedrive as onedrive_mod

    monkeypatch.setattr(onedrive_mod, "afetch", _fake_afetch)

    connector = OneDriveConnector(client_id="x", client_secret="y", redirect_base="http://localhost")
    changes, next_cursor, delta_link = await connector.list_changes(
        account={"tokens": {"access_token": "token"}},
        cursor=None,
    )

    first = changes[0]
    assert first.remote_id == "item-1"
    assert first.metadata["drive_id"] == "drive-123"
    assert first.remote_parent_id == "parent-1"
    assert next_cursor is None
    assert delta_link == "https://graph.microsoft.com/delta-token"


@pytest.mark.unit
def test_connector_source_request_accepts_onedrive_file_sources() -> None:
    payload = ConnectorSourceCreateRequest(
        account_id=1,
        provider="onedrive",
        remote_id="item-1",
        type="file",
    )

    assert payload.provider == "onedrive"
    assert payload.type == "file"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_providers_includes_onedrive() -> None:
    from tldw_Server_API.app.api.v1.endpoints import connectors as ep

    providers = await ep.list_providers()
    names = {item.name for item in providers}

    assert "onedrive" in names
