from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import os
import threading
import tempfile
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.agent_client_protocol import (
    ACPAgentInfo,
    ACPAgentListResponse,
    ACPSessionCancelRequest,
    ACPSessionCloseRequest,
    ACPSessionDetailResponse,
    ACPSessionForkRequest,
    ACPSessionForkResponse,
    ACPSessionInfo,
    ACPSessionListResponse,
    ACPSessionNewRequest,
    ACPSessionNewResponse,
    ACPSessionPromptRequest,
    ACPSessionPromptResponse,
    ACPSessionUpdatesResponse,
    ACPSessionUsageResponse,
    ACPTokenUsage,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.runner_client import (
    get_runner_client,
)
from tldw_Server_API.app.services.admin_acp_sessions_service import get_acp_session_store
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPResponseError
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
from tldw_Server_API.app.core.AuthNZ.ip_allowlist import is_single_user_ip_allowed, resolve_client_ip
from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
from tldw_Server_API.app.core.AuthNZ.settings import get_settings as get_auth_settings
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    User,
    get_request_user,
)
from tldw_Server_API.app.core.Streaming.streams import WebSocketStream
from tldw_Server_API.app.core.testing import is_explicit_pytest_runtime

router = APIRouter(prefix="/acp", tags=["acp"])

_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS = (
    ACPResponseError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    json.JSONDecodeError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TokenExpiredError,
    TypeError,
    UnicodeDecodeError,
    InvalidTokenError,
    ValueError,
)

_ACP_WS_QUOTA_LOCK = threading.Lock()
_ACP_WS_ACTIVE_TOTAL = 0
_ACP_WS_ACTIVE_BY_USER: dict[str, int] = {}
_ACP_WS_ACTIVE_BY_PERSONA: dict[str, int] = {}
_ACP_WS_ACTIVE_BY_SESSION: dict[str, int] = {}


def _acp_ws_limit(env_key: str, default: int) -> int:
    try:
        return int(os.getenv(env_key, str(default)))
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        return int(default)


def _acp_quota_inc(bucket: dict[str, int], key: str | None) -> None:
    if key is None:
        return
    bucket[key] = int(bucket.get(key, 0)) + 1


def _acp_quota_dec(bucket: dict[str, int], key: str | None) -> None:
    if key is None:
        return
    current = int(bucket.get(key, 0))
    if current <= 1:
        bucket.pop(key, None)
    else:
        bucket[key] = current - 1


def _acp_ws_try_acquire_quota(
    *,
    user_id: int,
    session_id: str,
    persona_id: str | None,
) -> tuple[dict[str, str | None] | None, str | None]:
    global _ACP_WS_ACTIVE_TOTAL
    total_limit = _acp_ws_limit("ACP_WS_MAX_CONNECTIONS_TOTAL", 1024)
    per_user_limit = _acp_ws_limit("ACP_WS_MAX_CONNECTIONS_PER_USER", 64)
    per_persona_limit = _acp_ws_limit("ACP_WS_MAX_CONNECTIONS_PER_PERSONA", 32)
    per_session_limit = _acp_ws_limit("ACP_WS_MAX_CONNECTIONS_PER_SESSION", 16)

    user_key = str(user_id)
    session_key = str(session_id).strip() if session_id else None
    persona_key = str(persona_id).strip() if persona_id else None

    with _ACP_WS_QUOTA_LOCK:
        if total_limit > 0 and _ACP_WS_ACTIVE_TOTAL >= total_limit:
            return None, "total_connections_quota_exceeded"
        if per_user_limit > 0 and int(_ACP_WS_ACTIVE_BY_USER.get(user_key, 0)) >= per_user_limit:
            return None, "user_connections_quota_exceeded"
        if persona_key and per_persona_limit > 0 and int(_ACP_WS_ACTIVE_BY_PERSONA.get(persona_key, 0)) >= per_persona_limit:
            return None, "persona_connections_quota_exceeded"
        if session_key and per_session_limit > 0 and int(_ACP_WS_ACTIVE_BY_SESSION.get(session_key, 0)) >= per_session_limit:
            return None, "session_connections_quota_exceeded"

        _ACP_WS_ACTIVE_TOTAL += 1
        _acp_quota_inc(_ACP_WS_ACTIVE_BY_USER, user_key)
        _acp_quota_inc(_ACP_WS_ACTIVE_BY_PERSONA, persona_key)
        _acp_quota_inc(_ACP_WS_ACTIVE_BY_SESSION, session_key)
        return {
            "user_key": user_key,
            "persona_key": persona_key,
            "session_key": session_key,
        }, None


