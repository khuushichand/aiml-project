from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from .connector_base import BaseConnector
import aiohttp


class GoogleDriveConnector(BaseConnector):
    name = "drive"

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, redirect_base: Optional[str] = None):
        super().__init__(
            client_id=client_id or os.getenv("CONNECTOR_DRIVE_CLIENT_ID"),
            client_secret=client_secret or os.getenv("CONNECTOR_DRIVE_CLIENT_SECRET"),
            redirect_base=redirect_base or os.getenv("CONNECTOR_REDIRECT_BASE_URL"),
        )

    def authorize_url(self, state: Optional[str] = None, scopes: Optional[List[str]] = None, redirect_path: str = "/api/v1/connectors/providers/drive/callback") -> str:
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

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data, timeout=30) as resp:
                resp.raise_for_status()
                tok = await resp.json()
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

    async def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
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
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data, timeout=30) as resp:
                resp.raise_for_status()
                tok = await resp.json()
        return {
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token") or refresh_token,
            "expires_in": tok.get("expires_in"),
            "token_type": tok.get("token_type"),
            "scope": tok.get("scope"),
        }

    async def list_files(self, account: Dict[str, Any], parent_remote_id: str, *, page_size: int = 50, cursor: Optional[str] = None):
        """List files/folders under a parent. Returns (items, next_cursor)."""
        token = (account.get("tokens") or {}).get("access_token") or account.get("access_token")
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
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=params, timeout=30) as resp:
                resp.raise_for_status()
                data = await resp.json()
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

    async def download_file(self, account: Dict[str, Any], file_id: str, *, mime_type: Optional[str] = None, export_mime: Optional[str] = None) -> bytes:
        token = (account.get("tokens") or {}).get("access_token") or account.get("access_token")
        if not token:
            return b""
        headers = {"Authorization": f"Bearer {token}"}
        # If mime_type is a Google Docs type, use export
        mt = (mime_type or "").lower()
        async with aiohttp.ClientSession() as session:
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
                async with session.get(url, headers=headers, params={"mimeType": exp}, timeout=60) as resp:
                    resp.raise_for_status()
                    return await resp.read()
            # Binary download for normal files
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            async with session.get(url, headers=headers, params={"alt": "media"}, timeout=60) as resp:
                resp.raise_for_status()
                return await resp.read()
