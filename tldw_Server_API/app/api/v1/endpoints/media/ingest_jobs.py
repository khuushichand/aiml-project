from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4
import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from cachetools import LRUCache
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request, Query
from pydantic import BaseModel, Field
from loguru import logger
from starlette.responses import JSONResponse

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    check_rate_limit,
    get_auth_principal,
    rbac_rate_limit,
    require_permissions,
)
from tldw_Server_API.app.api.v1.API_Deps.media_add_deps import get_add_media_form
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import file_validator_instance
from tldw_Server_API.app.api.v1.schemas.media_request_models import AddMediaForm
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_CREATE
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
    save_uploaded_files,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
    validate_add_media_inputs,
)
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, ensure_traceparent


router = APIRouter()

MAX_CACHED_JOB_MANAGER_INSTANCES = 4
_job_manager_cache: LRUCache = LRUCache(maxsize=MAX_CACHED_JOB_MANAGER_INSTANCES)
_job_manager_lock = threading.Lock()


def get_job_manager() -> JobManager:
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
    db_path = (os.getenv("JOBS_DB_PATH") or "").strip()
    cache_key = f"url:{db_url}" if db_url else f"path:{db_path or 'default'}"
    with _job_manager_lock:
        cached = _job_manager_cache.get(cache_key)
        if cached is not None:
            return cached

        if not db_url:
            if db_path:
                job_manager = JobManager(db_path=Path(db_path))
            else:
                job_manager = JobManager()
        else:
            backend = "postgres" if db_url.startswith("postgres") else None
            job_manager = JobManager(backend=backend, db_url=db_url)

        _job_manager_cache[cache_key] = job_manager
        return job_manager


class MediaIngestJobItem(BaseModel):
    id: int
    uuid: Optional[str]
    source: str
    source_kind: str
    status: str


class SubmitMediaIngestJobsResponse(BaseModel):
    batch_id: str
    jobs: List[MediaIngestJobItem]
    errors: List[str] = Field(default_factory=list)


class MediaIngestJobStatus(BaseModel):
    id: int
    uuid: Optional[str]
    status: str
    job_type: str
    owner_user_id: Optional[str]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    cancelled_at: Optional[str]
    cancellation_reason: Optional[str]
    progress_percent: Optional[float]
    progress_message: Optional[str]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    media_type: Optional[str] = None
    source: Optional[str] = None
    source_kind: Optional[str] = None
    batch_id: Optional[str] = None


class CancelMediaIngestJobResponse(BaseModel):
    success: bool
    job_id: int
    status: str
    message: Optional[str] = None


class MediaIngestJobListResponse(BaseModel):
    batch_id: str
    jobs: List[MediaIngestJobStatus]


def _cleanup_dir(path_str: str) -> None:
    try:
        shutil.rmtree(path_str, ignore_errors=True)
    except Exception as exc:
        logger.debug("Failed to cleanup temp dir {}: {}", path_str, exc)


