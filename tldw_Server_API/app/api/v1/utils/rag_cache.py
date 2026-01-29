from __future__ import annotations

from typing import Iterable, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _collect_cache_namespaces(
    current_user: Optional[User],
    namespaces: Optional[Iterable[str]] = None,
) -> set[str]:
    collected: set[str] = {str(ns) for ns in (namespaces or []) if ns}
    if current_user:
        username = getattr(current_user, "username", None)
        if username:
            collected.add(str(username))
        user_id = getattr(current_user, "id", None)
        if user_id is not None and user_id != "":
            collected.add(str(user_id))
    return collected


async def delete_media_vectors(
    current_user: Optional[User],
    *,
    media_id: int,
    namespaces: Optional[Iterable[str]] = None,
) -> None:
    """Best-effort vector-store cleanup for a media item."""
    cache_namespaces = _collect_cache_namespaces(current_user, namespaces)
    if not cache_namespaces:
        cache_namespaces = {"0"}

    try:
        from tldw_Server_API.app.core.config import settings as _settings
        if not isinstance(_settings, dict):
            return
        rag_cfg = _settings.get("RAG", {}) or {}
        if not rag_cfg.get("vector_store_type"):
            return
    except Exception as exc:
        logger.debug("Vector cleanup skipped (settings error): {}", exc)
        return

    try:
        from tldw_Server_API.app.core.RAG.rag_service.vector_stores.factory import (
            create_from_settings_for_user,
        )
    except Exception as exc:
        logger.debug("Vector cleanup skipped (factory import error): {}", exc)
        return

    for namespace in cache_namespaces:
        try:
            user_id = str(namespace)
            adapter = create_from_settings_for_user(_settings, user_id)
            if adapter is None:
                continue
            if not getattr(adapter, "_initialized", False):
                await adapter.initialize()
            collection_name = f"user_{user_id}_media_embeddings"
            await adapter.delete_by_filter(collection_name, {"media_id": str(media_id)})
        except Exception as exc:
            logger.debug(
                "Vector cleanup skipped for user {} media {}: {}",
                namespace,
                media_id,
                exc,
            )


def invalidate_rag_caches(
    current_user: Optional[User],
    *,
    namespaces: Optional[Iterable[str]] = None,
    media_id: Optional[int] = None,
) -> None:
    """Best-effort RAG cache invalidation for content updates."""
    cache_namespaces = _collect_cache_namespaces(current_user, namespaces)

    try:
        from tldw_Server_API.app.core.RAG.rag_service.semantic_cache import (
            clear_shared_caches,
        )

        if cache_namespaces:
            for namespace in cache_namespaces:
                clear_shared_caches(namespace=namespace)
        else:
            clear_shared_caches(namespace=None)
    except Exception as exc:
        logger.debug("RAG cache invalidation skipped: {}", exc)

    if media_id is None:
        return

    try:
        from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import (
            invalidate_intra_doc_vectors,
        )

        invalidate_intra_doc_vectors(str(media_id))
    except Exception as exc:
        logger.debug("Agentic cache invalidation skipped: {}", exc)
