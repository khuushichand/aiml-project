from __future__ import annotations

from typing import Optional, List, Dict, Any
import os

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, Field
try:
    # Pydantic v2
    from pydantic import model_validator  # type: ignore
except Exception:  # pragma: no cover - fallback for older environments
    model_validator = None  # type: ignore
from loguru import logger
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, ensure_traceparent, get_ps_logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    require_permissions,
    require_roles,
)
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_MAINTENANCE
from tldw_Server_API.app.core.Usage.audio_quota import TIER_LIMITS, get_user_tier, set_user_tier


router = APIRouter()


def get_job_manager() -> JobManager:
    """
    Dependency helper to construct a JobManager using JOBS_DB_URL.
    """
    db_url = os.getenv("JOBS_DB_URL")
    backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
    return JobManager(backend=backend, db_url=db_url)


class SubmitAudioJobRequest(BaseModel):
    url: Optional[str] = Field(None, description="URL to download audio from")
    local_path: Optional[str] = Field(None, description="Server-local path to an existing audio/video file")
    model: str = Field("whisper-1", description="Transcription model selector")
    perform_chunking: bool = Field(True, description="Whether to chunk the transcript after STT")
    perform_analysis: bool = Field(False, description="Whether to run LLM analysis after chunking")
    api_name: Optional[str] = Field(None, description="LLM provider key for analysis stage")

    if model_validator is not None:
        @model_validator(mode="after")
        def _validate_inputs(self) -> "SubmitAudioJobRequest":
            url = (self.url or "").strip() if self.url else ""
            lp = (self.local_path or "").strip() if self.local_path else ""
            if not url and not lp:
                raise ValueError("Either 'url' or 'local_path' must be provided")
            if url and lp:
                raise ValueError("Provide only one of 'url' or 'local_path'")
            return self
    else:
        # Backward-compatible path for environments still on Pydantic v1
        from pydantic import root_validator as _rv  # type: ignore

        @_rv
        def _validate_inputs(cls, values: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[no-redef]
            url = (values.get("url") or "").strip()
            lp = (values.get("local_path") or "").strip()
            if not url and not lp:
                raise ValueError("Either 'url' or 'local_path' must be provided")
            if url and lp:
                raise ValueError("Provide only one of 'url' or 'local_path'")
            return values


class SubmitAudioJobResponse(BaseModel):
    id: int
    uuid: Optional[str] = None
    domain: str
    queue: str
    job_type: str
    status: str


@router.post("/jobs/submit", response_model=SubmitAudioJobResponse, summary="Submit an audio processing job")
async def submit_audio_job(
    req: SubmitAudioJobRequest,
    current_user: User = Depends(get_request_user),
    jm: JobManager = Depends(get_job_manager),
    request: Request = None,
):
    """
    Create an audio job in the Jobs queue. First stage is determined by input:
    - url → audio_download
    - local_path → audio_convert
    """
    # Correlation IDs
    rid = ensure_request_id(request) if request is not None else None
    tp = ensure_traceparent(request) if request is not None else ""

    try:
        payload: Dict[str, Any] = {
            "model": req.model,
            "perform_chunking": bool(req.perform_chunking),
            "perform_analysis": bool(req.perform_analysis),
            "api_name": req.api_name,
        }
        job_type = "audio_download" if (req.url and req.url.strip()) else "audio_convert"
        if job_type == "audio_download":
            payload["url"] = req.url.strip()
            payload["temp_dir"] = os.getenv("AUDIO_JOBS_TEMP", "/tmp")
        else:
            payload["local_path"] = req.local_path.strip()

        row = jm.create_job(
            domain="audio",
            queue="default",
            job_type=job_type,
            payload=payload,
            owner_user_id=str(current_user.id),
            priority=5,
            max_retries=3,
            request_id=rid,
        )
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio", traceparent=tp).info(
            "Submitted audio job: job_id=%s type=%s", row.get("id"), job_type
        )
        return SubmitAudioJobResponse(
            id=int(row.get("id")),
            uuid=row.get("uuid"),
            domain=row.get("domain"),
            queue=row.get("queue"),
            job_type=row.get("job_type"),
            status=row.get("status"),
        )
    except HTTPException:
        raise
    except Exception as e:
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio", traceparent=tp).error(
            "Failed to submit audio job: %s", e
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit job")


class AudioJob(BaseModel):
    id: int
    uuid: Optional[str]
    job_type: str
    status: str
    priority: int
    retry_count: int
    max_retries: int
    owner_user_id: Optional[str]
    available_at: Optional[str]
    started_at: Optional[str]
    leased_until: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    completed_at: Optional[str]


