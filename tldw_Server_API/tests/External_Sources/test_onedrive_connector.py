from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tldw_Server_API.app.api.v1.schemas.connectors import ConnectorSourceCreateRequest
from tldw_Server_API.app.core.External_Sources.onedrive import OneDriveConnector
from tldw_Server_API.app.core.External_Sources.sync_adapter import FileSyncWebhookSubscription


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
async def test_onedrive_get_item_metadata_url_encodes_remote_id(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    async def _fake_afetch(*, method, url, headers=None, params=None, timeout=None):
        seen["method"] = method
        seen["url"] = url
        return _Resp(
            {
                "id": "item/../unsafe",
                "name": "unsafe.txt",
                "eTag": "etag-1",
                "file": {"mimeType": "text/plain"},
            }
        )

    import tldw_Server_API.app.core.External_Sources.onedrive as onedrive_mod

    monkeypatch.setattr(onedrive_mod, "afetch", _fake_afetch)

    connector = OneDriveConnector(client_id="x", client_secret="y", redirect_base="http://localhost")
    metadata = await connector.get_item_metadata(
        {"tokens": {"access_token": "token"}},
        "item/../unsafe",
    )

    assert seen["method"] == "GET"
    assert seen["url"].endswith("/v1.0/me/drive/items/item%2F..%2Funsafe")
    assert metadata is not None
    assert metadata["remote_id"] == "item/../unsafe"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_onedrive_subscribe_webhook_defaults_future_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def _fake_afetch(*, method, url, headers=None, json=None, timeout=None):
        seen["method"] = method
        seen["url"] = url
        seen["json"] = json
        return _Resp(
            {
                "id": "sub-1",
                "expirationDateTime": (json or {}).get("expirationDateTime"),
            }
        )

    import tldw_Server_API.app.core.External_Sources.onedrive as onedrive_mod

    monkeypatch.setattr(onedrive_mod, "afetch", _fake_afetch)

    connector = OneDriveConnector(client_id="x", client_secret="y", redirect_base="http://localhost")
    subscription = await connector.subscribe_webhook(
        {"tokens": {"access_token": "token"}},
        resource={
            "resource": "me/drive/root",
            "change_type": "updated",
            "clientState": "state-123",
        },
        callback_url="http://localhost/api/v1/connectors/providers/onedrive/webhook",
    )

    requested_expiration = str((seen.get("json") or {}).get("expirationDateTime") or "")
    requested_dt = datetime.fromisoformat(requested_expiration.replace("Z", "+00:00"))

    assert seen["method"] == "POST"
    assert seen["url"] == "https://graph.microsoft.com/v1.0/subscriptions"
    assert requested_expiration
    assert requested_dt > datetime.now(UTC)
    assert subscription is not None
    assert subscription.expires_at == requested_expiration


@pytest.mark.asyncio
@pytest.mark.unit
async def test_onedrive_renew_webhook_requests_new_future_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def _fake_afetch(*, method, url, headers=None, json=None, timeout=None):
        seen["method"] = method
        seen["url"] = url
        seen["json"] = json
        return _Resp(
            {
                "id": "sub-1",
                "expirationDateTime": (json or {}).get("expirationDateTime"),
            }
        )

    import tldw_Server_API.app.core.External_Sources.onedrive as onedrive_mod

    monkeypatch.setattr(onedrive_mod, "afetch", _fake_afetch)

    connector = OneDriveConnector(client_id="x", client_secret="y", redirect_base="http://localhost")
    renewed = await connector.renew_webhook(
        {"tokens": {"access_token": "token"}},
        subscription=FileSyncWebhookSubscription(
            subscription_id="sub-1",
            expires_at="2026-03-01T00:00:00Z",
            metadata={"expirationDateTime": "2026-03-01T00:00:00Z"},
        ),
    )

    requested_expiration = str((seen.get("json") or {}).get("expirationDateTime") or "")
    requested_dt = datetime.fromisoformat(requested_expiration.replace("Z", "+00:00"))

    assert seen["method"] == "PATCH"
    assert seen["url"] == "https://graph.microsoft.com/v1.0/subscriptions/sub-1"
    assert requested_expiration
    assert requested_expiration != "2026-03-01T00:00:00Z"
    assert requested_dt > datetime.now(UTC)
    assert renewed is not None
    assert renewed.expires_at == requested_expiration


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_providers_includes_onedrive() -> None:
    from tldw_Server_API.app.api.v1.endpoints import connectors as ep

    providers = await ep.list_providers()
    names = {item.name for item in providers}

    assert "onedrive" in names