def _acp_ws_release_quota(token: dict[str, str | None] | None) -> None:
    global _ACP_WS_ACTIVE_TOTAL
    if not token:
        return
    with _ACP_WS_QUOTA_LOCK:
        if _ACP_WS_ACTIVE_TOTAL > 0:
            _ACP_WS_ACTIVE_TOTAL -= 1
        _acp_quota_dec(_ACP_WS_ACTIVE_BY_USER, token.get("user_key"))
        _acp_quota_dec(_ACP_WS_ACTIVE_BY_PERSONA, token.get("persona_key"))
        _acp_quota_dec(_ACP_WS_ACTIVE_BY_SESSION, token.get("session_key"))


async def _resolve_acp_session_persona_id(client: Any, session_id: str, user_id: int) -> str | None:
    getter = getattr(client, "get_session_metadata", None)
    if not callable(getter):
        return None
    try:
        metadata = await getter(session_id, user_id=user_id)
    except TypeError:
        metadata = await getter(session_id)
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        return None
    if not isinstance(metadata, dict):
        return None
    persona_id = metadata.get("persona_id")
    if persona_id is None:
        return None
    return str(persona_id)


# -----------------------------------------------------------------------------
# WebSocket Authentication Helper
# -----------------------------------------------------------------------------

class _AuthNZJWTManagerCompat:
    """Compatibility shim exposing verify_token() with token_data.user_id."""

    async def verify_token(self, token: str) -> SimpleNamespace | None:
        try:
            payload = get_jwt_service().decode_access_token(token)
            session_manager = await get_session_manager()
            if await session_manager.is_token_blacklisted(token, payload.get("jti")):
                return None
            user_id = payload.get("user_id") or payload.get("sub")
            if user_id is None:
                return None
            return SimpleNamespace(user_id=int(user_id))
        except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
            return None


def get_jwt_manager() -> _AuthNZJWTManagerCompat:
    """Return a compatibility JWT manager for ACP WebSocket auth and legacy tests."""
    return _AuthNZJWTManagerCompat()


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
            if inspect.isawaitable(token_data):
                token_data = await token_data
            if token_data and getattr(token_data, "user_id", None):
                return int(token_data.user_id)
        except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS as e:
            logger.debug("JWT auth failed for WebSocket: {}", e)

    # Try API key (single-user mode)
    if api_key:
        try:
            settings = get_auth_settings()
            auth_mode = str(getattr(settings, "AUTH_MODE", "single_user")).strip().lower()
            client_ip = resolve_client_ip(websocket, settings)
            if auth_mode == "single_user":
                allowed_keys: set[str] = set()
                primary_key = getattr(settings, "SINGLE_USER_API_KEY", None)
                if isinstance(primary_key, str) and primary_key.strip():
                    allowed_keys.add(primary_key.strip())
                env_primary = os.getenv("SINGLE_USER_API_KEY") or os.getenv("API_KEY")
                if isinstance(env_primary, str) and env_primary.strip():
                    allowed_keys.add(env_primary.strip())
                if is_explicit_pytest_runtime():
                    test_key = os.getenv("SINGLE_USER_TEST_API_KEY")
                    if isinstance(test_key, str) and test_key.strip():
                        allowed_keys.add(test_key.strip())
                if api_key in allowed_keys and is_single_user_ip_allowed(client_ip, settings):
                    return int(getattr(settings, "SINGLE_USER_FIXED_ID", 1))
            else:
                api_mgr = await get_api_key_manager()
                info = await api_mgr.validate_api_key(
                    api_key=api_key,
                    required_scope="read",
                    ip_address=client_ip,
                )
                user_id = info.get("user_id") if isinstance(info, dict) else None
                if user_id is not None:
                    return int(user_id)
        except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS as e:
            logger.debug("API key auth failed for WebSocket: {}", e)

    # Try Authorization header
    auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth_header:
        if auth_header.lower().startswith("bearer "):
            return await _authenticate_ws(websocket, token=auth_header[7:].strip())
        elif auth_header.lower().startswith("x-api-key "):
            return await _authenticate_ws(websocket, api_key=auth_header[10:].strip())

    # Try Sec-WebSocket-Protocol: bearer,<token> or x-api-key,<key>
    proto_header = websocket.headers.get("sec-websocket-protocol") or websocket.headers.get("Sec-WebSocket-Protocol")
    if proto_header:
        parts = [p.strip() for p in proto_header.split(",") if p.strip()]
        for idx in range(len(parts) - 1):
            scheme = parts[idx].lower()
            value = parts[idx + 1]
            if scheme == "bearer" and value:
                return await _authenticate_ws(websocket, token=value)
            if scheme in {"x-api-key", "api-key"} and value:
                return await _authenticate_ws(websocket, api_key=value)

    return None


