from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ReferenceAttachmentCandidate:
    provider: str
    provider_item_key: str
    attachment_key: str
    title: str | None = None
    source_url: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedReferenceCollection:
    provider: str
    import_mode: str = "reference_manager"
    provider_library_id: str | None = None
    collection_key: str | None = None
    collection_name: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedReferenceItem:
    provider: str
    provider_item_key: str
    import_mode: str = "reference_manager"
    provider_library_id: str | None = None
    collection_key: str | None = None
    collection_name: str | None = None
    doi: str | None = None
    title: str | None = None
    authors: str | None = None
    publication_date: str | None = None
    year: str | None = None
    journal: str | None = None
    abstract: str | None = None
    source_url: str | None = None
    attachments: list[ReferenceAttachmentCandidate] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
