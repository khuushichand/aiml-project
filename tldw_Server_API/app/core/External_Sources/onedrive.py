from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse

from tldw_Server_API.app.core.http_client import afetch

from .connector_base import BaseConnector
from .sync_adapter import FileSyncChange, FileSyncWebhookSubscription


class OneDriveConnector(BaseConnector):
    name = "onedrive"
    _DEFAULT_WEBHOOK_LIFETIME_HOURS = 24

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, redirect_base: str | None = None):
        super().__init__(
            client_id=client_id or os.getenv("CONNECTOR_ONEDRIVE_CLIENT_ID"),
            client_secret=client_secret or os.getenv("CONNECTOR_ONEDRIVE_CLIENT_SECRET"),
            redirect_base=redirect_base or os.getenv("CONNECTOR_REDIRECT_BASE_URL"),
        )

    @staticmethod
    def _access_token_from_account(account: dict[str, Any]) -> str | None:
        return (account.get("tokens") or {}).get("access_token") or account.get("access_token")

    @classmethod
    def _default_expiration_datetime(cls) -> str:
        return (
            datetime.now(UTC) + timedelta(hours=cls._DEFAULT_WEBHOOK_LIFETIME_HOURS)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def authorize_url(
        self,
        state: str | None = None,
        scopes: list[str] | None = None,
        redirect_path: str = "/api/v1/connectors/providers/onedrive/callback",
    ) -> str:
        redirect_uri = f"{self.redirect_base}{redirect_path}"
        if not self.client_id:
            return f"{redirect_uri}?scaffold=1&state={state or ''}"
        scope = " ".join(scopes or ["Files.Read", "offline_access", "openid", "email", "profile"])
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": scope,
        }
        if state:
            params["state"] = state
        return f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        resp = await afetch(
            method="POST",
            url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        try:
            resp.raise_for_status()
            tok = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        return {
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token"),
            "expires_in": tok.get("expires_in"),
            "token_type": tok.get("token_type"),
            "scope": tok.get("scope"),
            "provider": self.name,
            "display_name": "OneDrive Account",
            "email": None,
        }

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any] | None:
        if not (self.client_id and self.client_secret and refresh_token):
            return None
        resp = await afetch(
            method="POST",
            url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        try:
            resp.raise_for_status()
            tok = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        return {
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token") or refresh_token,
            "expires_in": tok.get("expires_in"),
            "token_type": tok.get("token_type"),
            "scope": tok.get("scope"),
        }

    async def list_files(
        self,
        account: dict[str, Any],
        parent_remote_id: str,
        *,
        page_size: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        token = self._access_token_from_account(account)
        if not token:
            return [], None
        headers = {"Authorization": f"Bearer {token}"}
        url = cursor or (
            "https://graph.microsoft.com/v1.0/me/drive/root/children"
            if parent_remote_id in {"", "root"}
            else f"https://graph.microsoft.com/v1.0/me/drive/items/{parent_remote_id}/children"
        )
        params: dict[str, Any] | None = None if cursor else {
            "$top": max(1, min(int(page_size), 200)),
            "$select": "id,name,size,lastModifiedDateTime,webUrl,eTag,cTag,parentReference,file,folder",
        }
        resp = await afetch(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        items: list[dict[str, Any]] = []
        for item in data.get("value") or []:
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "size": int(item.get("size") or 0),
                    "modifiedTime": item.get("lastModifiedDateTime"),
                    "webUrl": item.get("webUrl"),
                    "is_folder": bool(item.get("folder")),
                    "mimeType": ((item.get("file") or {}).get("mimeType")),
                    "parentReference": item.get("parentReference") or {},
                }
            )
        return items, data.get("@odata.nextLink")

    async def list_changes(
        self,
        account: dict[str, Any],
        *,
        cursor: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[FileSyncChange], str | None, str | None]:
        token = self._access_token_from_account(account)
        if not token:
            return [], None, None
        headers = {"Authorization": f"Bearer {token}"}
        url = cursor or "https://graph.microsoft.com/v1.0/me/drive/root/delta"
        params: dict[str, Any] | None = None if cursor else {
            "$top": max(1, min(int(page_size), 200)),
            "$select": "id,name,size,eTag,cTag,lastModifiedDateTime,webUrl,parentReference,file,folder,deleted",
        }
        resp = await afetch(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        changes: list[FileSyncChange] = []
        for item in data.get("value") or []:
            if not isinstance(item, dict):
                continue
            remote_id = str(item.get("id") or "").strip()
            if not remote_id:
                continue
            parent_reference = item.get("parentReference") or {}
            if item.get("deleted"):
                changes.append(
                    FileSyncChange(
                        event_type="deleted",
                        remote_id=remote_id,
                        remote_name=item.get("name"),
                        remote_parent_id=parent_reference.get("id"),
                        metadata={
                            "drive_id": parent_reference.get("driveId"),
                            "remote_path": parent_reference.get("path"),
                        },
                    )
                )
                continue
            file_info = item.get("file") or {}
            hashes = file_info.get("hashes") or {}
            changes.append(
                FileSyncChange(
                    event_type="content_updated",
                    remote_id=remote_id,
                    remote_name=item.get("name"),
                    remote_parent_id=parent_reference.get("id"),
                    remote_path=parent_reference.get("path"),
                    remote_revision=item.get("eTag") or item.get("cTag"),
                    remote_hash=hashes.get("quickXorHash") or hashes.get("sha1Hash"),
                    metadata={
                        "drive_id": parent_reference.get("driveId"),
                        "mime_type": file_info.get("mimeType"),
                        "size": int(item.get("size") or 0),
                        "remote_url": item.get("webUrl"),
                        "last_modified": item.get("lastModifiedDateTime"),
                        "is_folder": bool(item.get("folder")),
                    },
                )
            )
        return changes, data.get("@odata.nextLink"), data.get("@odata.deltaLink")

    async def get_item_metadata(self, account: dict[str, Any], remote_id: str) -> dict[str, Any] | None:
        token = self._access_token_from_account(account)
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}"}
        quoted_remote_id = quote(remote_id, safe="")
        resp = await afetch(
            method="GET",
            url=f"https://graph.microsoft.com/v1.0/me/drive/items/{quoted_remote_id}",
            headers=headers,
            params={"$select": "id,name,size,eTag,cTag,lastModifiedDateTime,webUrl,parentReference,file,folder,deleted"},
            timeout=30,
        )
        try:
            resp.raise_for_status()
            item = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        resolved_id = str(item.get("id") or remote_id).strip()
        if not resolved_id:
            return None
        parent_reference = item.get("parentReference") or {}
        file_info = item.get("file") or {}
        hashes = file_info.get("hashes") or {}
        return {
            "remote_id": resolved_id,
            "remote_name": item.get("name"),
            "mime_type": file_info.get("mimeType"),
            "size": int(item.get("size") or 0),
            "remote_revision": item.get("eTag") or item.get("cTag"),
            "remote_hash": hashes.get("quickXorHash") or hashes.get("sha1Hash"),
            "remote_url": item.get("webUrl"),
            "remote_parent_id": parent_reference.get("id"),
            "remote_path": parent_reference.get("path"),
            "drive_id": parent_reference.get("driveId"),
            "last_modified": item.get("lastModifiedDateTime"),
            "deleted": bool(item.get("deleted")),
            "is_folder": bool(item.get("folder")),
        }

    async def download_file(self, account: dict[str, Any], file_id: str, **kwargs: Any) -> bytes:
        _ = kwargs
        token = self._access_token_from_account(account)
        if not token:
            return b""
        headers = {"Authorization": f"Bearer {token}"}
        quoted_file_id = quote(file_id, safe="")
        resp = await afetch(
            method="GET",
            url=f"https://graph.microsoft.com/v1.0/me/drive/items/{quoted_file_id}/content",
            headers=headers,
            timeout=60,
        )
        try:
            resp.raise_for_status()
            return resp.content
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()

    async def resolve_shared_link(self, account: dict[str, Any], shared_link: str) -> dict[str, Any] | None:
        parsed = urlparse(shared_link)
        query = parse_qs(parsed.query)
        remote_id = (query.get("id") or query.get("resid") or [None])[0]
        if not remote_id:
            return None
        return await self.get_item_metadata(account, str(remote_id))

    async def subscribe_webhook(
        self,
        account: dict[str, Any],
        *,
        resource: dict[str, Any],
        callback_url: str,
    ) -> FileSyncWebhookSubscription | None:
        token = self._access_token_from_account(account)
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        requested_expiration = str(resource.get("expirationDateTime") or "").strip() or self._default_expiration_datetime()
        resp = await afetch(
            method="POST",
            url="https://graph.microsoft.com/v1.0/subscriptions",
            headers=headers,
            json={
                "changeType": resource.get("change_type", "updated"),
                "notificationUrl": callback_url,
                "resource": resource.get("resource", "me/drive/root"),
                "expirationDateTime": requested_expiration,
                "clientState": resource.get("clientState"),
            },
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        metadata = dict(data or {})
        metadata.setdefault("expirationDateTime", requested_expiration)
        return FileSyncWebhookSubscription(
            subscription_id=data.get("id"),
            expires_at=data.get("expirationDateTime") or requested_expiration,
            metadata=metadata,
        )

    async def renew_webhook(
        self,
        account: dict[str, Any],
        *,
        subscription: FileSyncWebhookSubscription,
    ) -> FileSyncWebhookSubscription | None:
        token = self._access_token_from_account(account)
        if not token or not subscription.subscription_id:
            return None
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        requested_expiration = self._default_expiration_datetime()
        resp = await afetch(
            method="PATCH",
            url=f"https://graph.microsoft.com/v1.0/subscriptions/{subscription.subscription_id}",
            headers=headers,
            json={"expirationDateTime": requested_expiration},
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        metadata = dict(subscription.metadata or {})
        metadata.update(data or {})
        metadata["expirationDateTime"] = data.get("expirationDateTime") or requested_expiration
        return FileSyncWebhookSubscription(
            subscription_id=data.get("id", subscription.subscription_id),
            expires_at=data.get("expirationDateTime") or requested_expiration,
            metadata=metadata,
        )

    async def revoke_webhook(
        self,
        account: dict[str, Any],
        *,
        subscription: FileSyncWebhookSubscription,
    ) -> bool:
        token = self._access_token_from_account(account)
        if not token or not subscription.subscription_id:
            return False
        headers = {"Authorization": f"Bearer {token}"}
        resp = await afetch(
            method="DELETE",
            url=f"https://graph.microsoft.com/v1.0/subscriptions/{subscription.subscription_id}",
            headers=headers,
            timeout=30,
        )
        try:
            resp.raise_for_status()
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        return True
