from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class FileSyncChange:
    event_type: str
    remote_id: str
    remote_name: str | None = None
    remote_parent_id: str | None = None
    remote_path: str | None = None
    remote_revision: str | None = None
    remote_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FileSyncWebhookSubscription:
    subscription_id: str | None = None
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class FileSyncAdapter(Protocol):
    async def list_children(
        self,
        account: dict[str, Any],
        parent_remote_id: str,
        *,
        page_size: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]: ...

    async def list_changes(
        self,
        account: dict[str, Any],
        *,
        cursor: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[FileSyncChange], str | None, str | None]: ...

    async def get_item_metadata(
        self,
        account: dict[str, Any],
        remote_id: str,
    ) -> dict[str, Any] | None: ...

    async def download_or_export(
        self,
        account: dict[str, Any],
        remote_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> bytes: ...

    async def resolve_shared_link(
        self,
        account: dict[str, Any],
        shared_link: str,
    ) -> dict[str, Any] | None: ...

    async def subscribe_webhook(
        self,
        account: dict[str, Any],
        *,
        resource: dict[str, Any],
        callback_url: str,
    ) -> FileSyncWebhookSubscription | None: ...

    async def renew_webhook(
        self,
        account: dict[str, Any],
        *,
        subscription: FileSyncWebhookSubscription,
    ) -> FileSyncWebhookSubscription | None: ...

    async def revoke_webhook(
        self,
        account: dict[str, Any],
        *,
        subscription: FileSyncWebhookSubscription,
    ) -> bool: ...
