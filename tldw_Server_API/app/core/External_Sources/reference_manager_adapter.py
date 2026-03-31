from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .reference_manager_types import (
    NormalizedReferenceCollection,
    NormalizedReferenceItem,
    ReferenceAttachmentCandidate,
)


@runtime_checkable
class ReferenceManagerAdapter(Protocol):
    async def list_collections(
        self,
        account: dict[str, Any],
        *,
        cursor: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[NormalizedReferenceCollection], str | None]: ...

    async def list_collection_items(
        self,
        account: dict[str, Any],
        collection_key: str,
        *,
        cursor: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[NormalizedReferenceItem], str | None]: ...

    async def list_item_attachments(
        self,
        account: dict[str, Any],
        provider_item_key: str,
    ) -> list[ReferenceAttachmentCandidate]: ...

    async def resolve_attachment_download(
        self,
        account: dict[str, Any],
        attachment: ReferenceAttachmentCandidate,
    ) -> bytes: ...
