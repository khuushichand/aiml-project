from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Chatbooks.chatbook_models import ExportStatus, ImportStatus


_CHATBOOKS_DOMAIN = "chatbooks"


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _warn_legacy_flag(key: str) -> None:
    if _env_bool(key, False):
        logger.warning("Chatbooks jobs legacy fallback flag {} is ignored; core Jobs is the only backend.", key)


def _jobs_manager() -> JobManager:
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
    if not db_url:
        return JobManager()
    backend = "postgres" if db_url.startswith("postgres") else None
    return JobManager(backend=backend, db_url=db_url)


def _job_id_from_row(job: Dict[str, Any]) -> Optional[str]:
    payload = job.get("payload") or {}
    candidate = payload.get("chatbooks_job_id") or job.get("uuid") or job.get("id")
    if candidate is None:
        return None
    return str(candidate)


def _map_export_status(status: Optional[str]) -> Optional[ExportStatus]:
    status = str(status or "").lower()
    if status == "queued":
        return ExportStatus.PENDING
    if status == "processing":
        return ExportStatus.IN_PROGRESS
    if status == "completed":
        return ExportStatus.COMPLETED
    if status == "failed":
        return ExportStatus.FAILED
    if status == "cancelled":
        return ExportStatus.CANCELLED
    if status == "quarantined":
        return ExportStatus.FAILED
    return None


def _map_import_status(status: Optional[str]) -> Optional[ImportStatus]:
    status = str(status or "").lower()
    if status == "queued":
        return ImportStatus.PENDING
    if status == "processing":
        return ImportStatus.IN_PROGRESS
    if status == "completed":
        return ImportStatus.COMPLETED
    if status == "failed":
        return ImportStatus.FAILED
    if status == "cancelled":
        return ImportStatus.CANCELLED
    if status == "quarantined":
        return ImportStatus.FAILED
    return None


class ChatbooksJobsAdapter:
    def __init__(
        self,
        *,
        owner_user_id: Optional[str],
    ) -> None:
        self._owner_user_id = str(owner_user_id) if owner_user_id is not None else None
        _warn_legacy_flag("JOBS_ADAPTER_READ_LEGACY_CHATBOOKS")
        self._jm = _jobs_manager()

    def apply_export_status(self, job, job_row: Optional[Dict[str, Any]] = None) -> None:
        if job_row is None:
            job_row = self._get_job(job.job_id, job_type="export")
        if job_row is None:
            return
        mapped = _map_export_status(job_row.get("status"))
        if mapped and job.status not in {ExportStatus.COMPLETED, ExportStatus.FAILED}:
            job.status = mapped

    def apply_import_status(self, job, job_row: Optional[Dict[str, Any]] = None) -> None:
        if job_row is None:
            job_row = self._get_job(job.job_id, job_type="import")
        if job_row is None:
            return
        mapped = _map_import_status(job_row.get("status"))
        if mapped and job.status not in {ImportStatus.COMPLETED, ImportStatus.FAILED}:
            job.status = mapped

    def map_jobs(
        self,
        *,
        job_ids: Iterable[str],
        job_type: str,
        limit: int,
    ) -> Dict[str, Dict[str, Any]]:
        wanted = {str(job_id) for job_id in job_ids if job_id}
        if not wanted:
            return {}
        jobs = self._jm.list_jobs(
            domain=_CHATBOOKS_DOMAIN,
            queue=None,
            status=None,
            owner_user_id=self._owner_user_id,
            job_type=job_type,
            limit=max(limit, len(wanted)),
        )
        mapping: Dict[str, Dict[str, Any]] = {}
        for job in jobs:
            cid = _job_id_from_row(job)
            if cid and cid in wanted:
                mapping[cid] = job
        return mapping

    def _get_job(self, job_id: str, job_type: str) -> Optional[Dict[str, Any]]:
        job = None
        if job_id:
            try:
                job = self._jm.get_job_by_uuid(job_id)
            except Exception:
                job = None
        if job is None and job_id and job_id.isdigit():
            try:
                job = self._jm.get_job(int(job_id))
            except Exception:
                job = None
        if self._is_match(job, job_id, job_type):
            return job

        try:
            jobs = self._jm.list_jobs(
                domain=_CHATBOOKS_DOMAIN,
                queue=None,
                status=None,
                owner_user_id=self._owner_user_id,
                job_type=job_type,
                limit=200,
            )
        except Exception as exc:
            logger.debug(f"Chatbooks jobs adapter list failed: {exc}")
            return None

        for candidate in jobs:
            if self._is_match(candidate, job_id, job_type):
                return candidate
        return None

    def _is_match(self, job: Optional[Dict[str, Any]], job_id: str, job_type: str) -> bool:
        if not job:
            return False
        if str(job.get("domain")) != _CHATBOOKS_DOMAIN:
            return False
        if str(job.get("job_type")) != str(job_type):
            return False
        owner = job.get("owner_user_id")
        if owner is not None and self._owner_user_id is not None and str(owner) != str(self._owner_user_id):
            return False
        cid = _job_id_from_row(job)
        if cid and str(cid) == str(job_id):
            return True
        return False


__all__ = ["ChatbooksJobsAdapter"]
