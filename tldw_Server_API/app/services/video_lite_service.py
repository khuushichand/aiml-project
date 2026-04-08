from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import parse_qs, urlparse

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.video_lite_schemas import (
    VideoLiteEntitlement,
    VideoLiteLauncherAccess,
    VideoLiteSourceState,
    VideoLiteSourceStateRequest,
    VideoLiteSourceStateResponse,
    VideoLiteSummaryState,
    VideoLiteWorkspaceResponse,
)
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import DEFAULT_LLM_PROVIDER
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.billing_repo import AuthnzBillingRepo
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
from tldw_Server_API.app.core.DB_Management.media_db.api import (
    get_document_version,
    get_latest_transcription,
    get_media_by_url,
    managed_media_database,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Media_Update_lib import process_media_update
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze

_PAID_SUBSCRIPTION_STATUSES = {"active", "trialing", "canceling"}
_VIDEO_LITE_PENDING_JOB_STATUSES = {"queued", "processing"}
_VIDEO_LITE_FAILED_JOB_STATUSES = {"failed", "cancelled", "quarantined"}
VIDEO_LITE_SUMMARY_PROCESSING_MARKER = "[video-lite-summary-processing]"
VIDEO_LITE_SUMMARY_FAILED_PREFIX = "[video-lite-summary-failed] "
_VIDEO_LITE_SUMMARY_PROMPT = (
    "Provide a concise summary of this video transcript. Focus on the main topics, "
    "claims, and takeaways."
)
_VIDEO_LITE_SUMMARY_LOCKS: dict[str, asyncio.Lock] = {}
_VIDEO_LITE_ATTEMPT_RE = re.compile(r":attempt:(\d+)$")


def _host_matches(hostname: str | None, domain: str) -> bool:
    if not hostname:
        return False
    normalized_host = hostname.lower()
    normalized_domain = domain.lower()
    return normalized_host == normalized_domain or normalized_host.endswith(f".{normalized_domain}")


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_int_list(values: Any) -> list[int]:
    if not isinstance(values, (list, tuple, set)):
        return []
    coerced: list[int] = []
    for value in values:
        int_value = _coerce_int(value)
        if int_value is not None:
            coerced.append(int_value)
    return coerced


def normalize_video_lite_source_key(source_url: str) -> str:
    """Return a stable source key for the video-lite contract."""

    raw_value = str(source_url or "").strip()
    if not raw_value:
        return raw_value

    if raw_value.startswith("youtube:"):
        return raw_value

    parsed = urlparse(raw_value)
    host = parsed.hostname
    path = parsed.path.strip("/")

    if _host_matches(host, "youtu.be"):
        video_id = path.split("/", 1)[0].strip()
        return f"youtube:{video_id}" if video_id else raw_value

    if _host_matches(host, "youtube.com") and parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0].strip()
        return f"youtube:{video_id}" if video_id else raw_value

    return raw_value


def _resolve_active_org_id(
    *,
    current_user: Any | None,
    active_org_id: int | None = None,
    org_ids: list[int] | None = None,
) -> int | None:
    explicit_org_id = _coerce_int(active_org_id)
    if explicit_org_id is not None:
        return explicit_org_id

    scoped_org_ids = _coerce_int_list(org_ids)
    if scoped_org_ids:
        return scoped_org_ids[0]

    if current_user is None:
        return None

    for attr_name in ("active_org_id", "org_id"):
        attr_org_id = _coerce_int(getattr(current_user, attr_name, None))
        if attr_org_id is not None:
            return attr_org_id

    current_user_org_ids = _coerce_int_list(getattr(current_user, "org_ids", None))
    if current_user_org_ids:
        return current_user_org_ids[0]

    return None


def _subscription_is_active(subscription: dict[str, Any] | None) -> bool:
    if not subscription:
        return False
    status = str(subscription.get("status", "") or "").strip().lower()
    return status in _PAID_SUBSCRIPTION_STATUSES


def _resolve_video_lite_user_id(current_user: Any | None) -> int | None:
    user_id = _coerce_int(getattr(current_user, "id", None)) if current_user is not None else None
    if user_id is None or user_id < 1:
        return None
    return user_id


def _summary_lock_key(user_id: int, source_key: str) -> str:
    return f"{user_id}:{normalize_video_lite_source_key(source_key)}"


def _get_video_lite_summary_lock(user_id: int, source_key: str) -> asyncio.Lock:
    key = _summary_lock_key(user_id, source_key)
    lock = _VIDEO_LITE_SUMMARY_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _VIDEO_LITE_SUMMARY_LOCKS[key] = lock
    return lock


