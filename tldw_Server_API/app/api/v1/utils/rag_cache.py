from __future__ import annotations

from collections.abc import Iterable

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User

_RAG_CACHE_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


def _collect_cache_namespaces(
    current_user: User | None,
    namespaces: Iterable[str] | None = None,
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
    current_user: User | None,
    *,
    media_id: int,
    namespaces: Iterable[str] | None = None,
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
    except (ImportError, *_RAG_CACHE_NONCRITICAL_EXCEPTIONS) as exc:
        logger.debug("Vector cleanup skipped (settings error): {}", exc)
        return

    try:
        from tldw_Server_API.app.core.RAG.rag_service.vector_stores.factory import (
            create_from_settings_for_user,
        )
    except ImportError as exc:
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
        except _RAG_CACHE_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(
                "Vector cleanup skipped for user {} media {}: {}",
                namespace,
                media_id,
                exc,
            )


def invalidate_rag_caches(
    current_user: User | None,
    *,
    namespaces: Iterable[str] | None = None,
    media_id: int | None = None,
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
    except (ImportError, *_RAG_CACHE_NONCRITICAL_EXCEPTIONS) as exc:
        logger.debug("RAG cache invalidation skipped: {}", exc)

    if media_id is None:
        return

    try:
        from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import (
            invalidate_intra_doc_vectors,
        )

        invalidate_intra_doc_vectors(str(media_id))
    except (ImportError, *_RAG_CACHE_NONCRITICAL_EXCEPTIONS) as exc:
        logger.debug("Agentic cache invalidation skipped: {}", exc)
