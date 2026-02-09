# tldw_Server_API/app/api/v1/endpoints/persona.py
# Placeholder endpoints for Persona Agent (catalog, session, WebSocket stream)

from __future__ import annotations

import contextlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, Body, Query, WebSocket, WebSocketDisconnect, status
from loguru import logger
from starlette.requests import Request as StarletteRequest

from tldw_Server_API.app.api.v1.schemas.persona import (
    PersonaInfo,
    PersonaSessionRequest,
    PersonaSessionResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import verify_jwt_and_fetch_user
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.exceptions import DatabaseError, InvalidTokenError, TokenExpiredError
from tldw_Server_API.app.core.AuthNZ.ip_allowlist import resolve_client_ip
from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
from tldw_Server_API.app.core.feature_flags import is_persona_enabled
from tldw_Server_API.app.core.MCP_unified import MCPRequest, get_mcp_server
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
from tldw_Server_API.app.core.Persona.session_manager import get_session_manager
from tldw_Server_API.app.core.Streaming.streams import WebSocketStream

router = APIRouter()


def _get_persona_max_tool_steps() -> int:
    try:
        from tldw_Server_API.app.core.config import settings as _app_settings

        value = int(_app_settings.get("PERSONA_MAX_TOOL_STEPS", 3))
    except Exception:
        value = 3
    return max(1, min(value, 20))


def _is_authnz_access_token(token: str) -> bool:
    """Return True when token verifies as an AuthNZ access token."""
    try:
        jwt_service = get_jwt_service()
        jwt_service.decode_access_token(token)
        return True
    except TokenExpiredError:
        return True
    except InvalidTokenError:
        return False
    except Exception:
        return False


def _extract_auth_credentials(
    ws: WebSocket,
    token: str | None,
    api_key: str | None,
) -> tuple[str | None, str | None]:
    """Resolve auth credentials with headers taking precedence over query params."""
    auth_token = token
    resolved_api_key = api_key

    try:
        authz = ws.headers.get("authorization") or ws.headers.get("Authorization")
        if authz and authz.lower().startswith("bearer "):
            auth_token = authz.split(" ", 1)[1].strip()
    except Exception:
        pass

    try:
        header_key = ws.headers.get("x-api-key") or ws.headers.get("X-API-KEY")
        if header_key:
            resolved_api_key = header_key.strip()
    except Exception:
        pass

    try:
        proto = ws.headers.get("sec-websocket-protocol") or ws.headers.get("Sec-WebSocket-Protocol")
        if proto and not auth_token:
            parts = [p.strip() for p in proto.split(",")]
            if len(parts) >= 2 and parts[0].lower() == "bearer" and parts[1]:
                auth_token = parts[1]
    except Exception:
        pass

    return auth_token, resolved_api_key


def _build_request_from_websocket(ws: WebSocket) -> StarletteRequest:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/persona/stream",
        "headers": [
            (k.encode("latin-1"), v.encode("latin-1"))
            for k, v in ws.headers.items()
        ],
    }
    try:
        client = ws.client
        if isinstance(client, (list, tuple)) and len(client) >= 2:
            scope["client"] = (client[0], client[1])
        elif client is not None and getattr(client, "host", None) is not None:
            scope["client"] = (client.host, getattr(client, "port", 0))
    except Exception:
        pass
    return StarletteRequest(scope)


