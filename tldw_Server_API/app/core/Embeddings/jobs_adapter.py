from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
_EMBEDDINGS_DOMAIN = "embeddings"
_EMBEDDINGS_JOB_TYPE = "media_embeddings"


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _jobs_queue() -> str:
    queue = (os.getenv("EMBEDDINGS_JOBS_QUEUE") or "default").strip()
    return queue or "default"


def _jobs_manager() -> JobManager:
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
    if not db_url:
        return JobManager()
    backend = "postgres" if db_url.startswith("postgres") else None
    return JobManager(backend=backend, db_url=db_url)


def _map_status(raw_status: Optional[str]) -> str:
    status = str(raw_status or "").lower()
    if status == "queued":
        return "processing"
    if status == "quarantined":
        return "failed"
    if status in {"processing", "completed", "failed", "cancelled"}:
        return status
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


class EmbeddingsJobsAdapter:
    def __init__(
        self,
        *,
        read_legacy: Optional[bool] = None,
    ) -> None:
        self._read_legacy = _env_bool("JOBS_ADAPTER_READ_LEGACY_EMBEDDINGS", True) if read_legacy is None else bool(read_legacy)
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
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "media_id": int(media_id),
            "embedding_model": embedding_model,
            "embedding_provider": embedding_provider,
        }
        if chunk_size is not None:
            payload["chunk_size"] = int(chunk_size)
        if chunk_overlap is not None:
            payload["chunk_overlap"] = int(chunk_overlap)
        if request_source:
            payload["request_source"] = str(request_source)
        return self._jm.create_job(
            domain=_EMBEDDINGS_DOMAIN,
            queue=_jobs_queue(),
            job_type=_EMBEDDINGS_JOB_TYPE,
            payload=payload,
            owner_user_id=str(user_id) if user_id is not None else None,
            priority=5,
            max_retries=0,
            request_id=request_id,
            trace_id=trace_id,
        )

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
            return self._format_job(job)
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
        mapped_status = None
        filter_after = None
        if desired == "processing":
            filter_after = {"processing"}
        elif desired in {"completed", "failed", "cancelled"}:
            mapped_status = desired
        raw_limit = max(0, int(limit) + int(offset))
        jobs = self._jm.list_jobs(
            domain=_EMBEDDINGS_DOMAIN,
            queue=None,
            status=mapped_status,
            owner_user_id=str(user_id),
            job_type=_EMBEDDINGS_JOB_TYPE,
            limit=raw_limit or 1,
        )
        if filter_after:
            jobs = [job for job in jobs if _map_status(job.get("status")) in filter_after]
        if jobs:
            sliced = jobs[int(offset):int(offset) + int(limit)]
            return [self._format_job(job) for job in sliced]
        return []

    def _format_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = _normalize_payload(job.get("payload"))
        result = _normalize_payload(job.get("result"))
        response: Dict[str, Any] = {
            "id": str(job.get("uuid") or job.get("id")),
            "media_id": payload.get("media_id"),
            "user_id": job.get("owner_user_id"),
            "status": _map_status(job.get("status")),
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
        if str(job.get("job_type")) != _EMBEDDINGS_JOB_TYPE:
            return None
        owner = job.get("owner_user_id")
        if owner is not None and str(owner) != str(user_id):
            return None
        return job


__all__ = ["EmbeddingsJobsAdapter"]
