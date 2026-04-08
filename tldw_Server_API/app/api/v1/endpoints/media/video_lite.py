from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status

from tldw_Server_API.app.api.v1.API_Deps.v1_endpoint_deps import oauth2_scheme
from tldw_Server_API.app.api.v1.endpoints.media.ingest_jobs import get_job_manager
from tldw_Server_API.app.api.v1.schemas.video_lite_schemas import (
    VideoLiteSourceStateRequest,
    VideoLiteSourceStateResponse,
    VideoLiteWorkspaceResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod
from tldw_Server_API.app.services.video_lite_service import (
    prepare_video_lite_summary_refresh,
    resolve_video_lite_access,
    resolve_video_lite_source_state,
    resolve_video_lite_workspace,
)

router = APIRouter(tags=["Media Processing"])


async def get_optional_request_user(
    request: Request,
    api_key: str | None = Header(None, alias="X-API-KEY"),
    token: str | None = Depends(oauth2_scheme),
) -> User | None:
    try:
        return await get_request_user(request, api_key=api_key, token=token)
    except HTTPException as exc:
        if exc.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
            if str(api_key or "").strip() or str(token or "").strip():
                raise
            return None
        raise


async def get_authenticated_request_user(
    request: Request,
    api_key: str | None = Header(None, alias="X-API-KEY"),
    token: str | None = Depends(oauth2_scheme),
) -> User:
    return await get_request_user(request, api_key=api_key, token=token)


def _request_org_scope(request: Request) -> tuple[int | None, list[int] | None]:
    active_org_id = getattr(request.state, "active_org_id", None)
    org_ids = getattr(request.state, "org_ids", None)
    return active_org_id, org_ids


@router.post(
    "/video-lite/source",
    response_model=VideoLiteSourceStateResponse,
    summary="Resolve a video-lite source key and source state",
)
async def resolve_video_lite_source(
    request: Request,
    payload: VideoLiteSourceStateRequest,
    current_user: User | None = Depends(get_optional_request_user),
    jm: JobManager = Depends(get_job_manager),
) -> VideoLiteSourceStateResponse:
    active_org_id, org_ids = _request_org_scope(request)
    return await resolve_video_lite_source_state(
        payload,
        current_user=current_user,
        active_org_id=active_org_id,
        org_ids=org_ids,
        state=payload.source_state,
        job_manager=jm,
    )


@router.get(
    "/video-lite/workspace/{source_key}",
    response_model=VideoLiteWorkspaceResponse,
    summary="Resolve lightweight workspace state for a video-lite source",
)
async def get_video_lite_workspace(
    source_key: str,
    request: Request,
    source_url: str | None = Query(default=None),
    current_user: User | None = Depends(get_optional_request_user),
    jm: JobManager = Depends(get_job_manager),
) -> VideoLiteWorkspaceResponse:
    active_org_id, org_ids = _request_org_scope(request)
    return await resolve_video_lite_workspace(
        source_key,
        source_url=source_url,
        current_user=current_user,
        active_org_id=active_org_id,
        org_ids=org_ids,
        job_manager=jm,
    )


@router.post(
    "/video-lite/workspace/{source_key}/summary-refresh",
    response_model=VideoLiteWorkspaceResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually re-request a lightweight video summary",
)
async def refresh_video_lite_summary(
    source_key: str,
    request: Request,
    background_tasks: BackgroundTasks,
    source_url: str | None = Query(default=None),
    current_user: User = Depends(get_authenticated_request_user),
    jm: JobManager = Depends(get_job_manager),
) -> VideoLiteWorkspaceResponse:
    active_org_id, org_ids = _request_org_scope(request)
    launcher_access, _entitlement = await resolve_video_lite_access(
        current_user=current_user,
        active_org_id=active_org_id,
        org_ids=org_ids,
    )
    if launcher_access != "allowed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required.",
        )

    workspace = await resolve_video_lite_workspace(
        source_key,
        source_url=source_url,
        current_user=current_user,
        active_org_id=active_org_id,
        org_ids=org_ids,
        job_manager=jm,
    )
    if workspace.state != "ready" or not workspace.transcript:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transcript not ready.",
        )

    prepared = await prepare_video_lite_summary_refresh(
        source_key=source_key,
        source_url=source_url,
        current_user=current_user,
    )
    if prepared:
        background_tasks.add_task(
            video_lite_service_mod.run_video_lite_summary_generation,
            source_key=source_key,
            source_url=source_url,
            current_user=current_user,
        )

    return await resolve_video_lite_workspace(
        source_key,
        source_url=source_url,
        current_user=current_user,
        active_org_id=active_org_id,
        org_ids=org_ids,
        job_manager=jm,
    )