@router.get("/jobs/{job_id}", response_model=AudioJob, summary="Get audio job status")
async def get_audio_job(
    job_id: int,
    current_user: User = Depends(get_request_user),
    jm: JobManager = Depends(get_job_manager),
):
    """
    Return a single audio job if it belongs to the caller (or the caller is admin).
    """
    try:
        d = jm.get_job(int(job_id))
        if not d or str(d.get("domain") or "") != "audio":
            raise HTTPException(status_code=404, detail="Job not found")
        # Owner/admin check
        owner = str(d.get("owner_user_id") or "")
        if not (current_user.is_admin or owner == str(current_user.id)):
            raise HTTPException(status_code=403, detail="Not authorized for this job")
        field_map = getattr(AudioJob, "model_fields", None) or getattr(AudioJob, "__fields__", {})
        return AudioJob(**{k: d.get(k) for k in field_map.keys()})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch job: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch job")


class ListAudioJobsResponse(BaseModel):
    jobs: List[AudioJob]


@router.get(
    "/jobs/admin/list",
    response_model=ListAudioJobsResponse,
    summary="List audio jobs (admin)",
    dependencies=[Depends(require_roles("admin")), Depends(require_permissions(SYSTEM_MAINTENANCE))],
)
async def list_audio_jobs_admin(
    status_filter: Optional[str] = Query(None, description="Filter by status: queued|processing|completed|failed|cancelled"),
    owner_user_id: Optional[str] = Query(None, description="Filter by owner user id"),
    limit: int = Query(50, ge=1, le=200),
    jm: JobManager = Depends(get_job_manager),
):
    try:
        jobs = jm.list_jobs(
            domain="audio",
            status=status_filter,
            owner_user_id=str(owner_user_id) if owner_user_id is not None else None,
            limit=int(limit),
            sort_by="created_at",
            sort_order="desc",
        )
        # Project to model
        field_map = getattr(AudioJob, "model_fields", None) or getattr(AudioJob, "__fields__", {})
        out = [AudioJob(**{k: j.get(k) for k in field_map.keys()}) for j in jobs]
        return ListAudioJobsResponse(jobs=out)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list jobs")


class AudioJobsSummary(BaseModel):
    counts_by_status: Dict[str, int]
    total: int
    owner_user_id: Optional[str] = None


