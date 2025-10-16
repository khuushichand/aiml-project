# tldw_Server_API/app/api/v1/endpoints/personalization.py
# Placeholder endpoints for Personalization feature (opt-in, preferences, memories, explanations)

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.personalization import (
    DetailResponse,
    ExplanationEntry,
    ExplanationListResponse,
    MemoryItem,
    MemoryListResponse,
    OptInRequest,
    PersonalizationProfile,
    PreferencesUpdate,
)
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    get_personalization_db_for_user,
    get_usage_event_logger,
    UsageEventLogger,
)
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB, SemanticMemory
from tldw_Server_API.app.core.feature_flags import is_personalization_enabled


router = APIRouter()


def _default_profile() -> PersonalizationProfile:
    return PersonalizationProfile(
        enabled=True,
        alpha=0.2,
        beta=0.6,
        gamma=0.2,
        recency_half_life_days=14,
        topic_count=0,
        memory_count=0,
        updated_at=datetime.utcnow(),
    )


@router.post("/opt-in", response_model=PersonalizationProfile, tags=["personalization"], status_code=status.HTTP_200_OK)
async def personalization_opt_in(
    payload: OptInRequest = Body(...),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> PersonalizationProfile:
    """Enable/disable personalization for current user (scaffold: returns default)."""
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")
    logger.info(f"Personalization opt-in called: enabled={payload.enabled}")
    try:
        prof_dict = db.update_profile(user_id=log.user_id, enabled=1 if payload.enabled else 0)
        # Map to response
        prof = PersonalizationProfile(
            enabled=bool(prof_dict.get("enabled")),
            alpha=float(prof_dict.get("alpha")),
            beta=float(prof_dict.get("beta")),
            gamma=float(prof_dict.get("gamma")),
            recency_half_life_days=int(prof_dict.get("recency_half_life_days")),
            topic_count=db.topic_counts(log.user_id),
            memory_count=db.memory_counts(log.user_id),
            updated_at=datetime.utcnow(),
        )
        log.log_event("personalization.opt-in", metadata={"enabled": prof.enabled})
        return prof
    except Exception as e:
        logger.warning(f"Opt-in failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update personalization profile")


@router.post("/purge", response_model=DetailResponse, tags=["personalization"], status_code=status.HTTP_200_OK)
async def personalization_purge(
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> DetailResponse:
    """Purge all personalization data for the user (scaffold: no-op)."""
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")
    logger.info("Personalization purge called")
    try:
        counts = db.purge_user(log.user_id)
        return DetailResponse(detail=f"ok: purged {counts}")
    except Exception as e:
        logger.warning(f"Purge failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to purge personalization data")


@router.get("/profile", response_model=PersonalizationProfile, tags=["personalization"], status_code=status.HTTP_200_OK)
async def personalization_profile(
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> PersonalizationProfile:
    """Get current personalization profile (scaffold values)."""
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")
    prof = db.get_or_create_profile(log.user_id)
    out = PersonalizationProfile(
        enabled=bool(prof.get("enabled")),
        alpha=float(prof.get("alpha")),
        beta=float(prof.get("beta")),
        gamma=float(prof.get("gamma")),
        recency_half_life_days=int(prof.get("recency_half_life_days")),
        topic_count=db.topic_counts(log.user_id),
        memory_count=db.memory_counts(log.user_id),
        updated_at=datetime.utcnow(),
    )
    log.log_event("personalization.view")
    return out


@router.post("/preferences", response_model=PersonalizationProfile, tags=["personalization"], status_code=status.HTTP_200_OK)
async def personalization_preferences(
    update: PreferencesUpdate,
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> PersonalizationProfile:
    """Update personalization weights/preferences (scaffold: merges into default)."""
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")
    prof_dict = db.update_profile(log.user_id, **update.model_dump(exclude_none=True))
    return PersonalizationProfile(
        enabled=bool(prof_dict.get("enabled")),
        alpha=float(prof_dict.get("alpha")),
        beta=float(prof_dict.get("beta")),
        gamma=float(prof_dict.get("gamma")),
        recency_half_life_days=int(prof_dict.get("recency_half_life_days")),
        topic_count=db.topic_counts(log.user_id),
        memory_count=db.memory_counts(log.user_id),
        updated_at=datetime.utcnow(),
    )


@router.get("/memories", response_model=MemoryListResponse, tags=["personalization"], status_code=status.HTTP_200_OK)
async def list_memories(
    type: Optional[str] = Query(None, description="semantic|episodic"),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> MemoryListResponse:
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")
    offset = (page - 1) * size
    # Only semantic implemented in scaffold; episodic not yet
    if type and type != "semantic":
        return MemoryListResponse(items=[], total=0, page=page, size=size)
    items, total = db.list_semantic_memories(log.user_id, q=q, limit=size, offset=offset)
    log.log_event("personalization.memories.view", metadata={"count": len(items)})
    return MemoryListResponse(items=items, total=total, page=page, size=size)


@router.post("/memories", response_model=MemoryItem, tags=["personalization"], status_code=status.HTTP_201_CREATED)
async def add_memory(
    item: MemoryItem,
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
    log: UsageEventLogger = Depends(get_usage_event_logger),
) -> MemoryItem:
    """Add or pin a semantic memory (scaffold: echoes)."""
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")
    mem = SemanticMemory(user_id=log.user_id, content=item.content, tags=item.tags, pinned=item.pinned)
    mid = db.add_semantic_memory(mem)
    return MemoryItem(id=mid, type="semantic", content=item.content, pinned=item.pinned, tags=item.tags)


@router.delete("/memories/{memory_id}", response_model=DetailResponse, tags=["personalization"], status_code=status.HTTP_200_OK)
async def delete_memory(memory_id: str, db: PersonalizationDB = Depends(get_personalization_db_for_user)) -> DetailResponse:
    """Delete memory by id (scaffold: no-op)."""
    if not is_personalization_enabled():
        raise HTTPException(status_code=404, detail="Personalization disabled")
    ok = db.delete_memory(memory_id)
    return DetailResponse(detail="ok: deleted" if ok else "no-op: not found")


@router.get("/explanations", response_model=ExplanationListResponse, tags=["personalization"], status_code=status.HTTP_200_OK)
async def list_explanations(limit: int = Query(10, ge=1, le=100)) -> ExplanationListResponse:
    """Return recent personalization explanations (scaffold: returns empty)."""
    return ExplanationListResponse(items=[], total=0)
