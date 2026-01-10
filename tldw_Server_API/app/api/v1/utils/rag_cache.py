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
