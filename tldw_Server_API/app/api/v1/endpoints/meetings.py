from __future__ import annotations

from fastapi import APIRouter

from tldw_Server_API.app.api.v1.schemas.meetings_schemas import MeetingHealthResponse

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("/health", response_model=MeetingHealthResponse, openapi_extra={"security": []})
async def meetings_health() -> MeetingHealthResponse:
    return MeetingHealthResponse()