@router.get(
    "/jobs/admin/summary",
    response_model=AudioJobsSummary,
    summary="Summarize audio jobs by status (admin)",
    dependencies=[Depends(require_roles("admin")), Depends(require_permissions(SYSTEM_MAINTENANCE))],
)
async def summarize_audio_jobs_admin(
    owner_user_id: Optional[str] = Query(None, description="Optional owner filter"),
    max_rows: int = Query(
        1000,
        ge=1,
        le=10000,
        description="Maximum number of jobs to scan for summary counts.",
    ),
    jm: JobManager = Depends(get_job_manager),
):
    try:
        by_status: Dict[str, int] = {}
        total = 0
        # Use list_jobs and aggregate counts in Python to avoid relying on private JobManager internals.
        jobs = jm.list_jobs(
            domain="audio",
            owner_user_id=str(owner_user_id) if owner_user_id is not None else None,
            # Use a generous limit for summaries; callers can adjust via max_rows.
            limit=int(max_rows),
        )
        for job in jobs:
            status_val = str(job.get("status") or "")
            if not status_val:
                continue
            by_status[status_val] = by_status.get(status_val, 0) + 1
        total = sum(by_status.values())
        return AudioJobsSummary(counts_by_status=by_status, total=total, owner_user_id=owner_user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to summarize jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to summarize jobs")


class AudioJobsOwnerSummaryItem(BaseModel):
    owner_user_id: Optional[str]
    status: str
    count: int


class AudioJobsSummaryByOwner(BaseModel):
    items: List[AudioJobsOwnerSummaryItem]


@router.get(
    "/jobs/admin/summary-by-owner",
    response_model=AudioJobsSummaryByOwner,
    summary="Summarize audio jobs by owner and status (admin)",
    dependencies=[Depends(require_roles("admin")), Depends(require_permissions(SYSTEM_MAINTENANCE))],
)
async def summary_by_owner_admin(
    max_rows: int = Query(
        1000,
        ge=1,
        le=10000,
        description="Maximum number of jobs to scan for owner/status summary.",
    ),
    jm: JobManager = Depends(get_job_manager),
):
    try:
        items: List[AudioJobsOwnerSummaryItem] = []
        # Aggregate by owner and status using list_jobs to avoid private internals.
        jobs = jm.list_jobs(domain="audio", limit=int(max_rows))
        summary: Dict[tuple[Optional[str], str], int] = {}
        for job in jobs:
            owner = job.get("owner_user_id")
            owner_str: Optional[str] = str(owner) if owner is not None else None
            status_val = str(job.get("status") or "")
            if not status_val:
                continue
            key = (owner_str, status_val)
            summary[key] = summary.get(key, 0) + 1
        for (owner_str, status_val), count in summary.items():
            items.append(
                AudioJobsOwnerSummaryItem(
                    owner_user_id=owner_str,
                    status=status_val,
                    count=int(count),
                )
            )
        return AudioJobsSummaryByOwner(items=items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to summarize by owner: {e}")
        raise HTTPException(status_code=500, detail="Failed to summarize by owner")


class OwnerProcessingSummary(BaseModel):
    owner_user_id: str
    processing: int
    limit: Optional[int]


@router.get(
    "/jobs/admin/owner/{owner_user_id}/processing",
    response_model=OwnerProcessingSummary,
    summary="Get owner's processing count and limit (admin)",
    dependencies=[Depends(require_roles("admin")), Depends(require_permissions(SYSTEM_MAINTENANCE))],
)
async def owner_processing_summary(
    owner_user_id: str,
    max_rows: int = Query(
        1000,
        ge=1,
        le=10000,
        description="Maximum number of jobs to scan when counting processing jobs.",
    ),
    jm: JobManager = Depends(get_job_manager),
    request: Request = None,
):
    try:
        # Count processing jobs for this owner using JobManager APIs.
        jobs = jm.list_jobs(
            domain="audio",
            status="processing",
            owner_user_id=str(owner_user_id),
            limit=int(max_rows),
        )
        processing = len(jobs)
        # Limit
        # Correlate logs with request_id if available
        rid = ensure_request_id(request) if request is not None else None

        try:
            from tldw_Server_API.app.core.Usage.audio_quota import get_limits_for_user
            limits = await get_limits_for_user(int(owner_user_id))
        except (ImportError, ValueError, KeyError, RuntimeError) as e:
            get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
                "Failed to get limits for owner %s; returning limit=None: %s", owner_user_id, e
            )
            limits = None
        if limits is None:
            limit = None
        else:
            try:
                limit = int(limits.get("concurrent_jobs") or 0)
            except (ValueError, TypeError) as e:
                get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
                    "Could not parse concurrent_jobs limit for owner %s; returning limit=None: %s", owner_user_id, e
                )
                limit = None
        return OwnerProcessingSummary(owner_user_id=str(owner_user_id), processing=processing, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get owner processing summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get owner processing summary")


# --- Admin: user tiers (audio) ---

class UserTierResponse(BaseModel):
    user_id: int
    tier: str


class SetUserTierRequest(BaseModel):
    tier: str = Field(..., description="Tier name (one of: free, standard, premium)")


@router.get(
    "/jobs/admin/tiers/{user_id}",
    response_model=UserTierResponse,
    summary="Get user's audio tier (admin)",
    dependencies=[Depends(require_roles("admin")), Depends(require_permissions(SYSTEM_MAINTENANCE))],
)
async def get_user_tier_admin(user_id: int):
    try:
        tier = await get_user_tier(int(user_id))
        return UserTierResponse(user_id=int(user_id), tier=tier)
    except Exception as e:
        logger.error(f"Failed to get user tier: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user tier")


@router.put(
    "/jobs/admin/tiers/{user_id}",
    response_model=UserTierResponse,
    summary="Set user's audio tier (admin)",
    dependencies=[Depends(require_roles("admin")), Depends(require_permissions(SYSTEM_MAINTENANCE))],
)
async def set_user_tier_admin(user_id: int, req: SetUserTierRequest):
    try:
        tier = req.tier.strip().lower()
        allowed = set(TIER_LIMITS.keys())
        if tier not in allowed:
            raise HTTPException(status_code=400, detail=f"Invalid tier. Allowed: {', '.join(sorted(allowed))}")
        await set_user_tier(int(user_id), tier)
        return UserTierResponse(user_id=int(user_id), tier=tier)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set user tier: {e}")
        raise HTTPException(status_code=500, detail="Failed to set user tier")
