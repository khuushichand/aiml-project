from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.quota_config import (
    apply_prompt_studio_quota_defaults,
)

_PROMPT_STUDIO_DOMAIN = "prompt_studio"


def _jobs_backend() -> str:
    backend = (os.getenv("PROMPT_STUDIO_JOBS_BACKEND") or os.getenv("TLDW_JOBS_BACKEND") or "").strip().lower()
    if backend and backend != "core":
        logger.warning("Prompt Studio jobs backend override ignored; only core Jobs is supported now.")
    return "core"


def _jobs_queue() -> str:
    queue = (os.getenv("PROMPT_STUDIO_JOBS_QUEUE") or "default").strip()
    return queue or "default"


def _jobs_manager() -> JobManager:
    apply_prompt_studio_quota_defaults()
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
    if not db_url:
        return JobManager()
    backend = "postgres" if db_url.startswith("postgres") else None
    return JobManager(backend=backend, db_url=db_url)


def _map_status(raw_status: str | None) -> str:
    status = str(raw_status or "").lower()
    if status == "quarantined":
        return "failed"
    if status in {"queued", "processing", "completed", "failed", "cancelled"}:
        return status
    return "queued"


def _normalize_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _format_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _entity_id_from_payload(payload: dict[str, Any]) -> int | None:
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
        backend: str | None = None,
    ) -> None:
        if backend and backend != "core":
            logger.warning("Prompt Studio jobs adapter forced to core backend; legacy backend removed.")
        self._backend = "core"
        self._jm = _jobs_manager()

    @property
    def backend(self) -> str:
        return self._backend

    def get_job(
        self,
        job_id: str,
        *,
        db,
        user_id: str | None,
        job_type: str | None = None,
    ) -> dict[str, Any] | None:
        if self._backend == "core":
            job = self._lookup_core_job(job_id, user_id=user_id, job_type=job_type)
            if job is not None:
                return self._format_job(job)
        return None

    def list_jobs(
        self,
        *,
        db,
        user_id: str | None,
        job_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
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
        return []

    def get_latest_job_for_entity(
        self,
        *,
        db,
        user_id: str | None,
        job_type: str,
        entity_id: int,
    ) -> dict[str, Any] | None:
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
        user_id: str | None,
        job_type: str,
        entity_id: int,
        limit: int = 50,
        ascending: bool = True,
    ) -> list[dict[str, Any]]:
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
        return []

    def create_job(
        self,
        *,
        user_id: str | None,
        job_type: str,
        entity_id: int | None,
        payload: dict[str, Any] | None,
        project_id: int | None = None,
        priority: int = 5,
        max_retries: int = 3,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        payload_dict: dict[str, Any] = dict(payload or {})
        if entity_id is not None:
            try:
                payload_dict.setdefault("entity_id", int(entity_id))
            except (TypeError, ValueError):
                payload_dict.setdefault("entity_id", entity_id)
        return self._jm.create_job(
            domain=_PROMPT_STUDIO_DOMAIN,
            queue=_jobs_queue(),
            job_type=str(job_type),
            payload=payload_dict,
            owner_user_id=str(user_id) if user_id is not None else None,
            project_id=project_id,
            priority=priority,
            max_retries=max_retries,
            request_id=request_id,
            trace_id=trace_id,
        )

    def cancel_job(
        self,
        job_id: str,
        *,
        user_id: str | None,
        reason: str | None = None,
        job_type: str | None = None,
    ) -> bool:
        job = self._lookup_core_job(job_id, user_id=user_id, job_type=job_type)
        if not job:
            return False
        try:
            return bool(self._jm.cancel_job(int(job["id"]), reason=reason))
        except Exception:
            return False

    def _lookup_core_job(
        self,
        job_id: str,
        *,
        user_id: str | None,
        job_type: str | None,
    ) -> dict[str, Any] | None:
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

    def _matches(self, job: dict[str, Any], *, user_id: str | None, job_type: str | None) -> bool:
        if not job:
            return False
        if str(job.get("domain")) != _PROMPT_STUDIO_DOMAIN:
            return False
        if job_type and str(job.get("job_type")) != str(job_type):
            return False
        owner = job.get("owner_user_id")
        return not (owner is not None and user_id is not None and str(owner) != str(user_id))

    def _format_job(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = _normalize_payload(job.get("payload"))
        result = _normalize_payload(job.get("result"))
        progress = job.get("progress_percent")
        formatted: dict[str, Any] = {
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
            with contextlib.suppress(TypeError, ValueError):
                formatted["progress"] = float(progress) / 100.0
        return formatted

__all__ = ["PromptStudioJobsAdapter"]
