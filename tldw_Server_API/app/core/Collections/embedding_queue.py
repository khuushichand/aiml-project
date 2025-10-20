from __future__ import annotations

import os
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.Embeddings.job_manager import (
    EmbeddingJobManager,
    JobManagerConfig,
    JobPriority,
    UserTier,
)
from tldw_Server_API.app.core.Embeddings.queue_schemas import ChunkingConfig
from tldw_Server_API.app.core.config import settings


def _redis_url() -> str:
    return (
        settings.get("EMBEDDINGS_REDIS_URL")
        or settings.get("REDIS_URL")
        or os.getenv("EMBEDDINGS_REDIS_URL")
        or os.getenv("REDIS_URL")
        or "redis://localhost:6379"
    )


async def enqueue_embeddings_job_for_item(
    *,
    user_id: int | str,
    item_id: int,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = JobPriority.NORMAL,
) -> None:
    """Best-effort queueing of an embedding job for a collections item."""
    if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes"}:
        return

    text = (content or "").strip()
    if not text:
        return

    redis_url = _redis_url()
    job_config = JobManagerConfig(redis_url=redis_url)
    manager = EmbeddingJobManager(job_config)

    try:
        await manager.initialize()
        await manager.create_job(
            media_id=item_id,
            user_id=str(user_id),
            user_tier=UserTier.FREE,
            content=text,
            content_type="text",
            chunking_config=ChunkingConfig(chunk_size=1000, overlap=200, separator="\n"),
            priority=priority,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.debug(f"Embedding job enqueue failed for item {item_id}: {exc}")
    finally:
        try:
            await manager.close()
        except Exception:
            pass
