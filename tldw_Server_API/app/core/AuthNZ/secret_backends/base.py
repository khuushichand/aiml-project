from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


class SecretBackend(ABC):
    """Capability-oriented interface for logical secret backends."""

    backend_name: str
    display_name: str
    capabilities: dict[str, bool]

    def __init__(self, *, db_pool: DatabasePool) -> None:
        self.db_pool = db_pool

    @abstractmethod
    async def ensure_tables(self) -> None:
        """Ensure backend metadata and backing storage are available."""

    @abstractmethod
    async def store_ref(
        self,
        *,
        owner_scope_type: str,
        owner_scope_id: int,
        provider_key: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        display_name: str | None = None,
        created_by: int | None = None,
        updated_by: int | None = None,
    ) -> dict[str, Any]:
        """Persist secret material and return the managed logical reference."""

    @abstractmethod
    async def resolve_for_use(self, secret_ref_id: int) -> dict[str, Any]:
        """Resolve a logical reference into short-lived execution material."""

    @abstractmethod
    async def rotate_if_supported(
        self,
        secret_ref_id: int,
        *,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        updated_by: int | None = None,
    ) -> dict[str, Any]:
        """Rotate or replace the stored material when the backend supports it."""

    @abstractmethod
    async def describe_status(self, secret_ref_id: int) -> dict[str, Any]:
        """Return the current availability/status of a logical reference."""

    @abstractmethod
    async def delete_ref(
        self,
        secret_ref_id: int,
        *,
        revoked_by: int | None = None,
    ) -> bool:
        """Revoke the logical reference and its backing secret material."""
