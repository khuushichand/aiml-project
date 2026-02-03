from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.agent_client_protocol import (
    ACPAgentInfo,
    ACPAgentListResponse,
    ACPAgentType,
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
from tldw_Server_API.app.core.AuthNZ.JWT_Manager import get_jwt_manager
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    User,
    get_request_user,
)
from tldw_Server_API.app.core.Streaming.streams import WebSocketStream

router = APIRouter(prefix="/acp", tags=["acp"])


# -----------------------------------------------------------------------------
# WebSocket Authentication Helper
# -----------------------------------------------------------------------------


async def _authenticate_ws(
    websocket: WebSocket,
    token: str | None = None,
    api_key: str | None = None,
) -> int | None:
    """Authenticate a WebSocket connection. Returns user_id or None."""
    # Try JWT token first
    if token:
        try:
            jwtm = get_jwt_manager()
            token_data = jwtm.verify_token(token)
            if token_data and token_data.user_id:
                return token_data.user_id
        except Exception as e:
            logger.debug("JWT auth failed for WebSocket: {}", e)

    # Try API key (single-user mode)
    if api_key:
        try:
            import os
            expected_key = os.getenv("SINGLE_USER_API_KEY", "")
            if expected_key and api_key == expected_key:
                return 1  # Single-user mode user ID
        except Exception as e:
            logger.debug("API key auth failed for WebSocket: {}", e)

    # Try Authorization header
    auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth_header:
        if auth_header.lower().startswith("bearer "):
            return await _authenticate_ws(websocket, token=auth_header[7:].strip())
        elif auth_header.lower().startswith("x-api-key "):
            return await _authenticate_ws(websocket, api_key=auth_header[10:].strip())

    return None


# -----------------------------------------------------------------------------
# WebSocket Endpoint
# -----------------------------------------------------------------------------


@router.websocket("/sessions/{session_id}/stream")
async def acp_session_stream(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(None),
    api_key: str | None = Query(None),
) -> None:
    """
    WebSocket endpoint for real-time ACP session updates.

    Message types (Server → Client):
    - connected: Connection established
    - update: Session update from agent
    - permission_request: Permission required for tool execution
    - error: Error occurred
    - prompt_complete: Prompt execution completed

    Message types (Client → Server):
    - permission_response: Approve/deny permission request
    - cancel: Cancel current operation
    - prompt: Send a new prompt (alternative to REST endpoint)

    Authentication:
    - Pass token as query param: ?token=<jwt>
    - Pass api_key as query param: ?api_key=<key>
    - Or via Authorization header: Bearer <token>
    """
    # Authenticate
    user_id = await _authenticate_ws(websocket, token=token, api_key=api_key)
    if user_id is None:
        try:
            await websocket.close(code=4401)
        except Exception:
            pass
        return

    # Set up WebSocket stream wrapper for metrics
    stream = WebSocketStream(
        websocket,
        heartbeat_interval_s=30.0,
        idle_timeout_s=None,  # No idle timeout for ACP sessions
        close_on_done=False,
        labels={"component": "acp", "endpoint": "acp_session_stream"},
    )

    try:
        await stream.start()

        # Get runner client
        client = await get_runner_client()

        # Define send callback for broadcasting
        async def send_callback(message: dict[str, Any]) -> None:
            await stream.send_json(message)

        # Register this WebSocket with the session
        await client.register_websocket(session_id, send_callback)

        # Send connected message
        await stream.send_json({
            "type": "connected",
            "session_id": session_id,
            "agent_capabilities": client.agent_capabilities,
        })

        logger.info("WebSocket connected for ACP session {} (user={})", session_id, user_id)

        # Main message loop
        while True:
            try:
                data = await stream.receive_json()
                await _handle_client_message(client, session_id, data, stream)
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected for ACP session {}", session_id)
                break
            except json.JSONDecodeError as e:
                await stream.send_json({
                    "type": "error",
                    "code": "invalid_json",
                    "message": f"Invalid JSON: {e}",
                    "session_id": session_id,
                })
            except Exception as e:
                logger.exception("Error handling WebSocket message for session {}", session_id)
                await stream.send_json({
                    "type": "error",
                    "code": "internal_error",
                    "message": str(e),
                    "session_id": session_id,
                })

    except Exception as e:
        logger.exception("WebSocket error for ACP session {}", session_id)
    finally:
        # Unregister WebSocket
        try:
            client = await get_runner_client()
            await client.unregister_websocket(session_id, send_callback)
        except Exception:
            pass
        await stream.stop()


