from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseConnector(ABC):
    name: str

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, redirect_base: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_base = (redirect_base or "http://localhost:8000").rstrip("/")

    @abstractmethod
    def authorize_url(self, state: Optional[str] = None, scopes: Optional[List[str]] = None, redirect_path: str = "/api/v1/connectors/callback") -> str:
        """Return provider-specific OAuth authorization URL."""
        raise NotImplementedError

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens and account info."""
        raise NotImplementedError

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh tokens. Default: not implemented in scaffold."""
        return {"access_token": None, "expires_in": None}

    async def list_sources(self, account: Dict[str, Any], parent_remote_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List folders/pages/databases; scaffold returns empty list."""
        return []

    async def list_files(self, account: Dict[str, Any], remote_id: str) -> List[Dict[str, Any]]:
        """List files under a folder/page; scaffold returns empty list."""
        return []

    async def download_file(self, account: Dict[str, Any], file_id: str) -> bytes:
        """Download file contents; scaffold returns empty bytes."""
        return b""
