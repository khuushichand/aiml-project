from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.agent_client_protocol import (
    ACPSessionCancelRequest,
    ACPSessionCloseRequest,
    ACPSessionNewRequest,
    ACPSessionNewResponse,
    ACPSessionPromptRequest,
    ACPSessionPromptResponse,
    ACPSessionUpdatesResponse,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.runner_client import (
    get_runner_client,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPResponseError
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    User,
    get_request_user,
)

router = APIRouter(prefix="/acp", tags=["acp"])


@router.post("/sessions/new", response_model=ACPSessionNewResponse)
async def acp_session_new(
    payload: ACPSessionNewRequest,
    user: User = Depends(get_request_user),
) -> ACPSessionNewResponse:
    try:
        client = await get_runner_client()
        session_id = await client.create_session(payload.cwd, payload.mcp_servers)
    except ACPResponseError as exc:
        logger.error("ACP session/new failed for user {}: {}", user.user_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return ACPSessionNewResponse(
        session_id=session_id,
        agent_capabilities=client.agent_capabilities,
    )


@router.post("/sessions/prompt", response_model=ACPSessionPromptResponse)
async def acp_session_prompt(
    payload: ACPSessionPromptRequest,
    user: User = Depends(get_request_user),
) -> ACPSessionPromptResponse:
    try:
        client = await get_runner_client()
        result = await client.prompt(payload.session_id, payload.prompt)
    except ACPResponseError as exc:
        logger.error("ACP session/prompt failed for user {}: {}", user.user_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return ACPSessionPromptResponse(
        stop_reason=result.get("stopReason"),
        raw_result=result,
    )


@router.post("/sessions/cancel")
async def acp_session_cancel(
    payload: ACPSessionCancelRequest,
    user: User = Depends(get_request_user),
) -> dict:
    try:
        client = await get_runner_client()
        await client.cancel(payload.session_id)
    except ACPResponseError as exc:
        logger.error("ACP session/cancel failed for user {}: {}", user.user_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"status": "ok"}


@router.post("/sessions/close")
async def acp_session_close(
    payload: ACPSessionCloseRequest,
    user: User = Depends(get_request_user),
) -> dict:
    try:
        client = await get_runner_client()
        await client.close_session(payload.session_id)
    except ACPResponseError as exc:
        logger.error("ACP session/close failed for user {}: {}", user.user_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"status": "ok"}


@router.get("/sessions/{session_id}/updates", response_model=ACPSessionUpdatesResponse)
async def acp_session_updates(
    session_id: str,
    limit: Optional[int] = Query(default=100, ge=1, le=1000),
    user: User = Depends(get_request_user),
) -> ACPSessionUpdatesResponse:
    client = await get_runner_client()
    updates = client.pop_updates(session_id, limit=limit or 100)
    return ACPSessionUpdatesResponse(updates=updates)
