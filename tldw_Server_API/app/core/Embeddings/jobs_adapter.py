from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tldw_Server_API.app.core.Embeddings import redis_pipeline
from tldw_Server_API.app.core.Jobs.manager import JobManager
_EMBEDDINGS_DOMAIN = "embeddings"
_EMBEDDINGS_ROOT_JOB_TYPE = "embeddings_pipeline"
_VALID_STAGES = {"chunking", "embedding", "storage"}


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _jobs_queue() -> str:
    queue = (os.getenv("EMBEDDINGS_JOBS_QUEUE") or "default").strip()
    return queue or "default"


def _root_jobs_queue(stage_queue: str) -> str:
    root_queue = (os.getenv("EMBEDDINGS_ROOT_JOBS_QUEUE") or "").strip()
    if root_queue:
        return root_queue
    return "low" if stage_queue != "low" else "default"


def _jobs_manager() -> JobManager:
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
    if not db_url:
        return JobManager()
    backend = "postgres" if db_url.startswith("postgres") else None
    return JobManager(backend=backend, db_url=db_url)


def _map_status(raw_status: Optional[str]) -> str:
    status = str(raw_status or "").lower()
    if status == "quarantined":
        return "failed"
    if status in {"processing", "completed", "failed", "cancelled"}:
        return status
    if status == "queued":
        return "queued"
    return "processing"


def _dt_to_epoch(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", ""))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _normalize_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _config_version(
    embedding_model: str,
    embedding_provider: Optional[str],
    chunk_size: Optional[int],
    chunk_overlap: Optional[int],
) -> str:
    return ":".join(
        [
            str(embedding_model or "").strip(),
            str(embedding_provider or "").strip(),
            str(chunk_size or ""),
            str(chunk_overlap or ""),
        ]
    )


def _map_priority(embedding_priority: Optional[int]) -> int:
    try:
        raw = int(embedding_priority) if embedding_priority is not None else 50
    except (TypeError, ValueError):
        raw = 50
    return max(1, min(10, int(raw / 10)))


def _derive_root_status(root_job: Dict[str, Any]) -> str:
    status = _map_status(root_job.get("status"))
    if status in {"completed", "failed", "cancelled"}:
        return status
    if status == "processing":
        return status
    result = _normalize_payload(root_job.get("result"))
    progress = root_job.get("progress_percent")
    progress_message = root_job.get("progress_message")
    if progress is not None:
        try:
            if float(progress) > 0:
                return "processing"
        except (TypeError, ValueError):
            pass
    if progress_message:
        return "processing"
    if any(result.get(key) is not None for key in ("embedding_count", "chunks_processed", "total_chunks")):
        return "processing"
    return "queued"