async def _resolve_authenticated_user_id(
    ws: WebSocket,
    token: str | None,
    api_key: str | None,
) -> tuple[str | None, bool, bool]:
    """
    Resolve authenticated user id from WS credentials.

    Returns: (user_id, credentials_supplied, auth_ok)
    """
    auth_token, resolved_api_key = _extract_auth_credentials(ws, token, api_key)
    credentials_supplied = bool(auth_token or resolved_api_key)
    user_id: str | None = None

    if auth_token:
        auth_ok = False
        authnz_token_failed = False
        try:
            req = _build_request_from_websocket(ws)
            user = await verify_jwt_and_fetch_user(req, auth_token)
            uid = str(getattr(user, "id", None) or "")
            if uid:
                user_id = uid
                auth_ok = True
                logger.debug("persona stream: authenticated via AuthNZ JWT")
        except Exception as exc:
            logger.debug(f"persona stream: AuthNZ JWT auth failed: {exc}")
            if _is_authnz_access_token(auth_token):
                authnz_token_failed = True
                if not resolved_api_key:
                    return None, True, False
        if not auth_ok and not authnz_token_failed:
            try:
                token_data = get_jwt_manager().verify_token(auth_token)
                uid = str(getattr(token_data, "sub", "") or "")
                if uid:
                    user_id = uid
                    auth_ok = True
                    logger.debug("persona stream: authenticated via MCP JWT")
            except Exception as exc:
                logger.debug(f"persona stream: MCP JWT auth failed: {exc}")
        if auth_token and not auth_ok and not resolved_api_key:
            return None, True, False

    if resolved_api_key and not user_id:
        try:
            api_mgr = await get_api_key_manager()
            client_ip = resolve_client_ip(ws, None)
            info = await api_mgr.validate_api_key(resolved_api_key, ip_address=client_ip)
            if info and info.get("user_id") is not None:
                user_id = str(info["user_id"])
                logger.debug("persona stream: authenticated via API key")
            else:
                return None, True, False
        except (DatabaseError, InvalidTokenError) as exc:
            logger.debug(f"persona stream: API key authentication failed: {exc}")
            return None, True, False
        except Exception:
            logger.exception("persona stream: unexpected API key authentication error")
            return None, True, False

    if credentials_supplied and not user_id:
        return None, True, False
    return user_id, credentials_supplied, True


@router.get("/catalog", response_model=list[PersonaInfo], tags=["persona"], status_code=status.HTTP_200_OK)
async def persona_catalog() -> list[PersonaInfo]:
    """Return a placeholder persona catalog (scaffold)."""
    if not is_persona_enabled():
        return []
    return [
        PersonaInfo(
            id="research_assistant",
            name="Research Assistant",
            description="Helps ingest, search, and summarize content",
            voice="default",
            avatar_url=None,
            capabilities=["ingest", "rag_search", "summarize"],
            default_tools=["ingest_url", "rag_search", "summarize"],
        )
    ]


@router.post("/session", response_model=PersonaSessionResponse, tags=["persona"], status_code=status.HTTP_200_OK)
async def persona_session(req: PersonaSessionRequest = Body(...)) -> PersonaSessionResponse:
    """Create or resume a persona session (scaffold)."""
    if not is_persona_enabled():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Persona disabled")
    session_id = req.resume_session_id or str(uuid.uuid4())
    persona = (await persona_catalog())[0]
    if req.persona_id and req.persona_id != persona.id:
        logger.info(f"Unknown persona_id requested in scaffold: {req.persona_id}; defaulting to {persona.id}")
    return PersonaSessionResponse(session_id=session_id, persona=persona, scopes=["read", "write:preview"])


