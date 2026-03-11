from __future__ import annotations

"""Companion API endpoints for explicit activity, goals, and workspace data."""

import asyncio
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.api.v1.API_Deps.jobs_deps import get_job_manager
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    UsageEventLogger,
    get_personalization_db_for_user,
    get_usage_event_logger,
)
from tldw_Server_API.app.api.v1.schemas.companion import (
    CompanionActivityCreate,
    CompanionActivityListResponse,
    CompanionActivityItem,
    CompanionCheckInCreate,
    CompanionGoal,
    CompanionGoalCreate,
    CompanionGoalListResponse,
    CompanionGoalUpdate,
    CompanionKnowledgeListResponse,
    CompanionLifecycleResponse,
    CompanionPurgeRequest,
    CompanionRebuildRequest,
)
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.feature_flags import is_personalization_enabled
from tldw_Server_API.app.core.Personalization.companion_activity import build_manual_check_in_activity
from tldw_Server_API.app.core.Personalization.companion_lifecycle import purge_companion_scope
from tldw_Server_API.app.core.Personalization.companion_reflection_jobs import (
    COMPANION_REBUILD_JOB_TYPE,
    COMPANION_REFLECTION_DOMAIN,
    companion_reflection_queue,
)


router = APIRouter()


def _ensure_personalization_enabled() -> None:
    """Raise when the companion module is unavailable."""
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")


def _ensure_companion_opt_in(db: PersonalizationDB, user_id: str) -> None:
    """Raise when the user has not explicitly enabled personalization."""
    profile = db.get_or_create_profile(user_id)
    if not bool(profile.get("enabled")):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Enable personalization before using companion.",
        )


