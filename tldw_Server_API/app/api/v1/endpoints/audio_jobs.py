from __future__ import annotations

from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, root_validator
from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin


router = APIRouter()


class SubmitAudioJobRequest(BaseModel):
    url: Optional[str] = Field(None, description="URL to download audio from")
    local_path: Optional[str] = Field(None, description="Server-local path to an existing audio/video file")
    model: str = Field("whisper-1", description="Transcription model selector")
    perform_chunking: bool = Field(True, description="Whether to chunk the transcript after STT")
    perform_analysis: bool = Field(False, description="Whether to run LLM analysis after chunking")
    api_name: Optional[str] = Field(None, description="LLM provider key for analysis stage")

    @root_validator
    def _validate_inputs(cls, values: Dict[str, Any]) -> Dict[str, Any]:
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
):
    """
    Create an audio job in the Jobs queue. First stage is determined by input:
    - url → audio_download
    - local_path → audio_convert
    """
    try:
        # Determine backend from env similar to jobs admin
        import os
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)

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
        logger.error(f"Failed to submit audio job: {e}")
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
async def get_audio_job(job_id: int, current_user: User = Depends(get_request_user)):
    """
    Return a single audio job if it belongs to the caller (or the caller is admin).
    """
    try:
        import os
        jm = JobManager(backend="postgres" if (os.getenv("JOBS_DB_URL", "").startswith("postgres")) else None,
                        db_url=os.getenv("JOBS_DB_URL"))
        conn = jm._connect()
        try:
            if jm.backend == "postgres":
                with jm._pg_cursor(conn) as cur:
                    cur.execute("SELECT * FROM jobs WHERE id=%s AND domain=%s", (int(job_id), "audio"))
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(status_code=404, detail="Job not found")
                    d = dict(row)
            else:
                row = conn.execute("SELECT * FROM jobs WHERE id=? AND domain=?", (int(job_id), "audio")).fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Job not found")
                d = dict(row)
        finally:
            conn.close()
        # Owner/admin check
        owner = str(d.get("owner_user_id") or "")
        if not (current_user.is_admin or owner == str(current_user.id)):
            raise HTTPException(status_code=403, detail="Not authorized for this job")
        return AudioJob(**{k: d.get(k) for k in AudioJob.model_fields.keys()})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch job: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch job")


class ListAudioJobsResponse(BaseModel):
    jobs: List[AudioJob]


@router.get("/jobs/admin/list", response_model=ListAudioJobsResponse, summary="List audio jobs (admin)")
async def list_audio_jobs_admin(
    status_filter: Optional[str] = Query(None, description="Filter by status: queued|processing|completed|failed|cancelled"),
    owner_user_id: Optional[str] = Query(None, description="Filter by owner user id"),
    limit: int = Query(50, ge=1, le=200),
    _=Depends(require_admin),
):
    try:
        import os
        jm = JobManager(backend="postgres" if (os.getenv("JOBS_DB_URL", "").startswith("postgres")) else None,
                        db_url=os.getenv("JOBS_DB_URL"))
        conn = jm._connect()
        try:
            jobs: List[Dict[str, Any]] = []
            if jm.backend == "postgres":
                q = "SELECT * FROM jobs WHERE domain=%s"
                params: List[Any] = ["audio"]
                if status_filter:
                    q += " AND status=%s"
                    params.append(status_filter)
                if owner_user_id:
                    q += " AND owner_user_id=%s"
                    params.append(str(owner_user_id))
                q += " ORDER BY created_at DESC LIMIT %s"
                params.append(int(limit))
                with jm._pg_cursor(conn) as cur:
                    cur.execute(q, tuple(params))
                    rows = cur.fetchall() or []
                    jobs = [dict(r) for r in rows]
            else:
                q = "SELECT * FROM jobs WHERE domain=?"
                params2: List[Any] = ["audio"]
                if status_filter:
                    q += " AND status=?"
                    params2.append(status_filter)
                if owner_user_id:
                    q += " AND owner_user_id=?"
                    params2.append(str(owner_user_id))
                q += " ORDER BY created_at DESC LIMIT ?"
                params2.append(int(limit))
                cur2 = conn.execute(q, tuple(params2))
                rows = cur2.fetchall() or []
                jobs = [dict(r) for r in rows]
        finally:
            conn.close()
        # Project to model
        out = [AudioJob(**{k: j.get(k) for k in AudioJob.model_fields.keys()}) for j in jobs]
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


