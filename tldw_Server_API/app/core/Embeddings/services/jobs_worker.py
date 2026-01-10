"""
Embeddings Jobs worker (Phase 2):

- Consumes core Jobs entries for media embeddings.
- Executes the embeddings pipeline using existing media embeddings helpers.
- Updates Jobs status/result via the core JobManager.

Job contract (domain/queue/job_type):
- domain = "embeddings"
- queue = os.getenv("EMBEDDINGS_JOBS_QUEUE", "default")
- job_type = "media_embeddings"

Payload fields (media jobs):
- media_id: int (required)
- embedding_model: str
- embedding_provider: str
- chunk_size: int
- chunk_overlap: int
- request_source: str (optional)

Usage:
  python -m tldw_Server_API.app.core.Embeddings.services.jobs_worker
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.DB_Management.db_path_utils import (
    DatabasePaths,
    get_user_media_db_path,
)
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerSDK, WorkerConfig
from tldw_Server_API.app.api.v1.endpoints.media_embeddings import (
    generate_embeddings_for_media,
    _resolve_model_provider,
)
from tldw_Server_API.app.api.v1.utils.rag_cache import invalidate_rag_caches


_EMBEDDINGS_DOMAIN = "embeddings"
_EMBEDDINGS_JOB_TYPE = "media_embeddings"


class EmbeddingsJobError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, backoff_seconds: Optional[int] = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        if backoff_seconds is not None:
            self.backoff_seconds = backoff_seconds


def _jobs_manager() -> JobManager:
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
    if not db_url:
        return JobManager()
    backend = "postgres" if db_url.startswith("postgres") else None
    return JobManager(backend=backend, db_url=db_url)


def _get_user_id(job: Dict[str, Any], payload: Dict[str, Any]) -> str:
    owner = job.get("owner_user_id") or payload.get("user_id")
    if owner is None or str(owner).strip() == "":
        return str(DatabasePaths.get_single_user_id())
    return str(owner)


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _load_media_content(media_id: int, user_id: str) -> Dict[str, Any]:
    db_path = get_user_media_db_path(user_id)
    db = create_media_database(client_id="embeddings_jobs_worker", db_path=db_path)

    media_item = db.get_media_by_id(media_id)
    if not media_item:
        raise EmbeddingsJobError(f"Media item {media_id} not found", retryable=False)

    try:
        if isinstance(media_item, dict) and not (media_item.get("content") or "").strip():
            from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import get_document_version

            latest = get_document_version(db, media_id=media_id, version_number=None, include_content=True)
            if latest and latest.get("content"):
                media_item = dict(media_item)
                media_item["content"] = latest["content"]
    except Exception as exc:
        logger.warning(f"Failed to load fallback document content for media {media_id}: {exc}")

    if not media_item:
        raise EmbeddingsJobError(f"No content found for media item {media_id}", retryable=False)

    return {
        "media_item": media_item,
        "content": media_item,
    }


async def _handle_job(job: Dict[str, Any]) -> Dict[str, Any]:
    job_type = job.get("job_type")
    if job_type != _EMBEDDINGS_JOB_TYPE:
        raise EmbeddingsJobError(
            f"Unsupported embeddings job type: {job_type}",
            retryable=False,
        )

    payload = job.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    media_id = payload.get("media_id")
    if media_id is None:
        raise EmbeddingsJobError("Missing media_id in job payload", retryable=False)

    user_id = _get_user_id(job, payload)

    embedding_model = payload.get("embedding_model")
    embedding_provider = payload.get("embedding_provider")
    embedding_model, embedding_provider = _resolve_model_provider(embedding_model, embedding_provider)

    chunk_size = _coerce_int(payload.get("chunk_size"), 1000)
    chunk_overlap = _coerce_int(payload.get("chunk_overlap"), 200)

    media_content = _load_media_content(int(media_id), user_id)
    result = await generate_embeddings_for_media(
        media_id=int(media_id),
        media_content=media_content,
        embedding_model=embedding_model,
        embedding_provider=embedding_provider,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        user_id=user_id,
    )

    allow_zero = bool(result.get("allow_zero_embeddings"))
    if result.get("status") != "success" and not allow_zero:
        error = result.get("error") or result.get("message") or "Embedding generation failed"
        raise EmbeddingsJobError(str(error), retryable=False)

    try:
        invalidate_rag_caches(None, namespaces=[user_id], media_id=int(media_id))
    except Exception:
        pass

    return {
        "embedding_count": result.get("embedding_count"),
        "chunks_processed": result.get("chunks_processed"),
        "embedding_model": embedding_model,
        "embedding_provider": embedding_provider,
    }


async def main() -> None:
    worker_id = (os.getenv("EMBEDDINGS_JOBS_WORKER_ID") or f"embeddings-jobs-{os.getpid()}").strip()
    queue = (os.getenv("EMBEDDINGS_JOBS_QUEUE") or "default").strip() or "default"

    cfg = WorkerConfig(
        domain=_EMBEDDINGS_DOMAIN,
        queue=queue,
        worker_id=worker_id,
        lease_seconds=_coerce_int(os.getenv("EMBEDDINGS_JOBS_LEASE_SECONDS"), 60),
        renew_jitter_seconds=_coerce_int(os.getenv("EMBEDDINGS_JOBS_RENEW_JITTER_SECONDS"), 5),
        renew_threshold_seconds=_coerce_int(os.getenv("EMBEDDINGS_JOBS_RENEW_THRESHOLD_SECONDS"), 10),
        backoff_base_seconds=_coerce_int(os.getenv("EMBEDDINGS_JOBS_BACKOFF_BASE_SECONDS"), 2),
        backoff_max_seconds=_coerce_int(os.getenv("EMBEDDINGS_JOBS_BACKOFF_MAX_SECONDS"), 30),
        retry_on_exception=True,
        retry_backoff_seconds=_coerce_int(os.getenv("EMBEDDINGS_JOBS_RETRY_BACKOFF_SECONDS"), 10),
    )

    jm = _jobs_manager()
    sdk = WorkerSDK(jm, cfg)
    logger.info(f"Embeddings Jobs worker starting (queue={queue}, worker_id={worker_id})")
    await sdk.run(handler=_handle_job)


if __name__ == "__main__":
    asyncio.run(main())