async def _require_session_access(
    client: Any,
    *,
    session_id: str,
    user_id: int,
) -> None:
    """Require that the authenticated user owns the requested ACP session."""
    verifier = getattr(client, "verify_session_access", None)
    if not callable(verifier):
        logger.warning(
            "ACP session access denied: client {} does not expose verify_session_access()",
            type(client).__name__,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")

    allowed = await verifier(session_id, user_id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")


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
        with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=4401)
        return

    try:
        client = await get_runner_client()
        await _require_session_access(client, session_id=session_id, user_id=user_id)
    except HTTPException:
        with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=4404)
        return
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=4404)
        return

    # Set up WebSocket stream wrapper for metrics
    persona_id = await _resolve_acp_session_persona_id(client, session_id=session_id, user_id=int(user_id))
    ws_quota_token, _ws_quota_reason = _acp_ws_try_acquire_quota(
        user_id=int(user_id),
        session_id=session_id,
        persona_id=persona_id,
    )
    if ws_quota_token is None:
        with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=4429)
        return

    stream = WebSocketStream(
        websocket,
        heartbeat_interval_s=30.0,
        idle_timeout_s=None,  # No idle timeout for ACP sessions
        close_on_done=False,
        labels={"component": "acp", "endpoint": "acp_session_stream"},
    )
    send_callback: Any | None = None

    try:
        await stream.start()

        # Define send callback for broadcasting
        async def _send_callback(message: dict[str, Any]) -> None:
            await stream.send_json(message)
        send_callback = _send_callback

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
            except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS as e:
                logger.exception("Error handling WebSocket message for session {}", session_id)
                await stream.send_json({
                    "type": "error",
                    "code": "internal_error",
                    "message": str(e),
                    "session_id": session_id,
                })

    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        logger.exception("WebSocket error for ACP session {}", session_id)
    finally:
        # Unregister WebSocket
        if send_callback is not None:
            try:
                client = await get_runner_client()
                await client.unregister_websocket(session_id, send_callback)
            except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
                pass
        await stream.stop()
        _acp_ws_release_quota(ws_quota_token)


