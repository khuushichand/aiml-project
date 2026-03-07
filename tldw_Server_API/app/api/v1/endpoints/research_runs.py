"""API routes for deep research session lifecycle management."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from tldw_Server_API.app.api.v1.schemas.research_runs_schemas import (
    ResearchCheckpointPatchApproveRequest,
    ResearchRunCreateRequest,
    ResearchRunResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Research.service import ResearchService

router = APIRouter(prefix="/research", tags=["research-runs"])


def get_research_service() -> ResearchService:
    """Return the default deep research service."""
    return ResearchService(research_db_path=None, outputs_dir=None, job_manager=None)


@router.post("/runs", response_model=ResearchRunResponse, summary="Create a deep research run")
async def create_research_run(
    payload: ResearchRunCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    service: ResearchService = Depends(get_research_service),
) -> ResearchRunResponse:
    session = service.create_session(
        owner_user_id=str(current_user.id),
        query=payload.query,
        source_policy=payload.source_policy,
        autonomy_mode=payload.autonomy_mode,
        limits_json=payload.limits_json,
    )
    return ResearchRunResponse.model_validate(session)


@router.post(
    "/runs/{session_id}/checkpoints/{checkpoint_id}/patch-and-approve",
    response_model=ResearchRunResponse,
    summary="Patch and approve a deep research checkpoint",
)
async def patch_and_approve_research_checkpoint(
    session_id: str = Path(..., min_length=1),
    checkpoint_id: str = Path(..., min_length=1),
    payload: ResearchCheckpointPatchApproveRequest = Body(default_factory=ResearchCheckpointPatchApproveRequest),
    current_user: User = Depends(get_request_user),
    service: ResearchService = Depends(get_research_service),
) -> ResearchRunResponse:
    try:
        session = service.approve_checkpoint(
            owner_user_id=str(current_user.id),
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            patch_payload=payload.patch_payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"research_not_found:{exc.args[0]}") from None
    return ResearchRunResponse.model_validate(session)
