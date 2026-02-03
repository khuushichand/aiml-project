from __future__ import annotations

from fastapi import APIRouter, Query

from tldw_Server_API.app.services import admin_personalization_service

router = APIRouter()


@router.post("/personalization/consolidate", response_model=dict)
async def trigger_personalization_consolidation(
    user_id: str | None = Query(None, description="User ID to consolidate; defaults to single-user id"),
) -> dict:
    return await admin_personalization_service.trigger_consolidation(user_id=user_id)


@router.get("/personalization/status", response_model=dict)
async def get_personalization_status() -> dict:
    return await admin_personalization_service.get_status()
