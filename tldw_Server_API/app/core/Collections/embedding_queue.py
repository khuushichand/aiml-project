from __future__ import annotations

import os
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _jobs_queue() -> str:
    queue = (os.getenv("EMBEDDINGS_JOBS_QUEUE") or "default").strip()
    return queue or "default"


def _map_priority(priority: int) -> int:
    # Map 0-100 legacy priority to 1-10 Jobs priority.
    try:
        val = int(priority)
    except (TypeError, ValueError):
        val = 50
    mapped = max(1, min(10, int(val / 10)))
    return mapped or 5


async def enqueue_embeddings_job_for_item(
    *,
    user_id: int | str,
    item_id: int,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = 50,
) -> None:
    """Best-effort queueing of an embedding job for a collections item."""
    if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes"}:
        return

    text = (content or "").strip()
    if not text:
        return

    try:
        jm = JobManager()
        payload = {
            "item_id": int(item_id),
            "content": text,
            "metadata": metadata or {},
        }
        jm.create_job(
            domain="embeddings",
            queue=_jobs_queue(),
            job_type="content_embeddings",
            payload=payload,
            owner_user_id=str(user_id),
            priority=_map_priority(priority),
            max_retries=0,
        )
    except Exception as exc:
        logger.debug(f"Embedding job enqueue failed for item {item_id}: {exc}")
