"""Shared sync entities/operations contracts used by client and API layers."""

from __future__ import annotations

from enum import Enum


class SyncEntity(str, Enum):
    """All entities that may appear in sync log responses."""

    MEDIA = "Media"
    KEYWORDS = "Keywords"
    MEDIA_KEYWORDS = "MediaKeywords"
    TRANSCRIPTS = "Transcripts"
    MEDIA_CHUNKS = "MediaChunks"
    UNVECTORIZED_MEDIA_CHUNKS = "UnvectorizedMediaChunks"
    DOCUMENT_VERSIONS = "DocumentVersions"


class SyncSendEntity(str, Enum):
    """Entities accepted by /sync/send."""

    MEDIA = SyncEntity.MEDIA.value
    KEYWORDS = SyncEntity.KEYWORDS.value
    MEDIA_KEYWORDS = SyncEntity.MEDIA_KEYWORDS.value


class SyncOperation(str, Enum):
    """Allowed sync operations."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LINK = "link"
    UNLINK = "unlink"


ALLOWED_SYNC_ENTITIES: frozenset[str] = frozenset(member.value for member in SyncEntity)
ALLOWED_SYNC_SEND_ENTITIES: frozenset[str] = frozenset(member.value for member in SyncSendEntity)
ALLOWED_SYNC_OPERATIONS: frozenset[str] = frozenset(member.value for member in SyncOperation)

