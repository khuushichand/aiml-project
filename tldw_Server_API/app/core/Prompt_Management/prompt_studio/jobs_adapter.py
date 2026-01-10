from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager


_PROMPT_STUDIO_DOMAIN = "prompt_studio"


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _jobs_backend() -> str:
    backend = (os.getenv("PROMPT_STUDIO_JOBS_BACKEND") or os.getenv("TLDW_JOBS_BACKEND") or "").strip().lower()
    if backend not in {"core", "legacy"}:
        backend = "legacy"
    return backend


def _jobs_queue() -> str:
    queue = (os.getenv("PROMPT_STUDIO_JOBS_QUEUE") or "default").strip()
    return queue or "default"


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
    if status in {"queued", "processing", "completed", "failed", "cancelled"}:
        return status
    return "queued"


def _normalize_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _format_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _entity_id_from_payload(payload: Dict[str, Any]) -> Optional[int]:
    for key in ("optimization_id", "evaluation_id", "generation_id", "entity_id"):
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


class PromptStudioJobsAdapter:
    """Bridge Prompt Studio job views to the core Jobs table when enabled."""

    def __init__(
        self,
        *,
        backend: Optional[str] = None,
        read_legacy: Optional[bool] = None,
    ) -> None:
        self._backend = backend or _jobs_backend()
        self._read_legacy = _env_bool("JOBS_ADAPTER_READ_LEGACY_PROMPT_STUDIO", True) if read_legacy is None else bool(read_legacy)
        self._jm = _jobs_manager()

    @property
    def backend(self) -> str:
        return self._backend

    def get_job(
        self,
        job_id: str,
        *,
        db,
        user_id: Optional[str],
        job_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if self._backend == "core":
            job = self._lookup_core_job(job_id, user_id=user_id, job_type=job_type)
            if job is not None:
                return self._format_job(job)
        if self._read_legacy:
            return self._legacy_get_job(db, job_id)
        return None

    def list_jobs(
        self,
        *,
        db,
        user_id: Optional[str],
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self._backend == "core":
            jobs = self._jm.list_jobs(
                domain=_PROMPT_STUDIO_DOMAIN,
                queue=None,
                status=None,
                owner_user_id=str(user_id) if user_id is not None else None,
                job_type=job_type,
                limit=max(1, int(limit)),
            )
            return [self._format_job(job) for job in jobs]
        if self._read_legacy:
            return self._legacy_list_jobs(db, job_type=job_type, limit=limit)
        return []

    def get_latest_job_for_entity(
        self,
        *,
        db,
        user_id: Optional[str],
        job_type: str,
        entity_id: int,
    ) -> Optional[Dict[str, Any]]:
        jobs = self.list_jobs_for_entity(
            db=db,
            user_id=user_id,
            job_type=job_type,
            entity_id=entity_id,
            limit=1,
            ascending=False,
        )
        return jobs[0] if jobs else None

    def list_jobs_for_entity(
        self,
        *,
        db,
        user_id: Optional[str],
        job_type: str,
        entity_id: int,
        limit: int = 50,
        ascending: bool = True,
    ) -> List[Dict[str, Any]]:
        if self._backend == "core":
            raw_jobs = self._jm.list_jobs(
                domain=_PROMPT_STUDIO_DOMAIN,
                queue=None,
                status=None,
                owner_user_id=str(user_id) if user_id is not None else None,
                job_type=job_type,
                limit=max(1, int(limit) * 2),
            )
            matched = []
            for job in raw_jobs:
                payload = _normalize_payload(job.get("payload"))
                if _entity_id_from_payload(payload) == int(entity_id):
                    matched.append(job)
            matched.sort(key=lambda row: _format_datetime(row.get("created_at")) or "", reverse=not ascending)
            return [self._format_job(job) for job in matched[: int(limit)]]
        if self._read_legacy:
            return self._legacy_list_jobs_for_entity(
                db,
                job_type=job_type,
                entity_id=entity_id,
                limit=limit,
                ascending=ascending,
            )
        return []

    def _lookup_core_job(
        self,
        job_id: str,
        *,
        user_id: Optional[str],
        job_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        job = None
        if job_id:
            try:
                job = self._jm.get_job_by_uuid(str(job_id))
            except Exception:
                job = None
        if job is None and str(job_id).isdigit():
            try:
                job = self._jm.get_job(int(job_id))
            except Exception:
                job = None
        if job and self._matches(job, user_id=user_id, job_type=job_type):
            return job

        try:
            jobs = self._jm.list_jobs(
                domain=_PROMPT_STUDIO_DOMAIN,
                queue=None,
                status=None,
                owner_user_id=str(user_id) if user_id is not None else None,
                job_type=job_type,
                limit=200,
            )
        except Exception as exc:
            logger.debug(f"Prompt studio jobs adapter list failed: {exc}")
            return None

        for candidate in jobs:
            if self._matches(candidate, user_id=user_id, job_type=job_type):
                cid = candidate.get("uuid") or candidate.get("id")
                if cid and str(cid) == str(job_id):
                    return candidate
        return None

    def _matches(self, job: Dict[str, Any], *, user_id: Optional[str], job_type: Optional[str]) -> bool:
        if not job:
            return False
        if str(job.get("domain")) != _PROMPT_STUDIO_DOMAIN:
            return False
        if job_type and str(job.get("job_type")) != str(job_type):
            return False
        owner = job.get("owner_user_id")
        if owner is not None and user_id is not None and str(owner) != str(user_id):
            return False
        return True

    def _format_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = _normalize_payload(job.get("payload"))
        result = _normalize_payload(job.get("result"))
        progress = job.get("progress_percent")
        formatted: Dict[str, Any] = {
            "id": str(job.get("uuid") or job.get("id")),
            "uuid": job.get("uuid"),
            "job_type": job.get("job_type"),
            "status": _map_status(job.get("status")),
            "entity_id": _entity_id_from_payload(payload),
            "project_id": payload.get("project_id") or job.get("project_id"),
            "priority": job.get("priority"),
            "payload": json.dumps(payload),
            "result": json.dumps(result),
            "error_message": job.get("error_message") or job.get("last_error"),
            "created_at": _format_datetime(job.get("created_at")),
            "updated_at": _format_datetime(job.get("updated_at")),
            "started_at": _format_datetime(job.get("started_at") or job.get("acquired_at")),
            "completed_at": _format_datetime(job.get("completed_at")),
        }
        if progress is not None:
            try:
                formatted["progress"] = float(progress) / 100.0
            except (TypeError, ValueError):
                pass
        return formatted

    def _legacy_get_job(self, db, job_id: str) -> Optional[Dict[str, Any]]:
        from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_manager import JobManager as LegacyJobManager

        legacy = LegacyJobManager(db)
        try:
            if str(job_id).isdigit():
                job = legacy.get_job(int(job_id))
            else:
                job = legacy.get_job(job_id)
        except Exception:
            job = None
        if job is not None:
            return job
        return legacy.get_job_by_uuid(str(job_id))

    def _legacy_list_jobs(
        self,
        db,
        *,
        job_type: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_manager import JobManager as LegacyJobManager

        legacy = LegacyJobManager(db)
        return legacy.list_jobs(job_type=job_type, limit=limit)

    def _legacy_list_jobs_for_entity(
        self,
        db,
        *,
        job_type: str,
        entity_id: int,
        limit: int,
        ascending: bool,
    ) -> List[Dict[str, Any]]:
        return db.list_jobs_for_entity(job_type, entity_id, limit=limit, ascending=ascending)


__all__ = ["PromptStudioJobsAdapter"]