def _video_lite_source_lookup_candidates(source_key: str, source_url: str | None = None) -> list[str]:
    candidates: list[str] = []

    def _add(value: str | None) -> None:
        candidate = str(value or "").strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    normalized_source_key = normalize_video_lite_source_key(source_key)
    _add(source_url)
    _add(normalized_source_key)
    if normalized_source_key.startswith("youtube:"):
        video_id = normalized_source_key.split(":", 1)[1].strip()
        if video_id:
            _add(f"https://www.youtube.com/watch?v={video_id}")
            _add(f"https://youtu.be/{video_id}")
    return candidates


def _video_lite_ingest_batch_id(user_id: int, source_key: str) -> str:
    normalized_source_key = normalize_video_lite_source_key(source_key)
    return f"video-lite:{user_id}:{normalized_source_key}"


def _video_lite_ingest_idempotency_key(user_id: int, source_key: str, attempt: int) -> str:
    return f"{_video_lite_ingest_batch_id(user_id, source_key)}:attempt:{max(1, int(attempt))}"


def _extract_video_lite_attempt(job: dict[str, Any]) -> int:
    raw_key = str(job.get("idempotency_key") or "").strip()
    matched = _VIDEO_LITE_ATTEMPT_RE.search(raw_key)
    if not matched:
        return 0
    try:
        return int(matched.group(1))
    except (TypeError, ValueError):
        return 0


def _resolve_video_lite_ingest_queue() -> str:
    default_queue = (os.getenv("MEDIA_INGEST_JOBS_DEFAULT_QUEUE") or "default").strip() or "default"
    route_heavy = str(os.getenv("MEDIA_INGEST_JOBS_ROUTE_HEAVY", "true")).strip().lower()
    if route_heavy not in {"1", "true", "yes", "y", "on"}:
        return default_queue
    heavy_queue = (os.getenv("MEDIA_INGEST_JOBS_HEAVY_QUEUE") or "low").strip() or "low"
    return heavy_queue


def _build_video_lite_ingest_payload(
    *,
    source_url: str,
    user_id: int,
    source_key: str,
) -> dict[str, Any]:
    batch_id = _video_lite_ingest_batch_id(user_id, source_key)
    return {
        "batch_id": batch_id,
        "media_type": "video",
        "source": source_url,
        "source_kind": "url",
        "input_ref": source_url,
        "options": {
            "perform_analysis": True,
        },
    }