@router.post(
    "/activity",
    response_model=CompanionActivityItem,
    tags=["companion"],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rbac_rate_limit("companion.activity.create"))],
)
async def create_companion_activity(
    payload: CompanionActivityCreate = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionActivityItem:
    """Create one explicit companion activity event."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    dedupe_key = (
        payload.dedupe_key
        or f"{payload.event_type}:{payload.source_type}:{payload.source_id}"
    )
    try:
        event_id = await asyncio.to_thread(
            db.insert_companion_activity_event,
            user_id=log.user_id,
            event_type=payload.event_type,
            source_type=payload.source_type,
            source_id=payload.source_id,
            surface=payload.surface,
            dedupe_key=dedupe_key,
            tags=payload.tags,
            provenance=payload.provenance,
            metadata=payload.metadata,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Companion activity already captured",
        ) from exc

    await asyncio.to_thread(
        log.log_event,
        "companion.activity.create",
        resource_id=event_id,
        tags=list(payload.tags or []),
        metadata={"event_type": payload.event_type, "surface": payload.surface},
    )
    return CompanionActivityItem(
        id=event_id,
        event_type=payload.event_type,
        source_type=payload.source_type,
        source_id=payload.source_id,
        surface=payload.surface,
        tags=list(payload.tags or []),
        provenance=dict(payload.provenance),
        metadata=dict(payload.metadata or {}),
        created_at=datetime.now(timezone.utc),
    )


@router.post(
    "/check-ins",
    response_model=CompanionActivityItem,
    tags=["companion"],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rbac_rate_limit("companion.checkins.create"))],
)
async def create_companion_check_in(
    payload: CompanionCheckInCreate = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionActivityItem:
    """Create one manual companion check-in."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    created_at = datetime.now(timezone.utc)
    source_id = f"checkin-{uuid4().hex}"
    activity_payload = build_manual_check_in_activity(
        source_id=source_id,
        title=payload.title,
        summary=payload.summary,
        surface=payload.surface or "companion.workspace",
        tags=payload.tags,
        event_timestamp=created_at.isoformat(),
    )
    event_id = await asyncio.to_thread(
        db.insert_companion_activity_event,
        user_id=log.user_id,
        **activity_payload,
    )
    await asyncio.to_thread(
        log.log_event,
        "companion.checkins.create",
        resource_id=event_id,
        tags=list(activity_payload["tags"] or []),
        metadata={"source_id": source_id},
    )
    return CompanionActivityItem(
        id=event_id,
        event_type=activity_payload["event_type"],
        source_type=activity_payload["source_type"],
        source_id=activity_payload["source_id"],
        surface=activity_payload["surface"],
        tags=list(activity_payload["tags"] or []),
        provenance=dict(activity_payload["provenance"]),
        metadata=dict(activity_payload["metadata"] or {}),
        created_at=created_at,
    )


@router.get(
    "/activity",
    response_model=CompanionActivityListResponse,
    tags=["companion"],
    dependencies=[Depends(rbac_rate_limit("companion.activity.read"))],
)
async def list_companion_activity(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionActivityListResponse:
    """List persisted companion activity events for the current user."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    items, total = await asyncio.to_thread(
        db.list_companion_activity_events,
        log.user_id,
        limit,
        offset,
    )
    await asyncio.to_thread(log.log_event, "companion.activity.view", metadata={"count": len(items)})
    return CompanionActivityListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/knowledge",
    response_model=CompanionKnowledgeListResponse,
    tags=["companion"],
    dependencies=[Depends(rbac_rate_limit("companion.knowledge.read"))],
)
async def list_companion_knowledge(
    status_filter: str | None = Query("active", alias="status"),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionKnowledgeListResponse:
    """List derived companion knowledge cards for the current user."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    items = await asyncio.to_thread(db.list_companion_knowledge_cards, log.user_id, status_filter)
    await asyncio.to_thread(log.log_event, "companion.knowledge.view", metadata={"count": len(items)})
    return CompanionKnowledgeListResponse(items=items, total=len(items))


@router.get(
    "/goals",
    response_model=CompanionGoalListResponse,
    tags=["companion"],
    dependencies=[Depends(rbac_rate_limit("companion.goals.read"))],
)
async def list_companion_goals(
    status_filter: str | None = Query(None, alias="status"),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionGoalListResponse:
    """List companion goals for the current user."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    items = await asyncio.to_thread(db.list_companion_goals, log.user_id, status_filter)
    await asyncio.to_thread(log.log_event, "companion.goals.view", metadata={"count": len(items)})
    return CompanionGoalListResponse(items=items, total=len(items))


@router.post(
    "/goals",
    response_model=CompanionGoal,
    tags=["companion"],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rbac_rate_limit("companion.goals.create"))],
)
async def create_companion_goal(
    payload: CompanionGoalCreate = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionGoal:
    """Create a new companion goal."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    goal_id = await asyncio.to_thread(
        db.create_companion_goal,
        user_id=log.user_id,
        title=payload.title,
        description=payload.description,
        goal_type=payload.goal_type,
        config=payload.config,
        progress=payload.progress,
        status=payload.status,
    )
    goal = await asyncio.to_thread(db.update_companion_goal, goal_id, log.user_id)
    if goal is None:
        raise HTTPException(status_code=500, detail="Failed to load created goal")
    await asyncio.to_thread(
        log.log_event,
        "companion.goals.create",
        resource_id=goal_id,
        tags=[payload.goal_type],
        metadata={"status": goal["status"]},
    )
    return CompanionGoal.model_validate(goal)


@router.patch(
    "/goals/{goal_id}",
    response_model=CompanionGoal,
    tags=["companion"],
    dependencies=[Depends(rbac_rate_limit("companion.goals.update"))],
)
async def update_companion_goal(
    goal_id: str,
    payload: CompanionGoalUpdate = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionGoal:
    """Update a companion goal."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    fields = payload.model_dump(exclude_unset=True)
    invalid_null_fields = sorted(
        key for key in ("title", "config", "progress", "status") if key in fields and fields[key] is None
    )
    if invalid_null_fields:
        raise HTTPException(
            status_code=422,
            detail=f"Fields cannot be null: {', '.join(invalid_null_fields)}",
        )
    goal = await asyncio.to_thread(db.update_companion_goal, goal_id, log.user_id, **fields)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    await asyncio.to_thread(
        log.log_event,
        "companion.goals.update",
        resource_id=goal_id,
        tags=[goal["goal_type"], goal["status"]],
        metadata={"updated_fields": sorted(fields.keys())},
    )
    return CompanionGoal.model_validate(goal)


@router.post(
    "/purge",
    response_model=CompanionLifecycleResponse,
    tags=["companion"],
    dependencies=[Depends(rbac_rate_limit("companion.lifecycle.purge"))],
)
async def purge_companion_data(
    payload: CompanionPurgeRequest = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    collections_db: CollectionsDatabase = Depends(get_collections_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionLifecycleResponse:
    """Purge one rebuildable slice of companion state while preserving explicit activity by default."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    result = await asyncio.to_thread(
        purge_companion_scope,
        user_id=log.user_id,
        scope=payload.scope,
        personalization_db=db,
        collections_db=collections_db,
    )
    await asyncio.to_thread(
        log.log_event,
        "companion.lifecycle.purge",
        tags=[payload.scope],
        metadata={"deleted_counts": result["deleted_counts"]},
    )
    return CompanionLifecycleResponse.model_validate(result)


@router.post(
    "/rebuild",
    response_model=CompanionLifecycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["companion"],
    dependencies=[Depends(rbac_rate_limit("companion.lifecycle.rebuild"))],
)
async def rebuild_companion_data(
    payload: CompanionRebuildRequest = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    jm: JobManager = Depends(get_job_manager),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionLifecycleResponse:
    """Queue a scoped companion rebuild job."""
    _ensure_personalization_enabled()
    await asyncio.to_thread(_ensure_companion_opt_in, db, log.user_id)
    job = await asyncio.to_thread(
        jm.create_job,
        domain=COMPANION_REFLECTION_DOMAIN,
        queue=companion_reflection_queue(),
        job_type=COMPANION_REBUILD_JOB_TYPE,
        payload={"scope": payload.scope, "user_id": log.user_id},
        owner_user_id=str(log.user_id),
        priority=5,
        max_retries=1,
    )
    job_id = job.get("id")
    await asyncio.to_thread(
        log.log_event,
        "companion.lifecycle.rebuild",
        resource_id=None if job_id is None else str(job_id),
        tags=[payload.scope],
        metadata={"job_uuid": job.get("uuid")},
    )
    return CompanionLifecycleResponse(
        status=str(job.get("status") or "queued"),
        scope=payload.scope,
        job_id=None if job_id is None else int(job_id),
        job_uuid=job.get("uuid"),
    )