@router.websocket("/sessions/{session_id}/ssh")
async def acp_session_ssh(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(None),
    api_key: str | None = Query(None),
) -> None:
    """WebSocket SSH proxy for an ACP sandbox session."""
    user_id = await _authenticate_ws(websocket, token=token, api_key=api_key)
    if user_id is None:
        with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=4401)
        return

    try:
        client = await get_runner_client()
        if not hasattr(client, "get_ssh_info"):
            await websocket.close(code=4404)
            return
        try:
            ssh_info = await client.get_ssh_info(session_id, user_id=user_id)
        except TypeError:
            ssh_info = await client.get_ssh_info(session_id)
        if not ssh_info:
            await websocket.close(code=4404)
            return
        ssh_host, ssh_port, ssh_user, ssh_key = ssh_info
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=4404)
        return

    persona_id = await _resolve_acp_session_persona_id(client, session_id=session_id, user_id=int(user_id))
    ws_quota_token, _ws_quota_reason = _acp_ws_try_acquire_quota(
        user_id=int(user_id),
        session_id=session_id,
        persona_id=persona_id,
    )
    if ws_quota_token is None:
        with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=4429)
        return

    await websocket.accept()
    ssh_proc: asyncio.subprocess.Process | None = None
    temp_key_path: str | None = None
    try:
        try:
            import asyncssh  # type: ignore
        except ImportError:
            asyncssh = None  # type: ignore[assignment]

        if asyncssh is not None:
            key = asyncssh.import_private_key(ssh_key)
            async with asyncssh.connect(
                ssh_host,
                port=int(ssh_port),
                username=ssh_user,
                client_keys=[key],
                known_hosts=None,
            ) as conn:
                process = await conn.create_process(term_type="xterm", term_size=(80, 24))

                async def _read_output(reader: Any) -> None:
                    while True:
                        data = await reader.read(4096)
                        if not data:
                            return
                        await websocket.send_bytes(data.encode() if isinstance(data, str) else data)

                async def _write_input() -> None:
                    while True:
                        try:
                            msg = await websocket.receive()
                        except WebSocketDisconnect:
                            return
                        if msg.get("type") == "websocket.disconnect":
                            return
                        if msg.get("text"):
                            text = msg["text"]
                            try:
                                payload = json.loads(text)
                            except json.JSONDecodeError:
                                payload = None
                            if isinstance(payload, dict) and payload.get("type") == "resize":
                                cols = int(payload.get("cols") or 0)
                                rows = int(payload.get("rows") or 0)
                                if cols > 0 and rows > 0:
                                    with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
                                        process.set_term_size(cols, rows)
                                continue
                            process.stdin.write(text)
                            await process.stdin.drain()
                        elif msg.get("bytes"):
                            process.stdin.write(msg["bytes"])
                            await process.stdin.drain()

                await asyncio.gather(
                    _read_output(process.stdout),
                    _read_output(process.stderr),
                    _write_input(),
                )
        else:
            with tempfile.NamedTemporaryFile("w", delete=False, prefix="acp_ssh_", suffix="_key") as tmp_key:
                tmp_key.write(ssh_key)
                temp_key_path = tmp_key.name
            os.chmod(temp_key_path, 0o600)

            ssh_proc = await asyncio.create_subprocess_exec(
                "ssh",
                "-i",
                temp_key_path,
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "IdentitiesOnly=yes",
                "-p",
                str(ssh_port),
                f"{ssh_user}@{ssh_host}",
                "-tt",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def _read_output(reader: asyncio.StreamReader | None) -> None:
                if reader is None:
                    return
                while True:
                    data = await reader.read(4096)
                    if not data:
                        return
                    await websocket.send_bytes(data)

            async def _write_input() -> None:
                if ssh_proc is None or ssh_proc.stdin is None:
                    return
                while True:
                    try:
                        msg = await websocket.receive()
                    except WebSocketDisconnect:
                        return
                    if msg.get("type") == "websocket.disconnect":
                        return
                    if msg.get("text"):
                        text = msg["text"]
                        # The ssh fallback cannot resize PTY directly; ignore resize control messages.
                        try:
                            payload = json.loads(text)
                        except json.JSONDecodeError:
                            payload = None
                        if isinstance(payload, dict) and payload.get("type") == "resize":
                            continue
                        ssh_proc.stdin.write(text.encode("utf-8"))
                        await ssh_proc.stdin.drain()
                    elif msg.get("bytes"):
                        ssh_proc.stdin.write(msg["bytes"])
                        await ssh_proc.stdin.drain()

            tasks = {
                asyncio.create_task(_read_output(ssh_proc.stdout)),
                asyncio.create_task(_read_output(ssh_proc.stderr)),
                asyncio.create_task(_write_input()),
            }
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in pending:
                with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
                    await task
            for task in done:
                with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
                    _ = task.result()
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=1011)
    finally:
        if ssh_proc is not None and ssh_proc.returncode is None:
            ssh_proc.terminate()
            with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
                await asyncio.wait_for(ssh_proc.wait(), timeout=2)
        if temp_key_path:
            with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
                os.unlink(temp_key_path)
        _acp_ws_release_quota(ws_quota_token)

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
        logger.debug(
            "ACP permission response processed: session_id={} request_id={} approved={} success={}",
            session_id,
            request_id,
            approved,
            success,
        )
        if not success:
            # Compatibility fallback for lightweight/mock runner clients that
            # track pending permissions in a simple dict.
            with contextlib.suppress(_ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS):
                pending = getattr(client, "_pending_permissions", None)
                if isinstance(pending, dict):
                    sess_pending = pending.get(session_id)
                    if isinstance(sess_pending, dict) and request_id in sess_pending:
                        sess_pending.pop(request_id, None)
                        success = True
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