def _list_video_lite_ingest_jobs(
    job_manager: JobManager | Any | None,
    *,
    user_id: int,
    source_key: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if job_manager is None:
        return []
    jobs = job_manager.list_jobs(
        domain="media_ingest",
        owner_user_id=str(user_id),
        batch_group=_video_lite_ingest_batch_id(user_id, source_key),
        limit=limit,
        sort_by="created_at",
        sort_order="desc",
    )
    if not isinstance(jobs, Sequence):
        return []
    return [dict(job) for job in jobs if isinstance(job, dict)]


def _resolve_video_lite_ingest_state_from_jobs(jobs: Sequence[dict[str, Any]]) -> VideoLiteSourceState | None:
    statuses = {
        str(job.get("status") or "").strip().lower()
        for job in jobs
        if str(job.get("status") or "").strip()
    }
    if statuses & _VIDEO_LITE_PENDING_JOB_STATUSES:
        return "processing"
    if statuses & _VIDEO_LITE_FAILED_JOB_STATUSES:
        return "failed"
    return None


def _next_video_lite_ingest_attempt(jobs: Sequence[dict[str, Any]]) -> int:
    current_attempt = max((_extract_video_lite_attempt(job) for job in jobs), default=0)
    return current_attempt + 1


def _parse_video_lite_summary_content(
    analysis_content: Any,
) -> tuple[VideoLiteSummaryState, str | None]:
    normalized = str(analysis_content or "").strip()
    if not normalized:
        return "not_requested", None
    if normalized == VIDEO_LITE_SUMMARY_PROCESSING_MARKER:
        return "processing", None
    if normalized.startswith(VIDEO_LITE_SUMMARY_FAILED_PREFIX):
        return "failed", None
    return "ready", normalized


def _lookup_video_lite_media(db: Any, source_key: str, source_url: str | None = None) -> dict[str, Any] | None:
    for candidate in _video_lite_source_lookup_candidates(source_key, source_url):
        media = get_media_by_url(
            db,
            candidate,
            include_deleted=False,
            include_trash=False,
        )
        if media:
            return media
    return None


def _load_video_lite_workspace_snapshot(
    user_id: int,
    *,
    source_key: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    db_path = get_user_media_db_path(user_id)
    normalized_source_key = normalize_video_lite_source_key(source_key)
    resolved_source_url = str(source_url or normalized_source_key)

    with managed_media_database(
        client_id=str(user_id),
        db_path=db_path,
        initialize=False,
    ) as db:
        media = _lookup_video_lite_media(db, normalized_source_key, source_url)
        if not media:
            return {
                "source_url": resolved_source_url,
                "source_key": normalized_source_key,
                "state": "not_ingested",
                "transcript": None,
                "summary": None,
                "summary_state": "not_requested",
            }

        media_id = int(media["id"])
        resolved_source_url = str(media.get("url") or resolved_source_url)
        transcript = get_latest_transcription(db, media_id)
        latest_version = get_document_version(
            db,
            media_id=media_id,
            version_number=None,
            include_content=False,
        ) or {}
        summary_state, summary = _parse_video_lite_summary_content(
            latest_version.get("analysis_content")
        )

        return {
            "source_url": resolved_source_url,
            "source_key": normalized_source_key,
            "state": "ready" if transcript else "processing",
            "transcript": transcript,
            "summary": summary,
            "summary_state": summary_state,
        }


async def prepare_video_lite_summary_generation(
    *,
    source_key: str,
    source_url: str | None = None,
    current_user: Any | None = None,
) -> bool:
    user_id = _resolve_video_lite_user_id(current_user)
    if user_id is None:
        return False

    normalized_source_key = normalize_video_lite_source_key(source_key)
    async with _get_video_lite_summary_lock(user_id, normalized_source_key):
        db_path = get_user_media_db_path(user_id)
        with managed_media_database(
            client_id=str(user_id),
            db_path=db_path,
            initialize=False,
        ) as db:
            media = _lookup_video_lite_media(db, normalized_source_key, source_url)
            if not media:
                return False

            media_id = int(media["id"])
            transcript = get_latest_transcription(db, media_id)
            if not transcript:
                return False

            latest_version = get_document_version(
                db,
                media_id=media_id,
                version_number=None,
                include_content=False,
            ) or {}
            summary_state, _ = _parse_video_lite_summary_content(
                latest_version.get("analysis_content")
            )
            if summary_state in {"ready", "processing", "failed"}:
                return False

            process_media_update(
                db,
                media_id=media_id,
                summary=VIDEO_LITE_SUMMARY_PROCESSING_MARKER,
            )
            return True


async def prepare_video_lite_summary_refresh(
    *,
    source_key: str,
    source_url: str | None = None,
    current_user: Any | None = None,
) -> bool:
    user_id = _resolve_video_lite_user_id(current_user)
    if user_id is None:
        return False

    normalized_source_key = normalize_video_lite_source_key(source_key)
    async with _get_video_lite_summary_lock(user_id, normalized_source_key):
        db_path = get_user_media_db_path(user_id)
        with managed_media_database(
            client_id=str(user_id),
            db_path=db_path,
            initialize=False,
        ) as db:
            media = _lookup_video_lite_media(db, normalized_source_key, source_url)
            if not media:
                return False

            media_id = int(media["id"])
            transcript = get_latest_transcription(db, media_id)
            if not transcript:
                return False

            latest_version = get_document_version(
                db,
                media_id=media_id,
                version_number=None,
                include_content=False,
            ) or {}
            summary_state, _ = _parse_video_lite_summary_content(
                latest_version.get("analysis_content")
            )
            if summary_state == "processing":
                return False

            process_media_update(
                db,
                media_id=media_id,
                summary=VIDEO_LITE_SUMMARY_PROCESSING_MARKER,
            )
            return True


async def generate_video_lite_summary_text(transcript: str, *, source_key: str) -> str:
    _ = source_key
    provider = str(DEFAULT_LLM_PROVIDER or "openai").strip().lower() or "openai"
    summary_result = await asyncio.to_thread(
        analyze,
        provider,
        transcript,
        _VIDEO_LITE_SUMMARY_PROMPT,
    )
    summary_text = str(summary_result or "").strip()
    if not summary_text or summary_text.lower().startswith("error:"):
        raise ValueError(summary_text or "summary generation failed")
    return summary_text


async def run_video_lite_summary_generation(
    *,
    source_key: str,
    source_url: str | None = None,
    current_user: Any | None = None,
) -> bool:
    user_id = _resolve_video_lite_user_id(current_user)
    if user_id is None:
        return False

    normalized_source_key = normalize_video_lite_source_key(source_key)
    async with _get_video_lite_summary_lock(user_id, normalized_source_key):
        db_path = get_user_media_db_path(user_id)
        with managed_media_database(
            client_id=str(user_id),
            db_path=db_path,
            initialize=False,
        ) as db:
            media = _lookup_video_lite_media(db, normalized_source_key, source_url)
            if not media:
                return False

            media_id = int(media["id"])
            transcript = get_latest_transcription(db, media_id)
            if not transcript:
                return False

            latest_version = get_document_version(
                db,
                media_id=media_id,
                version_number=None,
                include_content=False,
            ) or {}
            summary_state, _ = _parse_video_lite_summary_content(
                latest_version.get("analysis_content")
            )
            if summary_state in {"ready", "failed"}:
                return False

            if summary_state == "not_requested":
                process_media_update(
                    db,
                    media_id=media_id,
                    summary=VIDEO_LITE_SUMMARY_PROCESSING_MARKER,
                )

        try:
            summary_text = await generate_video_lite_summary_text(
                transcript,
                source_key=normalized_source_key,
            )
        except Exception as exc:
            failure_reason = str(exc).strip() or "summary generation failed"
            logger.warning(
                "Video-lite summary generation failed for {}: {}",
                normalized_source_key,
                failure_reason,
            )
            with managed_media_database(
                client_id=str(user_id),
                db_path=db_path,
                initialize=False,
            ) as db:
                media = _lookup_video_lite_media(db, normalized_source_key, source_url)
                if not media:
                    return False
                process_media_update(
                    db,
                    media_id=int(media["id"]),
                    summary=f"{VIDEO_LITE_SUMMARY_FAILED_PREFIX}{failure_reason}",
                )
            return False

        with managed_media_database(
            client_id=str(user_id),
            db_path=db_path,
            initialize=False,
        ) as db:
            media = _lookup_video_lite_media(db, normalized_source_key, source_url)
            if not media:
                return False
            process_media_update(
                db,
                media_id=int(media["id"]),
                summary=summary_text,
            )
        return True


async def get_video_lite_billing_repo(db_pool: DatabasePool | None = None) -> AuthnzBillingRepo:
    """Return the AuthNZ billing repository for the configured pool."""

    pool = db_pool or await get_db_pool()
    return AuthnzBillingRepo(pool)


def enqueue_video_lite_ingest_job(
    *,
    job_manager: JobManager | Any | None,
    user_id: int,
    source_key: str,
    source_url: str,
) -> dict[str, Any] | None:
    """Create or reuse the current video-lite ingest attempt for this user/source."""

    if job_manager is None:
        return None

    normalized_source_key = normalize_video_lite_source_key(source_key)
    existing_jobs = _list_video_lite_ingest_jobs(
        job_manager,
        user_id=user_id,
        source_key=normalized_source_key,
    )
    existing_state = _resolve_video_lite_ingest_state_from_jobs(existing_jobs)
    if existing_state == "processing":
        return existing_jobs[0] if existing_jobs else None

    attempt = _next_video_lite_ingest_attempt(existing_jobs)
    batch_id = _video_lite_ingest_batch_id(user_id, normalized_source_key)
    return job_manager.create_job(
        domain="media_ingest",
        queue=_resolve_video_lite_ingest_queue(),
        job_type="media_ingest_item",
        payload=_build_video_lite_ingest_payload(
            source_url=source_url,
            user_id=user_id,
            source_key=normalized_source_key,
        ),
        owner_user_id=str(user_id),
        batch_group=batch_id,
        priority=5,
        max_retries=3,
        idempotency_key=_video_lite_ingest_idempotency_key(
            user_id,
            normalized_source_key,
            attempt,
        ),
    )


async def resolve_video_lite_access(
    *,
    current_user: Any | None,
    active_org_id: int | None = None,
    org_ids: list[int] | None = None,
    db_pool: DatabasePool | None = None,
    billing_repo: AuthnzBillingRepo | None = None,
) -> tuple[VideoLiteLauncherAccess, VideoLiteEntitlement]:
    """Resolve launcher access and entitlement for the video-lite contract."""

    if current_user is None:
        return "login_required", "signed_out"

    resolved_org_id = _resolve_active_org_id(
        current_user=current_user,
        active_org_id=active_org_id,
        org_ids=org_ids,
    )
    if resolved_org_id is None:
        return "subscription_required", "signed_in_unsubscribed"

    repo = billing_repo or await get_video_lite_billing_repo(db_pool)
    subscription = await repo.get_org_subscription(resolved_org_id)
    if _subscription_is_active(subscription):
        return "allowed", "signed_in_subscribed"
    return "subscription_required", "signed_in_unsubscribed"


async def resolve_video_lite_source_state(
    request: VideoLiteSourceStateRequest,
    *,
    current_user: Any | None = None,
    active_org_id: int | None = None,
    org_ids: list[int] | None = None,
    state: VideoLiteSourceState = "not_ingested",
    db_pool: DatabasePool | None = None,
    billing_repo: AuthnzBillingRepo | None = None,
    job_manager: JobManager | Any | None = None,
) -> VideoLiteSourceStateResponse:
    """Resolve the current source state and kick off ingest when needed."""

    source_url = str(request.source_url).strip()
    source_key = normalize_video_lite_source_key(source_url)
    launcher_access, entitlement = await resolve_video_lite_access(
        current_user=current_user,
        active_org_id=active_org_id,
        org_ids=org_ids,
        db_pool=db_pool,
        billing_repo=billing_repo,
    )
    effective_state: VideoLiteSourceState = "not_ingested"
    if launcher_access == "allowed":
        user_id = _resolve_video_lite_user_id(current_user)
        if user_id is not None:
            workspace_snapshot = _load_video_lite_workspace_snapshot(
                user_id,
                source_key=source_key,
                source_url=source_url,
            )
            workspace_state = workspace_snapshot["state"]
            if workspace_state in {"ready", "processing"}:
                effective_state = workspace_state
            else:
                pending_jobs = _list_video_lite_ingest_jobs(
                    job_manager,
                    user_id=user_id,
                    source_key=source_key,
                )
                pending_state = _resolve_video_lite_ingest_state_from_jobs(pending_jobs)
                if pending_state == "processing":
                    effective_state = "processing"
                else:
                    enqueue_video_lite_ingest_job(
                        job_manager=job_manager,
                        user_id=user_id,
                        source_key=source_key,
                        source_url=source_url,
                    )
                    effective_state = "processing"
        else:
            effective_state = state

    return VideoLiteSourceStateResponse(
        source_url=source_url,
        source_key=source_key,
        state=effective_state,
        target_tab=request.target_tab,
        launcher_access=launcher_access,
        entitlement=entitlement,
    )


async def resolve_video_lite_workspace(
    source_key: str,
    *,
    source_url: str | None = None,
    current_user: Any | None = None,
    active_org_id: int | None = None,
    org_ids: list[int] | None = None,
    state: VideoLiteSourceState = "not_ingested",
    db_pool: DatabasePool | None = None,
    billing_repo: AuthnzBillingRepo | None = None,
    job_manager: JobManager | Any | None = None,
) -> VideoLiteWorkspaceResponse:
    """Resolve the current workspace state for the lightweight video contract."""

    normalized_source_key = normalize_video_lite_source_key(source_key)
    launcher_access, entitlement = await resolve_video_lite_access(
        current_user=current_user,
        active_org_id=active_org_id,
        org_ids=org_ids,
        db_pool=db_pool,
        billing_repo=billing_repo,
    )
    if launcher_access != "allowed":
        return VideoLiteWorkspaceResponse(
            source_url=str(source_url or normalized_source_key),
            source_key=normalized_source_key,
            state="not_ingested",
            transcript=None,
            summary=None,
            summary_state="not_requested",
            entitlement=entitlement,
        )

    user_id = _resolve_video_lite_user_id(current_user)
    if user_id is None:
        return VideoLiteWorkspaceResponse(
            source_url=str(source_url or normalized_source_key),
            source_key=normalized_source_key,
            state="not_ingested",
            transcript=None,
            summary=None,
            summary_state="not_requested",
            entitlement=entitlement,
        )

    workspace_snapshot = _load_video_lite_workspace_snapshot(
        user_id,
        source_key=normalized_source_key,
        source_url=source_url,
    )
    workspace_state = workspace_snapshot["state"]
    if workspace_state == "not_ingested":
        pending_jobs = _list_video_lite_ingest_jobs(
            job_manager,
            user_id=user_id,
            source_key=normalized_source_key,
        )
        pending_state = _resolve_video_lite_ingest_state_from_jobs(pending_jobs)
        if pending_state is not None:
            workspace_state = pending_state

    return VideoLiteWorkspaceResponse(
        source_url=str(workspace_snapshot["source_url"]),
        source_key=normalized_source_key,
        state=workspace_state,
        transcript=workspace_snapshot["transcript"],
        summary=workspace_snapshot["summary"],
        summary_state=workspace_snapshot["summary_state"],
        entitlement=entitlement,
    )