async def _handle_client_message(
    client: Any,
    session_id: str,
    data: dict[str, Any],
    stream: WebSocketStream,
) -> None:
    """Handle a message from the WebSocket client."""
    msg_type = data.get("type")

    if msg_type == "permission_response":
        request_id = data.get("request_id")
        approved = data.get("approved", False)
        batch_approve_tier = data.get("batch_approve_tier")

        if not request_id:
            await stream.send_json({
                "type": "error",
                "code": "missing_request_id",
                "message": "permission_response requires request_id",
                "session_id": session_id,
            })
            return

        success = await client.respond_to_permission(
            session_id,
            request_id,
            approved,
            batch_approve_tier,
        )
        if not success:
            await stream.send_json({
                "type": "error",
                "code": "permission_not_found",
                "message": f"Permission request {request_id} not found",
                "session_id": session_id,
            })

    elif msg_type == "cancel":
        try:
            await client.cancel(session_id)
            await stream.send_json({
                "type": "update",
                "session_id": session_id,
                "update_type": "cancelled",
                "data": {"message": "Operation cancelled"},
            })
        except ACPResponseError as e:
            await stream.send_json({
                "type": "error",
                "code": "cancel_failed",
                "message": str(e),
                "session_id": session_id,
            })

    elif msg_type == "prompt":
        prompt = data.get("prompt", [])
        if not prompt:
            await stream.send_json({
                "type": "error",
                "code": "missing_prompt",
                "message": "prompt message requires prompt array",
                "session_id": session_id,
            })
            return

        try:
            result = await client.prompt(session_id, prompt)
            await stream.send_json({
                "type": "prompt_complete",
                "session_id": session_id,
                "stop_reason": result.get("stopReason"),
                "raw_result": result,
            })
        except ACPResponseError as e:
            await stream.send_json({
                "type": "error",
                "code": "prompt_failed",
                "message": str(e),
                "session_id": session_id,
            })

    else:
        await stream.send_json({
            "type": "error",
            "code": "unknown_message_type",
            "message": f"Unknown message type: {msg_type}",
            "session_id": session_id,
        })


def _get_available_agents() -> list[ACPAgentInfo]:
    """Get list of available agents and their configuration status."""
    import os

    agents = []

    # Claude Code (requires ANTHROPIC_API_KEY)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    agents.append(
        ACPAgentInfo(
            type=ACPAgentType.CLAUDE_CODE,
            name="Claude Code",
            description="Anthropic's Claude Code agent for software development tasks",
            is_configured=bool(anthropic_key),
            requires_api_key="ANTHROPIC_API_KEY" if not anthropic_key else None,
        )
    )

    # Codex (requires OPENAI_API_KEY)
    openai_key = os.getenv("OPENAI_API_KEY", "")
    agents.append(
        ACPAgentInfo(
            type=ACPAgentType.CODEX,
            name="OpenAI Codex",
            description="OpenAI's Codex agent for code generation and analysis",
            is_configured=bool(openai_key),
            requires_api_key="OPENAI_API_KEY" if not openai_key else None,
        )
    )

    # OpenCode (open-source, runs locally - always available)
    agents.append(
        ACPAgentInfo(
            type=ACPAgentType.OPENCODE,
            name="OpenCode",
            description="Open-source coding agent (github.com/sst/opencode)",
            is_configured=True,
            requires_api_key=None,
        )
    )

    # Custom (always available)
    agents.append(
        ACPAgentInfo(
            type=ACPAgentType.CUSTOM,
            name="Custom Agent",
            description="Configure a custom agent with your own settings",
            is_configured=True,
            requires_api_key=None,
        )
    )

    return agents


@router.get("/agents", response_model=ACPAgentListResponse)
async def acp_list_agents(
    user: User = Depends(get_request_user),
) -> ACPAgentListResponse:
    """
    List available ACP agents and their configuration status.

    Returns information about which agents are available and properly configured.
    """
    agents = _get_available_agents()
    return ACPAgentListResponse(
        agents=agents,
        default_agent=ACPAgentType.CLAUDE_CODE,
    )


def _generate_session_name(cwd: str) -> str:
    """Generate a session name from the working directory."""
    from datetime import datetime

    # Extract project name from cwd
    parts = cwd.rstrip("/").split("/")
    project_name = parts[-1] if parts else "Session"

    # Add time stamp
    time_str = datetime.now().strftime("%H:%M")

    return f"{project_name} ({time_str})"


@router.post("/sessions/new", response_model=ACPSessionNewResponse)
async def acp_session_new(
    payload: ACPSessionNewRequest,
    user: User = Depends(get_request_user),
) -> ACPSessionNewResponse:
    """
    Create a new ACP session.

    Optionally specify a session name, agent type, tags, and MCP server configs.
    """
    # Generate session name if not provided
    session_name = payload.name or _generate_session_name(payload.cwd)

    # Convert MCP server configs to dicts for the runner client
    mcp_servers_dicts = None
    if payload.mcp_servers:
        mcp_servers_dicts = [
            server.model_dump(exclude_none=True) for server in payload.mcp_servers
        ]

    try:
        client = await get_runner_client()
        session_id = await client.create_session(
            payload.cwd,
            mcp_servers_dicts,
            agent_type=payload.agent_type.value,
        )
    except ACPResponseError as exc:
        logger.error("ACP session/new failed for user {}: {}", user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return ACPSessionNewResponse(
        session_id=session_id,
        name=session_name,
        agent_type=payload.agent_type,
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
        logger.error("ACP session/prompt failed for user {}: {}", user.id, exc)
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
        logger.error("ACP session/cancel failed for user {}: {}", user.id, exc)
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
        logger.error("ACP session/close failed for user {}: {}", user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"status": "ok"}


@router.get("/sessions/{session_id}/updates", response_model=ACPSessionUpdatesResponse)
async def acp_session_updates(
    session_id: str,
    limit: int | None = Query(default=100, ge=1, le=1000),
    user: User = Depends(get_request_user),
) -> ACPSessionUpdatesResponse:
    client = await get_runner_client()
    updates = client.pop_updates(session_id, limit=limit or 100)
    return ACPSessionUpdatesResponse(updates=updates)