class EmbeddingsJobsAdapter:
    def __init__(
        self,
    ) -> None:
        self._expose_progress = _env_bool("EMBEDDINGS_JOBS_EXPOSE_PROGRESS", False)
        self._jm = _jobs_manager()

    def create_job(
        self,
        *,
        user_id: str,
        media_id: int,
        embedding_model: str,
        embedding_provider: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        request_source: Optional[str] = None,
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        force_regenerate: bool = False,
        stage: Optional[str] = None,
        embedding_priority: Optional[int] = None,
    ) -> Dict[str, Any]:
        stage_name = (stage or "chunking").strip().lower() or "chunking"
        if stage_name not in _VALID_STAGES:
            raise ValueError(f"Invalid embeddings stage: {stage_name}")
        payload: Dict[str, Any] = {
            "media_id": int(media_id),
            "embedding_model": embedding_model,
            "embedding_provider": embedding_provider,
            "current_stage": stage_name,
            "force_regenerate": bool(force_regenerate),
        }
        if embedding_priority is not None:
            payload["embedding_priority"] = int(embedding_priority)
        if chunk_size is not None:
            payload["chunk_size"] = int(chunk_size)
        if chunk_overlap is not None:
            payload["chunk_overlap"] = int(chunk_overlap)
        if request_source:
            payload["request_source"] = str(request_source)
        idempotency_key = None
        root_idempotency_key = None
        version = None
        if not force_regenerate:
            version = _config_version(embedding_model, embedding_provider, chunk_size, chunk_overlap)
            idempotency_key = f"{media_id}:{stage_name}:{version}"
            root_idempotency_key = f"{media_id}:root:{version}"
        if version is not None:
            payload["config_version"] = version
        stage_queue = _jobs_queue()
        root_queue = _root_jobs_queue(stage_queue)
        root_job = self._jm.create_job(
            domain=_EMBEDDINGS_DOMAIN,
            queue=root_queue,
            job_type=_EMBEDDINGS_ROOT_JOB_TYPE,
            payload=payload,
            owner_user_id=str(user_id) if user_id is not None else None,
            idempotency_key=root_idempotency_key,
            priority=_map_priority(embedding_priority),
            max_retries=0,
            request_id=request_id,
            trace_id=trace_id,
        )

        stage_payload = dict(payload)
        stage_payload["root_job_uuid"] = root_job.get("uuid")
        stage_payload["parent_job_uuid"] = root_job.get("uuid")
        stage_payload["user_id"] = str(user_id) if user_id is not None else None
        if request_id:
            stage_payload["request_id"] = str(request_id)
        if trace_id:
            stage_payload["trace_id"] = str(trace_id)
        if idempotency_key:
            stage_payload["idempotency_key"] = idempotency_key

        try:
            if stage_name == "chunking":
                redis_pipeline.enqueue_chunking_job(
                    payload=stage_payload,
                    root_job_uuid=str(root_job.get("uuid") or ""),
                    force_regenerate=bool(force_regenerate),
                    require_redis=not redis_pipeline.allow_stub(),
                )
            else:
                redis_pipeline.enqueue_stage(
                    stage=stage_name,
                    payload=stage_payload,
                    require_redis=not redis_pipeline.allow_stub(),
                )
        except Exception:
            try:
                self._jm.fail_job(
                    int(root_job["id"]),
                    error="Failed to enqueue embeddings job to Redis",
                    retryable=False,
                    enforce=False,
                )
            except Exception:
                pass
            raise
        return root_job

    def update_job(
        self,
        *,
        job_id: str,
        user_id: str,
        status: str,
        embedding_count: Optional[int] = None,
        chunks_processed: Optional[int] = None,
        error: Optional[str] = None,
    ) -> bool:
        job = self._lookup_job(job_id, user_id)
        if not job:
            return False
        job_db_id = int(job["id"])
        status_norm = str(status or "").lower()
        if status_norm == "completed":
            result: Dict[str, Any] = {}
            if embedding_count is not None:
                result["embedding_count"] = int(embedding_count)
            if chunks_processed is not None:
                result["chunks_processed"] = int(chunks_processed)
            return bool(self._jm.complete_job(job_db_id, result=result, enforce=False))
        if status_norm == "failed":
            message = error or "Embedding job failed"
            return bool(self._jm.fail_job(job_db_id, error=message, retryable=False, enforce=False))
        return False

    def get_job(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        job = self._lookup_job(job_id, user_id)
        if job:
            derived = _derive_root_status(job)
            return self._format_job(job, status_override=derived)
        return None

    def list_jobs(
        self,
        *,
        user_id: str,
        status: Optional[str],
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        desired = str(status).lower() if status else None
        status_filter = desired if desired in {"completed", "failed", "cancelled"} else None
        raw_limit = max(0, int(limit) + int(offset))
        jobs = self._jm.list_jobs(
            domain=_EMBEDDINGS_DOMAIN,
            queue=None,
            status=status_filter,
            owner_user_id=str(user_id),
            job_type=_EMBEDDINGS_ROOT_JOB_TYPE,
            limit=raw_limit or 1,
        )
        filtered: List[Dict[str, Any]] = []
        for job in jobs:
            derived = _derive_root_status(job)
            if desired and derived != desired:
                continue
            filtered.append(self._format_job(job, status_override=derived))
        if jobs:
            sliced = filtered[int(offset):int(offset) + int(limit)]
            return sliced
        return []

    def _format_job(self, job: Dict[str, Any], *, status_override: Optional[str] = None) -> Dict[str, Any]:
        payload = _normalize_payload(job.get("payload"))
        result = _normalize_payload(job.get("result"))
        response: Dict[str, Any] = {
            "id": str(job.get("uuid") or job.get("id")),
            "media_id": payload.get("media_id"),
            "user_id": job.get("owner_user_id"),
            "status": status_override or _map_status(job.get("status")),
            "embedding_model": payload.get("embedding_model"),
            "embedding_count": result.get("embedding_count"),
            "chunks_processed": result.get("chunks_processed"),
            "error": job.get("error_message") or job.get("last_error"),
            "created_at": _dt_to_epoch(job.get("created_at")),
            "updated_at": _dt_to_epoch(job.get("updated_at")),
        }
        if self._expose_progress:
            response["progress_percent"] = job.get("progress_percent")
            response["total_chunks"] = result.get("total_chunks")
        return response

    def _lookup_job(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        if not job_id:
            return None
        job = None
        job_uuid = str(job_id)
        try:
            job = self._jm.get_job_by_uuid(job_uuid)
        except Exception:
            job = None
        if not job and str(job_id).isdigit():
            try:
                job = self._jm.get_job(int(job_id))
            except Exception:
                job = None
        if not job:
            return None
        if str(job.get("domain")) != _EMBEDDINGS_DOMAIN:
            return None
        if str(job.get("job_type")) != _EMBEDDINGS_ROOT_JOB_TYPE:
            return None
        owner = job.get("owner_user_id")
        if owner is not None and str(owner) != str(user_id):
            return None
        return job

__all__ = ["EmbeddingsJobsAdapter"]
