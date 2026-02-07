from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    name: str

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, redirect_base: str | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_base = (redirect_base or "http://localhost:8000").rstrip("/")

    @abstractmethod
    def authorize_url(self, state: str | None = None, scopes: list[str] | None = None, redirect_path: str = "/api/v1/connectors/callback") -> str:
        """Return provider-specific OAuth authorization URL."""
        raise NotImplementedError

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange authorization code for tokens and account info."""
        raise NotImplementedError

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh tokens. Default: not implemented in scaffold."""
        return {"access_token": None, "expires_in": None}

    async def list_sources(self, account: dict[str, Any], parent_remote_id: str | None = None) -> list[dict[str, Any]]:
        """List folders/pages/databases; scaffold returns empty list."""
        return []

    async def list_files(self, account: dict[str, Any], remote_id: str) -> list[dict[str, Any]]:
        """List files under a folder/page; scaffold returns empty list."""
        return []

    async def download_file(self, account: dict[str, Any], file_id: str) -> bytes:
        """Download file contents; scaffold returns empty bytes."""
        return b""
