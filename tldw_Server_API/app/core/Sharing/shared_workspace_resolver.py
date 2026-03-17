"""Resolves split DB context for cross-user workspace access."""
from __future__ import annotations

from dataclasses import dataclass

from tldw_Server_API.app.core.AuthNZ.repos.shared_workspace_repo import SharedWorkspaceRepo
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


@dataclass
class SharedWorkspaceContext:
    """DB context for accessing a shared workspace."""
    share_id: int
    workspace_id: str
    owner_user_id: int
    accessor_user_id: int
    access_level: str
    allow_clone: bool
    source_chacha_db: CharactersRAGDB
    source_media_db: MediaDatabase
    conversation_chacha_db: CharactersRAGDB
    embedding_namespace: str  # Owner's user_id for ChromaDB lookups


class SharedWorkspaceDBResolver:
    """
    Validates a share record and returns a SharedWorkspaceContext
    with the correct split DB references.

    Source content: owner's DBs (read-only or gated by access level)
    Conversations: accessor's DBs (full write)
    Embeddings: owner's namespace
    """

    def __init__(self, repo: SharedWorkspaceRepo) -> None:
        self._repo = repo

    async def resolve(
        self,
        share_id: int,
        accessor_user_id: int,
        *,
        source_chacha_db: CharactersRAGDB,
        source_media_db: MediaDatabase,
        conversation_chacha_db: CharactersRAGDB,
    ) -> SharedWorkspaceContext:
        share = await self._repo.get_share(share_id)
        if not share:
            raise PermissionError(f"Share {share_id} not found")

        if share.get("is_revoked") or share.get("revoked_at"):
            raise PermissionError("This share has been revoked")

        owner_user_id = share["owner_user_id"]

        return SharedWorkspaceContext(
            share_id=share_id,
            workspace_id=share["workspace_id"],
            owner_user_id=owner_user_id,
            accessor_user_id=accessor_user_id,
            access_level=share["access_level"],
            allow_clone=share["allow_clone"],
            source_chacha_db=source_chacha_db,
            source_media_db=source_media_db,
            conversation_chacha_db=conversation_chacha_db,
            embedding_namespace=str(owner_user_id),
        )

    @staticmethod
    def check_write_permission(ctx: SharedWorkspaceContext, operation: str) -> None:
        """Raise PermissionError if the access level forbids the operation."""
        level = ctx.access_level
        if operation == "add_source" and level not in ("view_chat_add", "full_edit"):
            raise PermissionError(f"Access level '{level}' does not allow adding sources")
        if operation in ("edit_source", "delete_source", "edit_workspace") and level != "full_edit":
            raise PermissionError(f"Access level '{level}' does not allow {operation}")

    @staticmethod
    def can_clone(ctx: SharedWorkspaceContext) -> bool:
        return ctx.allow_clone