@router.websocket("/stream")
async def persona_stream(
    ws: WebSocket,
    token: str | None = Query(default=None),
    api_key: str | None = Query(default=None),
):
    """
    Bi-directional placeholder stream.

    Standardized with WebSocketStream lifecycle/metrics; domain payloads unchanged.
    Accepts JSON text frames and echoes minimal notices.

    Security model:
    - Feature-gated via PERSONA_ENABLED.
    - Supports token/api-key auth resolution similar to MCP.
    - Tool execution requires an authenticated user_id.
    - Invalid credentials close the stream; no-credential sessions remain read-only.
    """
    # Wrap socket for lifecycle and metrics; keep domain payloads unchanged
    stream = WebSocketStream(
        ws,
        heartbeat_interval_s=0.0,  # disable WS pings for this scaffold
        idle_timeout_s=None,
        close_on_done=False,
        labels={"component": "persona", "endpoint": "persona_ws"},
    )
    await stream.start()

    if not is_persona_enabled():
        await stream.send_json({"event": "notice", "level": "error", "message": "Persona disabled"})
        try:
            await stream.ws.close(code=1000)
        except (RuntimeError, OSError) as exc:
            logger.debug(f"Persona stream close failed after disable notice: {exc}")
        return
    try:
        user_id, credentials_supplied, auth_ok = await _resolve_authenticated_user_id(ws, token=token, api_key=api_key)
        if credentials_supplied and not auth_ok:
            await stream.send_json({"event": "notice", "level": "error", "message": "Authentication failed"})
            try:
                await stream.ws.close(code=1008)
            except (RuntimeError, OSError):
                pass
            return

        await stream.send_json({"event": "notice", "message": "persona stream connected (scaffold)"})
        connection_user_id = user_id or f"anonymous:{uuid.uuid4().hex}"
        session_manager = get_session_manager()
        default_session_id = uuid.uuid4().hex

        # Basic RBAC policy from settings
        from tldw_Server_API.app.core.config import settings as _app_settings
        allow_export = bool(_app_settings.get("PERSONA_RBAC_ALLOW_EXPORT", False))
        allow_delete = bool(_app_settings.get("PERSONA_RBAC_ALLOW_DELETE", False))

        def _tool_allowed(name: str) -> bool:
            n = (name or "").lower()
            if "delete" in n and not allow_delete:
                return False
            return not ("export" in n and not allow_export)

        async def _call_tool(
            name: str,
            arguments: dict,
            *,
            session_id: str,
            plan_id: str,
            step_idx: int,
            why: str | None = None,
            description: str | None = None,
        ) -> dict:
            if user_id is None:
                return {"error": "Authentication required for tool execution"}
            if not _tool_allowed(name):
                return {"error": f"Tool '{name}' not permitted by policy"}
            req = MCPRequest(method="tools/call", params={"name": name, "arguments": arguments})
            server = get_mcp_server()
            if not server.initialized:
                await server.initialize()
            audit_metadata = {
                "session_id": session_id,
                "persona_audit": {
                    "source": "persona_ws",
                    "plan_id": plan_id,
                    "step_idx": step_idx,
                    "tool": name,
                    "why": str(why or ""),
                    "description": str(description or ""),
                },
            }
            resp = await server.handle_http_request(req, user_id=user_id, metadata=audit_metadata)
            if resp.error:
                return {"error": resp.error.message}
            return {"ok": True, "result": resp.result}

        async def _propose_plan(text: str) -> dict:
            steps = []
            t = (text or "").lower()
            if "http" in t or "ingest" in t or "url" in t:
                steps.append(
                    {
                        "idx": 0,
                        "tool": "ingest_url",
                        "args": {"url": text},
                        "description": "Ingest the provided URL",
                        "why": "Input looks like a URL or ingestion request.",
                    }
                )
                steps.append(
                    {
                        "idx": 1,
                        "tool": "summarize",
                        "args": {},
                        "description": "Summarize the ingested content",
                        "why": "User likely wants a concise summary after ingestion.",
                    }
                )
            else:
                steps.append(
                    {
                        "idx": 0,
                        "tool": "rag_search",
                        "args": {"query": text},
                        "description": "Search your knowledge base",
                        "why": "Input appears to be a knowledge query.",
                    }
                )
            return {"steps": steps}

        while True:
            raw = await stream.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = {"type": "unknown", "raw": raw}

            mtype = msg.get("type") or msg.get("event") or "unknown"
            if mtype == "user_message":
                text = (msg.get("text") or msg.get("message") or "").strip()
                session_id = str(msg.get("session_id") or default_session_id)
                plan = await _propose_plan(text)
                plan_id = uuid.uuid4().hex
                max_tool_steps = _get_persona_max_tool_steps()
                proposed_steps = list(plan.get("steps", []))
                if len(proposed_steps) > max_tool_steps:
                    proposed_steps = proposed_steps[:max_tool_steps]
                    await stream.send_json(
                        {
                            "event": "notice",
                            "session_id": session_id,
                            "level": "warning",
                            "message": f"Plan truncated to max_tool_steps={max_tool_steps}",
                        }
                    )
                try:
                    pending_plan = session_manager.put_plan(
                        session_id=session_id,
                        user_id=connection_user_id,
                        persona_id="research_assistant",
                        plan_id=plan_id,
                        steps=proposed_steps,
                    )
                except ValueError as exc:
                    await stream.send_json({"event": "notice", "session_id": session_id, "level": "error", "message": str(exc)})
                    continue
                stored_steps = [
                    {
                        "idx": step.idx,
                        "tool": step.tool,
                        "args": step.args,
                        "description": step.description,
                        "why": step.why,
                    }
                    for step in pending_plan.steps
                ]
                await stream.send_json({"event": "tool_plan", "session_id": session_id, "plan_id": plan_id, "steps": stored_steps})
            elif mtype == "confirm_plan":
                session_id = str(msg.get("session_id") or default_session_id)
                plan_id = str(msg.get("plan_id") or "").strip()
                if not plan_id:
                    await stream.send_json({"event": "notice", "session_id": session_id, "level": "error", "message": "plan_id is required"})
                    continue

                approved_steps_raw = msg.get("approved_steps", [])
                if not isinstance(approved_steps_raw, list):
                    await stream.send_json({"event": "notice", "session_id": session_id, "level": "error", "message": "approved_steps must be a list"})
                    continue
                approved_step_indices: list[int] = []
                for raw_idx in approved_steps_raw:
                    try:
                        approved_step_indices.append(int(raw_idx))
                    except (TypeError, ValueError):
                        continue
                if not approved_step_indices:
                    await stream.send_json({"event": "notice", "session_id": session_id, "level": "warning", "message": "No valid approved steps"})
                    continue
                max_tool_steps = _get_persona_max_tool_steps()
                approved_step_indices = sorted(set(approved_step_indices))[:max_tool_steps]

                pending_plan = session_manager.get_plan(
                    session_id=session_id,
                    plan_id=plan_id,
                    user_id=connection_user_id,
                    consume=True,
                )
                if pending_plan is None:
                    await stream.send_json({"event": "notice", "session_id": session_id, "level": "error", "message": "Invalid plan_id/session_id"})
                    continue

                executed_steps = 0
                for step in pending_plan.steps:
                    if step.idx not in approved_step_indices:
                        continue
                    executed_steps += 1
                    await stream.send_json(
                        {
                            "event": "tool_call",
                            "session_id": session_id,
                            "step_idx": step.idx,
                            "tool": step.tool,
                            "args": step.args,
                            "why": step.why,
                        }
                    )
                    result = await _call_tool(
                        step.tool,
                        step.args or {},
                        session_id=session_id,
                        plan_id=plan_id,
                        step_idx=step.idx,
                        why=step.why,
                        description=step.description,
                    )
                    await stream.send_json({"event": "tool_result", "session_id": session_id, "step_idx": step.idx, **result})
                if executed_steps == 0:
                    await stream.send_json({"event": "notice", "session_id": session_id, "level": "warning", "message": "No approved steps matched plan"})
            elif mtype == "cancel":
                session_id = str(msg.get("session_id") or default_session_id)
                reason = str(msg.get("reason") or "user_cancelled")
                cleared = session_manager.clear_plans(session_id=session_id, user_id=connection_user_id)
                await stream.send_json(
                    {
                        "event": "notice",
                        "session_id": session_id,
                        "level": "info",
                        "message": f"Cancelled pending work ({cleared} plan(s) cleared): {reason}",
                    }
                )
            else:
                session_id = str(msg.get("session_id") or default_session_id)
                await stream.send_json({"event": "assistant_delta", "session_id": session_id, "text_delta": "(scaffold)"})
                await stream.send_json({"event": "notice", "session_id": session_id, "message": f"echo: {mtype}"})
    except WebSocketDisconnect:
        logger.info("Persona stream disconnected")
    except Exception as e:
        logger.warning(f"Persona stream error: {e}")
        with contextlib.suppress(Exception):
            await stream.error("internal_error", "Internal error")