def _get_static_agents() -> tuple[list[ACPAgentInfo], str]:
    """Fallback list of built-in agents when runner registry is unavailable."""
    import os

    agents: list[ACPAgentInfo] = []

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    agents.append(
        ACPAgentInfo(
            type="claude_code",
            name="Claude Code",
            description="Anthropic's Claude Code agent for software development tasks",
            is_configured=bool(anthropic_key),
            requires_api_key="ANTHROPIC_API_KEY" if not anthropic_key else None,
        )
    )

    openai_key = os.getenv("OPENAI_API_KEY", "")
    agents.append(
        ACPAgentInfo(
            type="codex",
            name="OpenAI Codex",
            description="OpenAI's Codex agent for code generation and analysis",
            is_configured=bool(openai_key),
            requires_api_key="OPENAI_API_KEY" if not openai_key else None,
        )
    )

    agents.append(
        ACPAgentInfo(
            type="opencode",
            name="OpenCode",
            description="Open-source coding agent (github.com/sst/opencode)",
            is_configured=True,
            requires_api_key=None,
        )
    )

    agents.append(
        ACPAgentInfo(
            type="custom",
            name="Custom Agent",
            description="Configure a custom agent with your own settings",
            is_configured=True,
            requires_api_key=None,
        )
    )

    return agents, "claude_code"


async def _get_available_agents() -> tuple[list[ACPAgentInfo], str]:
    """Get list of available agents and their configuration status."""
    try:
        client = await get_runner_client()
        raw = await client.list_agents()
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        return _get_static_agents()

    agents_raw = raw.get("agents", []) if isinstance(raw, dict) else []
    default_agent = raw.get("defaultAgentType") if isinstance(raw, dict) else None

    agents: list[ACPAgentInfo] = []
    for item in agents_raw:
        if not isinstance(item, dict):
            continue
        agent_type = item.get("type")
        name = item.get("name")
        if not agent_type or not name:
            continue
        is_configured = item.get("isConfigured")
        if is_configured is None:
            is_configured = item.get("is_configured", False)
        requires_api_key = item.get("requiresApiKey")
        if requires_api_key is None:
            requires_api_key = item.get("requires_api_key")
        agents.append(
            ACPAgentInfo(
                type=str(agent_type),
                name=str(name),
                description=str(item.get("description") or ""),
                is_configured=bool(is_configured),
                requires_api_key=str(requires_api_key) if requires_api_key else None,
            )
        )

    if not agents:
        return _get_static_agents()

    default_value = str(default_agent) if default_agent else agents[0].type
    return agents, default_value


