from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from tldw_Server_API.app.core.http_client import afetch

from .connector_base import BaseConnector
from .sync_adapter import FileSyncChange


class GoogleDriveConnector(BaseConnector):
    name = "drive"
    _DRIVE_FILE_LINK_RE = re.compile(r"/file/d/([^/]+)")

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, redirect_base: str | None = None):
        super().__init__(
            client_id=client_id or os.getenv("CONNECTOR_DRIVE_CLIENT_ID"),
            client_secret=client_secret or os.getenv("CONNECTOR_DRIVE_CLIENT_SECRET"),
            redirect_base=redirect_base or os.getenv("CONNECTOR_REDIRECT_BASE_URL"),
        )

    def authorize_url(self, state: str | None = None, scopes: list[str] | None = None, redirect_path: str = "/api/v1/connectors/providers/drive/callback") -> str:
        # Scaffold: generate a Google OAuth URL if client_id is provided; otherwise return placeholder
        redirect_uri = f"{self.redirect_base}{redirect_path}"
        if not self.client_id:
            return f"{redirect_uri}?scaffold=1&state={state or ''}"
        # Request email/profile scopes to enable domain policy enforcement
        scope = " ".join(scopes or [
            "https://www.googleapis.com/auth/drive.readonly",
            "openid",
            "email",
            "profile",
        ])
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        resp = await afetch(method="POST", url=token_url, data=data, timeout=30)
        try:
            resp.raise_for_status()
            tok = resp.json()
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        # We requested profile scopes; email may be fetched via userinfo endpoint in callback
        return {
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token"),
            "expires_in": tok.get("expires_in"),
            "token_type": tok.get("token_type"),
            "scope": tok.get("scope"),
            "provider": self.name,
            "display_name": "Google Drive Account",
            "email": None,
        }

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Exchange a refresh_token for a new access_token."""
        if not (self.client_id and self.client_secret and refresh_token):
            return None
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        resp = await afetch(method="POST", url=token_url, data=data, timeout=30)
        try:
            resp.raise_for_status()
            tok = resp.json()
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

    @staticmethod
    def _access_token_from_account(account: dict[str, Any]) -> str | None:
        return (account.get("tokens") or {}).get("access_token") or account.get("access_token")

    async def get_start_page_token(self, account: dict[str, Any]) -> str | None:
        token = self._access_token_from_account(account)
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}"}
        resp = await afetch(
            method="GET",
            url="https://www.googleapis.com/drive/v3/changes/startPageToken",
            headers=headers,
            params={"supportsAllDrives": True},
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        return data.get("startPageToken")

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
        page_token = cursor or await self.get_start_page_token(account)
        if not page_token:
            return [], None, None

        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "pageToken": page_token,
            "pageSize": max(1, min(int(page_size), 1000)),
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "fields": (
                "nextPageToken,newStartPageToken,"
                "changes(fileId,removed,time,file("
                "id,name,mimeType,modifiedTime,md5Checksum,size,parents,version,webViewLink,trashed))"
            ),
        }
        resp = await afetch(
            method="GET",
            url="https://www.googleapis.com/drive/v3/changes",
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
        for raw_change in data.get("changes") or []:
            if not isinstance(raw_change, dict):
                continue
            file_id = str(raw_change.get("fileId") or "").strip()
            file_data = raw_change.get("file") or {}
            if raw_change.get("removed") or not file_data or file_data.get("trashed"):
                if file_id:
                    changes.append(
                        FileSyncChange(
                            event_type="deleted",
                            remote_id=file_id,
                            metadata={"change_time": raw_change.get("time")},
                        )
                    )
                continue
            remote_id = str(file_data.get("id") or file_id).strip()
            if not remote_id:
                continue
            changes.append(
                FileSyncChange(
                    event_type="content_updated",
                    remote_id=remote_id,
                    remote_name=file_data.get("name"),
                    remote_parent_id=((file_data.get("parents") or [None])[0]),
                    remote_revision=str(file_data.get("version") or "") or None,
                    remote_hash=file_data.get("md5Checksum"),
                    metadata={
                        "mime_type": file_data.get("mimeType"),
                        "modified_time": file_data.get("modifiedTime"),
                        "size": int(file_data.get("size") or 0),
                        "parents": file_data.get("parents") or [],
                        "remote_url": file_data.get("webViewLink"),
                        "change_time": raw_change.get("time"),
                    },
                )
            )
        return changes, data.get("nextPageToken"), data.get("newStartPageToken")

    async def get_item_metadata(self, account: dict[str, Any], remote_id: str) -> dict[str, Any] | None:
        token = self._access_token_from_account(account)
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}"}
        resp = await afetch(
            method="GET",
            url=f"https://www.googleapis.com/drive/v3/files/{remote_id}",
            headers=headers,
            params={
                "fields": "id,name,mimeType,modifiedTime,md5Checksum,size,parents,version,webViewLink,trashed",
                "supportsAllDrives": True,
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
        resolved_id = str(data.get("id") or remote_id).strip()
        if not resolved_id:
            return None
        return {
            "remote_id": resolved_id,
            "remote_name": data.get("name"),
            "mime_type": data.get("mimeType"),
            "modified_time": data.get("modifiedTime"),
            "remote_hash": data.get("md5Checksum"),
            "size": int(data.get("size") or 0),
            "parents": data.get("parents") or [],
            "remote_revision": str(data.get("version") or "") or None,
            "remote_url": data.get("webViewLink"),
            "trashed": bool(data.get("trashed")),
        }

    async def resolve_shared_link(self, account: dict[str, Any], shared_link: str) -> dict[str, Any] | None:
        parsed = urlparse(shared_link)
        match = self._DRIVE_FILE_LINK_RE.search(parsed.path or "")
        if match:
            return await self.get_item_metadata(account, match.group(1))

        query_id = (parse_qs(parsed.query).get("id") or [None])[0]
        if query_id:
            return await self.get_item_metadata(account, str(query_id))
        return None

    async def list_files(self, account: dict[str, Any], parent_remote_id: str, *, page_size: int = 50, cursor: str | None = None):
        """List files/folders under a parent. Returns (items, next_cursor)."""
        token = self._access_token_from_account(account)
        if not token:
            return [], None
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "q": f"'{parent_remote_id}' in parents and trashed=false",
            "fields": "nextPageToken, files(id,name,mimeType,modifiedTime,md5Checksum,size,parents)",
            "pageSize": int(page_size),
            # Support shared drives and items from shared drives
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        if cursor:
            params["pageToken"] = cursor
        resp = await afetch(
            method="GET",
            url="https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params=params,
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json()
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        files = data.get("files", [])
        items = []
        for f in files:
            items.append({
                "id": f.get("id"),
                "name": f.get("name"),
                "mimeType": f.get("mimeType"),
                "modifiedTime": f.get("modifiedTime"),
                "md5Checksum": f.get("md5Checksum"),
                "size": int(f.get("size") or 0),
                "is_folder": str(f.get("mimeType") or "").startswith("application/vnd.google-apps.folder"),
            })
        return items, data.get("nextPageToken")

    async def download_file(self, account: dict[str, Any], file_id: str, *, mime_type: str | None = None, export_mime: str | None = None) -> bytes:
        token = self._access_token_from_account(account)
        if not token:
            return b""
        headers = {"Authorization": f"Bearer {token}"}
        # If mime_type is a Google Docs type, use export
        mt = (mime_type or "").lower()
        if mt.startswith("application/vnd.google-apps."):
            # Choose export format: allow caller override (export_mime). Defaults aim for text where possible, PDF for slides.
            default_export_map = {
                "application/vnd.google-apps.document": "text/plain",
                "application/vnd.google-apps.spreadsheet": "text/csv",
                # Export Slides to PDF so downstream can extract text via PDF pipeline
                "application/vnd.google-apps.presentation": "application/pdf",
            }
            exp = export_mime or default_export_map.get(mt, "text/plain")
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            resp = await afetch(
                method="GET",
                url=url,
                headers=headers,
                params={"mimeType": exp},
                timeout=60,
            )
            try:
                resp.raise_for_status()
                return resp.content
            finally:
                close = getattr(resp, "aclose", None)
                if callable(close):
                    await close()
        # Binary download for normal files
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
        resp = await afetch(
            method="GET",
            url=url,
            headers=headers,
            params={"alt": "media"},
            timeout=60,
        )
        try:
            resp.raise_for_status()
            return resp.content
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