def _normalize_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            logger.debug(
                "Failed to parse payload as JSON (length={}, error={})",
                len(payload),
                exc,
            )
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_job_created_at(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _job_to_status(job: Dict[str, Any]) -> MediaIngestJobStatus:
    payload = _normalize_payload(job.get("payload"))
    id_value = job.get("id")
    if id_value is None:
        raise ValueError(f"Missing job id in job: {job!r}")
    try:
        job_id = int(id_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid job id {id_value!r} in job: {job!r}") from exc
    return MediaIngestJobStatus(
        id=job_id,
        uuid=job.get("uuid"),
        status=job.get("status"),
        job_type=job.get("job_type"),
        owner_user_id=job.get("owner_user_id"),
        created_at=job.get("created_at"),
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        cancelled_at=job.get("cancelled_at"),
        cancellation_reason=job.get("cancellation_reason"),
        progress_percent=job.get("progress_percent"),
        progress_message=job.get("progress_message"),
        result=job.get("result"),
        error_message=job.get("error_message"),
        media_type=payload.get("media_type"),
        source=payload.get("source"),
        source_kind=payload.get("source_kind"),
        batch_id=payload.get("batch_id"),
    )


@router.post(
    "/ingest/jobs",
    response_model=SubmitMediaIngestJobsResponse,
    summary="Submit async media ingestion jobs (one job per item)",
    tags=["Media Ingestion Jobs"],
    dependencies=[
        Depends(require_permissions(MEDIA_CREATE)),
        Depends(rbac_rate_limit("media.create")),
    ],
)
async def submit_media_ingest_jobs(
    request: Request,
    form_data: AddMediaForm = Depends(get_add_media_form),
    files: Optional[List[UploadFile]] = File(None, description="Optional media uploads"),
    current_user: User = Depends(get_request_user),
    jm: JobManager = Depends(get_job_manager),
) -> SubmitMediaIngestJobsResponse:
    rid = ensure_request_id(request) if request is not None else None
    tp = ensure_traceparent(request) if request is not None else ""

    # Normalize sentinel urls=[''] from some clients.
    if form_data.urls and form_data.urls == [""]:
        form_data.urls = None

    validate_add_media_inputs(form_data.media_type, form_data.urls, files)

    options = form_data.model_dump(mode="json")
    options.pop("urls", None)
    options.pop("keywords", None)

    batch_id = str(uuid4())
    jobs: List[MediaIngestJobItem] = []
    errors: List[str] = []

    url_list = form_data.urls or []
    for url in url_list:
        if not url or not str(url).strip():
            continue
        payload = {
            "batch_id": batch_id,
            "media_type": str(form_data.media_type),
            "source": str(url).strip(),
            "source_kind": "url",
            "input_ref": str(url).strip(),
            "options": options,
        }
        row = jm.create_job(
            domain="media_ingest",
            queue="default",
            job_type="media_ingest_item",
            payload=payload,
            owner_user_id=str(current_user.id),
            priority=5,
            max_retries=3,
            request_id=rid,
            trace_id=tp or None,
        )
        row_id = row.get("id")
        if row_id is None:
            raise ValueError(f"Job creation returned no id: {row!r}")
        jobs.append(
            MediaIngestJobItem(
                id=int(row_id),
                uuid=row.get("uuid"),
                source=payload["source"],
                source_kind="url",
                status=row.get("status"),
            )
        )

    if files:
        for upload in files:
            temp_dir_path = None
            try:
                with TempDirManager(prefix="media_ingest_job_", cleanup=False) as temp_dir:
                    temp_dir_path = str(temp_dir)
                    saved_files, file_errors = await save_uploaded_files(
                        [upload],
                        temp_dir=temp_dir,
                        validator=file_validator_instance,
                        expected_media_type_key=str(form_data.media_type),
                    )
                if file_errors:
                    for err in file_errors:
                        msg = err.get("error") or "Failed to stage upload"
                        errors.append(msg)
                    if temp_dir_path:
                        _cleanup_dir(temp_dir_path)
                    continue
                if not saved_files:
                    errors.append("Failed to stage upload")
                    if temp_dir_path:
                        _cleanup_dir(temp_dir_path)
                    continue

                saved = saved_files[0]
                source_path = str(saved.get("path"))
                original_filename = saved.get("original_filename")
                input_ref = saved.get("input_ref") or original_filename or source_path

                payload = {
                    "batch_id": batch_id,
                    "media_type": str(form_data.media_type),
                    "source": source_path,
                    "source_kind": "file",
                    "input_ref": input_ref,
                    "original_filename": original_filename,
                    "temp_dir": temp_dir_path,
                    "cleanup_temp_dir": True,
                    "options": options,
                }
                row = jm.create_job(
                    domain="media_ingest",
                    queue="default",
                    job_type="media_ingest_item",
                    payload=payload,
                    owner_user_id=str(current_user.id),
                    priority=5,
                    max_retries=3,
                    request_id=rid,
                    trace_id=tp or None,
                )
                row_id = row.get("id")
                if row_id is None:
                    raise ValueError(f"Job creation returned no id: {row!r}")
                jobs.append(
                    MediaIngestJobItem(
                        id=int(row_id),
                        uuid=row.get("uuid"),
                        source=source_path,
                        source_kind="file",
                        status=row.get("status"),
                    )
                )
            except Exception as exc:
                logger.warning("Failed to stage upload for ingest jobs: {}", exc)
                errors.append(f"Upload staging failed: {exc}")
                if temp_dir_path:
                    _cleanup_dir(temp_dir_path)

    if not jobs:
        if errors:
            return JSONResponse(
                status_code=status.HTTP_207_MULTI_STATUS,
                content=SubmitMediaIngestJobsResponse(
                    batch_id=batch_id,
                    jobs=[],
                    errors=errors,
                ).model_dump(),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid media sources supplied.",
        )

    return SubmitMediaIngestJobsResponse(batch_id=batch_id, jobs=jobs, errors=errors)


@router.get(
    "/ingest/jobs/{job_id}",
    response_model=MediaIngestJobStatus,
    summary="Get media ingest job status",
    tags=["Media Ingestion Jobs"],
    dependencies=[Depends(check_rate_limit)],
)
async def get_media_ingest_job(
    job_id: int,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    jm: JobManager = Depends(get_job_manager),
) -> MediaIngestJobStatus:
    job = jm.get_job(int(job_id))
    if not job or str(job.get("domain") or "") != "media_ingest":
        raise HTTPException(status_code=404, detail="Job not found")

    owner = str(job.get("owner_user_id") or "")
    if not (principal.is_admin or owner == str(current_user.id)):
        raise HTTPException(status_code=403, detail="Not authorized for this job")

    return _job_to_status(job)


@router.get(
    "/ingest/jobs",
    response_model=MediaIngestJobListResponse,
    summary="List media ingest jobs for a batch",
    tags=["Media Ingestion Jobs"],
)
async def list_media_ingest_jobs(
    batch_id: str = Query(..., min_length=1, description="Batch identifier from submit response"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    _: None = Depends(check_rate_limit),
    jm: JobManager = Depends(get_job_manager),
) -> MediaIngestJobListResponse:
    owner_filter = None if principal.is_admin else str(current_user.id)
    # Fetch in larger batches internally (100-500) to reduce DB round-trips
    # while still respecting the user limit for the final result set.
    page_limit = min(500, max(limit, 100))
    matched: List[MediaIngestJobStatus] = []
    cursor_created_at: Optional[datetime] = None
    cursor_id: Optional[int] = None
    last_cursor: Optional[tuple[datetime, int]] = None
    while len(matched) < limit:
        jobs = jm.list_jobs(
            domain="media_ingest",
            owner_user_id=owner_filter,
            limit=page_limit,
            created_before=cursor_created_at,
            before_id=cursor_id,
            sort_by="created_at",
            sort_order="desc",
        )
        if not jobs:
            break
        for job in jobs:
            payload = _normalize_payload(job.get("payload"))
            if str(payload.get("batch_id") or "") == batch_id:
                matched.append(_job_to_status(job))
                if len(matched) >= limit:
                    return MediaIngestJobListResponse(batch_id=batch_id, jobs=matched[:limit])
        if len(jobs) < page_limit:
            break
        last_job = jobs[-1]
        next_created_at = _parse_job_created_at(last_job.get("created_at"))
        next_id_raw = last_job.get("id")
        if next_created_at is None or next_id_raw is None:
            break
        next_cursor = (next_created_at, int(next_id_raw))
        if last_cursor == next_cursor:
            break
        last_cursor = next_cursor
        cursor_created_at, cursor_id = next_cursor

    return MediaIngestJobListResponse(batch_id=batch_id, jobs=matched[:limit])


@router.delete(
    "/ingest/jobs/{job_id}",
    response_model=CancelMediaIngestJobResponse,
    summary="Cancel a media ingest job",
    tags=["Media Ingestion Jobs"],
    dependencies=[Depends(check_rate_limit)],
)
async def cancel_media_ingest_job(
    job_id: int,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    jm: JobManager = Depends(get_job_manager),
    reason: Optional[str] = Query(None, description="Reason for cancellation"),
) -> CancelMediaIngestJobResponse:
    job = jm.get_job(int(job_id))
    if not job or str(job.get("domain") or "") != "media_ingest":
        raise HTTPException(status_code=404, detail="Job not found")

    owner = str(job.get("owner_user_id") or "")
    if not (principal.is_admin or owner == str(current_user.id)):
        raise HTTPException(status_code=403, detail="Not authorized for this job")

    status_val = str(job.get("status") or "").lower()
    if status_val in {"completed", "failed", "cancelled", "quarantined"}:
        raise HTTPException(status_code=400, detail="Cannot cancel terminal job")

    ok = jm.cancel_job(int(job_id), reason=reason)
    if not ok:
        raise HTTPException(status_code=400, detail="Cancellation failed")

    return CancelMediaIngestJobResponse(
        success=True,
        job_id=int(job_id),
        status="cancelled",
        message="Job cancellation requested",
    )


__all__ = ["router"]
