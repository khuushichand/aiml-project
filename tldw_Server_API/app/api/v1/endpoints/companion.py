from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

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
)
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.feature_flags import is_personalization_enabled
from tldw_Server_API.app.core.Personalization.companion_activity import build_manual_check_in_activity


router = APIRouter()


def _ensure_personalization_enabled() -> None:
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")


@router.post(
    "/activity",
    response_model=CompanionActivityItem,
    tags=["companion"],
    status_code=status.HTTP_201_CREATED,
)
async def create_companion_activity(
    payload: CompanionActivityCreate = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionActivityItem:
    _ensure_personalization_enabled()
    dedupe_key = (
        payload.dedupe_key
        or f"{payload.event_type}:{payload.source_type}:{payload.source_id}"
    )
    try:
        event_id = db.insert_companion_activity_event(
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

    log.log_event(
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
)
async def create_companion_check_in(
    payload: CompanionCheckInCreate = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionActivityItem:
    _ensure_personalization_enabled()
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
    event_id = db.insert_companion_activity_event(user_id=log.user_id, **activity_payload)
    log.log_event(
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


@router.get("/activity", response_model=CompanionActivityListResponse, tags=["companion"])
async def list_companion_activity(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionActivityListResponse:
    _ensure_personalization_enabled()
    items, total = db.list_companion_activity_events(log.user_id, limit=limit, offset=offset)
    log.log_event("companion.activity.view", metadata={"count": len(items)})
    return CompanionActivityListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/knowledge", response_model=CompanionKnowledgeListResponse, tags=["companion"])
async def list_companion_knowledge(
    status_filter: str | None = Query("active", alias="status"),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionKnowledgeListResponse:
    _ensure_personalization_enabled()
    items = db.list_companion_knowledge_cards(log.user_id, status=status_filter)
    log.log_event("companion.knowledge.view", metadata={"count": len(items)})
    return CompanionKnowledgeListResponse(items=items, total=len(items))


@router.get("/goals", response_model=CompanionGoalListResponse, tags=["companion"])
async def list_companion_goals(
    status_filter: str | None = Query(None, alias="status"),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionGoalListResponse:
    _ensure_personalization_enabled()
    items = db.list_companion_goals(log.user_id, status=status_filter)
    log.log_event("companion.goals.view", metadata={"count": len(items)})
    return CompanionGoalListResponse(items=items, total=len(items))


@router.post("/goals", response_model=CompanionGoal, tags=["companion"], status_code=status.HTTP_201_CREATED)
async def create_companion_goal(
    payload: CompanionGoalCreate = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionGoal:
    _ensure_personalization_enabled()
    goal_id = db.create_companion_goal(
        user_id=log.user_id,
        title=payload.title,
        description=payload.description,
        goal_type=payload.goal_type,
        config=payload.config,
        progress=payload.progress,
        status=payload.status,
    )
    goal = db.update_companion_goal(goal_id, log.user_id)
    if goal is None:
        raise HTTPException(status_code=500, detail="Failed to load created goal")
    log.log_event(
        "companion.goals.create",
        resource_id=goal_id,
        tags=[payload.goal_type],
        metadata={"status": goal["status"]},
    )
    return CompanionGoal.model_validate(goal)


@router.patch("/goals/{goal_id}", response_model=CompanionGoal, tags=["companion"])
async def update_companion_goal(
    goal_id: str,
    payload: CompanionGoalUpdate = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> CompanionGoal:
    _ensure_personalization_enabled()
    fields = payload.model_dump(exclude_unset=True)
    invalid_null_fields = sorted(
        key for key in ("title", "config", "progress", "status") if key in fields and fields[key] is None
    )
    if invalid_null_fields:
        raise HTTPException(
            status_code=422,
            detail=f"Fields cannot be null: {', '.join(invalid_null_fields)}",
        )
    goal = db.update_companion_goal(goal_id, log.user_id, **fields)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    log.log_event(
        "companion.goals.update",
        resource_id=goal_id,
        tags=[goal["goal_type"], goal["status"]],
        metadata={"updated_fields": sorted(fields.keys())},
    )
    return CompanionGoal.model_validate(goal)