@router.get("/agents", response_model=ACPAgentListResponse)
async def acp_list_agents(
    user: User = Depends(get_request_user),
) -> ACPAgentListResponse:
    """
    List available ACP agents and their configuration status.

    Returns information about which agents are available and properly configured.
    """
    agents, default_agent = await _get_available_agents()
    return ACPAgentListResponse(
        agents=agents,
        default_agent=default_agent,
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
        create_session_params = set(inspect.signature(client.create_session).parameters.keys())
        create_session_kwargs: dict[str, Any] = {}
        if payload.agent_type is not None and "agent_type" in create_session_params:
            create_session_kwargs["agent_type"] = payload.agent_type
        if "user_id" in create_session_params:
            create_session_kwargs["user_id"] = user.id
        optional_tenancy_args = (
            ("persona_id", payload.persona_id),
            ("workspace_id", payload.workspace_id),
            ("workspace_group_id", payload.workspace_group_id),
            ("scope_snapshot_id", payload.scope_snapshot_id),
        )
        for field_name, field_value in optional_tenancy_args:
            if field_value is not None and field_name in create_session_params:
                create_session_kwargs[field_name] = field_value
        session_id = await client.create_session(
            payload.cwd,
            mcp_servers_dicts,
            **create_session_kwargs,
        )
    except ACPResponseError as exc:
        logger.error("ACP session/new failed for user {}: {}", user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    sandbox_meta = None
    try:
        if hasattr(client, "get_session_metadata"):
            try:
                sandbox_meta = await client.get_session_metadata(session_id, user_id=user.id)
            except TypeError:
                sandbox_meta = await client.get_session_metadata(session_id)
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        sandbox_meta = None

    resolved_agent_type = payload.agent_type
    if resolved_agent_type is None:
        try:
            _, default_agent = await _get_available_agents()
            resolved_agent_type = default_agent
        except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
            resolved_agent_type = "custom"
    resolved_persona_id = payload.persona_id
    resolved_workspace_id = payload.workspace_id
    resolved_workspace_group_id = payload.workspace_group_id
    resolved_scope_snapshot_id = payload.scope_snapshot_id
    if sandbox_meta:
        resolved_persona_id = resolved_persona_id or sandbox_meta.get("persona_id")
        resolved_workspace_id = resolved_workspace_id or sandbox_meta.get("workspace_id")
        resolved_workspace_group_id = resolved_workspace_group_id or sandbox_meta.get("workspace_group_id")
        resolved_scope_snapshot_id = resolved_scope_snapshot_id or sandbox_meta.get("scope_snapshot_id")

    # Persist session metadata and emit SSE event
    try:
        store = await get_acp_session_store()
        await store.register_session(
            session_id=session_id,
            user_id=int(user.id),
            agent_type=resolved_agent_type or "custom",
            name=session_name,
            cwd=payload.cwd,
            tags=payload.tags,
            persona_id=resolved_persona_id,
            workspace_id=resolved_workspace_id,
            workspace_group_id=resolved_workspace_group_id,
            scope_snapshot_id=resolved_scope_snapshot_id,
        )
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        logger.warning("Failed to persist ACP session metadata for {}", session_id)
    try:
        from tldw_Server_API.app.api.v1.endpoints.admin.admin_events_stream import emit_admin_event
        await emit_admin_event("acp_session_created", {
            "session_id": session_id,
            "user_id": int(user.id),
            "agent_type": resolved_agent_type or "custom",
            "name": session_name,
        }, category="acp")
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        pass

    return ACPSessionNewResponse(
        session_id=session_id,
        name=session_name,
        agent_type=resolved_agent_type,
        agent_capabilities=client.agent_capabilities,
        sandbox_session_id=(sandbox_meta or {}).get("sandbox_session_id") if sandbox_meta else None,
        sandbox_run_id=(sandbox_meta or {}).get("sandbox_run_id") if sandbox_meta else None,
        ssh_ws_url=(sandbox_meta or {}).get("ssh_ws_url") if sandbox_meta else None,
        ssh_user=(sandbox_meta or {}).get("ssh_user") if sandbox_meta else None,
        persona_id=resolved_persona_id,
        workspace_id=resolved_workspace_id,
        workspace_group_id=resolved_workspace_group_id,
        scope_snapshot_id=resolved_scope_snapshot_id,
    )


@router.post("/sessions/prompt", response_model=ACPSessionPromptResponse)
async def acp_session_prompt(
    payload: ACPSessionPromptRequest,
    user: User = Depends(get_request_user),
) -> ACPSessionPromptResponse:
    try:
        client = await get_runner_client()
        await _require_session_access(client, session_id=payload.session_id, user_id=int(user.id))
        result = await client.prompt(payload.session_id, payload.prompt)
    except ACPResponseError as exc:
        logger.error("ACP session/prompt failed for user {}: {}", user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    # Record prompt exchange and accumulate token usage
    turn_usage = None
    try:
        store = await get_acp_session_store()
        turn_usage_data = await store.record_prompt(payload.session_id, payload.prompt, result)
        if turn_usage_data:
            turn_usage = ACPTokenUsage(
                prompt_tokens=turn_usage_data.prompt_tokens,
                completion_tokens=turn_usage_data.completion_tokens,
                total_tokens=turn_usage_data.total_tokens,
            )
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        logger.warning("Failed to record prompt for session {}", payload.session_id)

    return ACPSessionPromptResponse(
        stop_reason=result.get("stopReason"),
        raw_result=result,
        usage=turn_usage,
    )


@router.post("/sessions/cancel")
async def acp_session_cancel(
    payload: ACPSessionCancelRequest,
    user: User = Depends(get_request_user),
) -> dict:
    try:
        client = await get_runner_client()
        await _require_session_access(client, session_id=payload.session_id, user_id=int(user.id))
        await client.cancel(payload.session_id)
    except ACPResponseError as exc:
        logger.error("ACP session/cancel failed for user {}: {}", user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/sessions/close")
async def acp_session_close(
    payload: ACPSessionCloseRequest,
    user: User = Depends(get_request_user),
) -> dict:
    try:
        client = await get_runner_client()
        await _require_session_access(client, session_id=payload.session_id, user_id=int(user.id))
        await client.close_session(payload.session_id)
    except ACPResponseError as exc:
        logger.error("ACP session/close failed for user {}: {}", user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    # Mark session as closed in store and emit SSE event
    try:
        store = await get_acp_session_store()
        await store.close_session(payload.session_id)
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        pass
    try:
        from tldw_Server_API.app.api.v1.endpoints.admin.admin_events_stream import emit_admin_event
        await emit_admin_event("acp_session_closed", {
            "session_id": payload.session_id,
            "user_id": int(user.id),
        }, category="acp")
    except _ACP_ENDPOINT_NONCRITICAL_EXCEPTIONS:
        pass
    return {"status": "ok"}


@router.get("/sessions/{session_id}/updates", response_model=ACPSessionUpdatesResponse)
async def acp_session_updates(
    session_id: str,
    limit: int | None = Query(default=100, ge=1, le=1000),
    user: User = Depends(get_request_user),
) -> ACPSessionUpdatesResponse:
    client = await get_runner_client()
    await _require_session_access(client, session_id=session_id, user_id=int(user.id))
    updates = client.pop_updates(session_id, limit=limit or 100)
    return ACPSessionUpdatesResponse(updates=updates)


# -----------------------------------------------------------------------------
# Session Listing & Detail Endpoints
# -----------------------------------------------------------------------------


@router.get("/sessions", response_model=ACPSessionListResponse)
async def acp_list_sessions(
    status_filter: str | None = Query(default=None, alias="status"),
    agent_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_request_user),
) -> ACPSessionListResponse:
    """List ACP sessions for the authenticated user."""
    store = await get_acp_session_store()
    client = await get_runner_client()
    records, total = await store.list_sessions(
        user_id=int(user.id),
        status=status_filter,
        agent_type=agent_type,
        limit=limit,
        offset=offset,
    )
    sessions = [
        ACPSessionInfo(**rec.to_info_dict(
            has_websocket=client.has_websocket_connections(rec.session_id),
        ))
        for rec in records
    ]
    return ACPSessionListResponse(sessions=sessions, total=total)


@router.get("/sessions/{session_id}/detail", response_model=ACPSessionDetailResponse)
async def acp_session_detail(
    session_id: str,
    user: User = Depends(get_request_user),
) -> ACPSessionDetailResponse:
    """Get detailed information about an ACP session."""
    client = await get_runner_client()
    await _require_session_access(client, session_id=session_id, user_id=int(user.id))
    store = await get_acp_session_store()
    rec = await store.get_session(session_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")
    return ACPSessionDetailResponse(**rec.to_detail_dict(
        has_websocket=client.has_websocket_connections(session_id),
    ))


@router.get("/sessions/{session_id}/usage", response_model=ACPSessionUsageResponse)
async def acp_session_usage(
    session_id: str,
    user: User = Depends(get_request_user),
) -> ACPSessionUsageResponse:
    """Get token usage for an ACP session."""
    client = await get_runner_client()
    await _require_session_access(client, session_id=session_id, user_id=int(user.id))
    store = await get_acp_session_store()
    rec = await store.get_session(session_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")
    return ACPSessionUsageResponse(
        session_id=rec.session_id,
        user_id=rec.user_id,
        agent_type=rec.agent_type,
        usage=ACPTokenUsage(**rec.usage.to_dict()),
        message_count=rec.message_count,
        created_at=rec.created_at,
        last_activity_at=rec.last_activity_at,
    )


# -----------------------------------------------------------------------------
# Session Forking
# -----------------------------------------------------------------------------


@router.post("/sessions/{session_id}/fork", response_model=ACPSessionForkResponse)
async def acp_session_fork(
    session_id: str,
    payload: ACPSessionForkRequest,
    user: User = Depends(get_request_user),
) -> ACPSessionForkResponse:
    """Fork an ACP session from a specific message index.

    Creates a new session with message history up to the specified index.
    The forked session starts fresh with no active runner process — call
    ``/sessions/new`` with the returned session_id to resume.
    """
    client = await get_runner_client()
    await _require_session_access(client, session_id=session_id, user_id=int(user.id))

    store = await get_acp_session_store()
    source = await store.get_session(session_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")
    if payload.message_index >= len(source.messages):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"message_index {payload.message_index} exceeds message count {len(source.messages)}",
        )

    import uuid as _uuid
    new_session_id = str(_uuid.uuid4())
    forked = await store.fork_session(
        source_session_id=session_id,
        new_session_id=new_session_id,
        message_index=payload.message_index,
        user_id=int(user.id),
        name=payload.name,
    )
    if not forked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fork_failed")

    return ACPSessionForkResponse(
        session_id=forked.session_id,
        name=forked.name,
        forked_from=session_id,
        message_count=forked.message_count,
    )