@router.get("/jobs/admin/summary", response_model=AudioJobsSummary, summary="Summarize audio jobs by status (admin)")
async def summarize_audio_jobs_admin(
    owner_user_id: Optional[str] = Query(None, description="Optional owner filter"),
    _=Depends(require_admin),
):
    try:
        import os
        jm = JobManager(backend="postgres" if (os.getenv("JOBS_DB_URL", "").startswith("postgres")) else None,
                        db_url=os.getenv("JOBS_DB_URL"))
        conn = jm._connect()
        by_status: Dict[str, int] = {}
        total = 0
        try:
            if jm.backend == "postgres":
                with jm._pg_cursor(conn) as cur:
                    if owner_user_id:
                        cur.execute(
                            "SELECT status, COUNT(*) AS c FROM jobs WHERE domain=%s AND owner_user_id=%s GROUP BY status",
                            ("audio", str(owner_user_id)),
                        )
                    else:
                        cur.execute(
                            "SELECT status, COUNT(*) AS c FROM jobs WHERE domain=%s GROUP BY status",
                            ("audio",),
                        )
                    rows = cur.fetchall() or []
                    for r in rows:
                        by_status[str(r["status"])]= int(r["c"])  # type: ignore[index]
            else:
                if owner_user_id:
                    q = "SELECT status, COUNT(*) FROM jobs WHERE domain=? AND owner_user_id=? GROUP BY status"
                    args = ("audio", str(owner_user_id))
                else:
                    q = "SELECT status, COUNT(*) FROM jobs WHERE domain=? GROUP BY status"
                    args = ("audio",)
                rows = conn.execute(q, args).fetchall() or []
                for r in rows:
                    by_status[str(r[0])] = int(r[1])
        finally:
            conn.close()
        total = sum(by_status.values())
        return AudioJobsSummary(counts_by_status=by_status, total=total, owner_user_id=owner_user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to summarize jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to summarize jobs")


class OwnerProcessingSummary(BaseModel):
    owner_user_id: str
    processing: int
    limit: Optional[int]


@router.get("/jobs/admin/owner/{owner_user_id}/processing", response_model=OwnerProcessingSummary, summary="Get owner's processing count and limit (admin)")
async def owner_processing_summary(
    owner_user_id: str,
    _=Depends(require_admin),
):
    try:
        import os
        jm = JobManager(backend="postgres" if (os.getenv("JOBS_DB_URL", "").startswith("postgres")) else None,
                        db_url=os.getenv("JOBS_DB_URL"))
        # Count processing
        conn = jm._connect()
        processing = 0
        try:
            if jm.backend == "postgres":
                with jm._pg_cursor(conn) as cur:
                    cur.execute(
                        "SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND status='processing' AND owner_user_id=%s",
                        ("audio", str(owner_user_id)),
                    )
                    row = cur.fetchone()
                    processing = int(row["c"]) if row else 0
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM jobs WHERE domain=? AND status='processing' AND owner_user_id=?",
                    ("audio", str(owner_user_id)),
                ).fetchone()
                processing = int(row[0]) if row else 0
        finally:
            conn.close()
        # Limit
        try:
            from tldw_Server_API.app.core.Usage.audio_quota import get_limits_for_user
            limits = await get_limits_for_user(int(owner_user_id))
            limit = int(limits.get("concurrent_jobs") or 0)
        except Exception:
            limit = None
        return OwnerProcessingSummary(owner_user_id=str(owner_user_id), processing=processing, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get owner processing summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get owner processing summary")
