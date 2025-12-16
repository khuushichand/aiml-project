# tldw_Server_API/app/api/v1/endpoints/persona.py
# Placeholder endpoints for Persona Agent (catalog, session, WebSocket stream)

from __future__ import annotations

import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Body, WebSocket, WebSocketDisconnect, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.persona import (
    PersonaInfo,
    PersonaSessionRequest,
    PersonaSessionResponse,
)
from tldw_Server_API.app.core.feature_flags import is_persona_enabled
from tldw_Server_API.app.core.MCP_unified import get_mcp_server, MCPRequest
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.exceptions import DatabaseError, InvalidTokenError
from tldw_Server_API.app.core.Streaming.streams import WebSocketStream


router = APIRouter()


@router.get("/catalog", response_model=List[PersonaInfo], tags=["persona"], status_code=status.HTTP_200_OK)
async def persona_catalog() -> List[PersonaInfo]:
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
    token: Optional[str] = Query(default=None),
    api_key: Optional[str] = Query(default=None),
):
    """
    Bi-directional placeholder stream.

    Standardized with WebSocketStream lifecycle/metrics; domain payloads unchanged.
    Accepts JSON text frames and echoes minimal notices.

    Security model:
    - Feature-gated via PERSONA_ENABLED.
    - API keys are optional and used only to associate a best-effort user_id with the
      session; invalid or missing keys fall back to anonymous persona sessions rather
      than closing the connection.
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
        await stream.send_json({"event": "notice", "message": "persona stream connected (scaffold)"})
        # Resolve user_id from api_key via AuthNZ API key manager.
        # On known AuthNZ/database errors, log at debug level and continue
        # without a resolved user_id rather than failing the stream. Persona is
        # currently designed as an optional personalization layer for single-user
        # style deployments, so invalid/missing API keys are treated as anonymous
        # sessions rather than hard auth failures.
        user_id: Optional[str] = None
        if api_key:
            try:
                api_mgr = await get_api_key_manager()
                client = getattr(ws, "client", None)
                client_ip = getattr(client, "host", None) if client is not None else None
                info = await api_mgr.validate_api_key(api_key, ip_address=client_ip)
                if info and info.get("user_id") is not None:
                    user_id = str(info["user_id"])
            except (DatabaseError, InvalidTokenError) as exc:
                logger.debug(f"persona stream: failed to resolve user from api_key: {exc}")
            except Exception:  # noqa: BLE001 - keep stream alive, fall back to anonymous
                logger.exception("persona stream: unexpected error resolving user from api_key")
        # Basic RBAC policy from settings
        from tldw_Server_API.app.core.config import settings as _app_settings
        allow_export = bool(_app_settings.get("PERSONA_RBAC_ALLOW_EXPORT", False))
        allow_delete = bool(_app_settings.get("PERSONA_RBAC_ALLOW_DELETE", False))

        def _tool_allowed(name: str) -> bool:
            n = (name or "").lower()
            if "delete" in n and not allow_delete:
                return False
            if "export" in n and not allow_export:
                return False
            return True

        async def _call_tool(name: str, arguments: dict) -> dict:
            if not _tool_allowed(name):
                return {"error": f"Tool '{name}' not permitted by policy"}
            req = MCPRequest(method="tools/call", params={"name": name, "arguments": arguments})
            server = get_mcp_server()
            if not server.initialized:
                await server.initialize()
            resp = await server.handle_http_request(req, user_id=user_id)
            if resp.error:
                return {"error": resp.error.message}
            return {"ok": True, "result": resp.result}

        async def _propose_plan(text: str) -> dict:
            steps = []
            t = (text or "").lower()
            if "http" in t or "ingest" in t or "url" in t:
                steps.append({"idx": 0, "tool": "ingest_url", "args": {"url": text}, "description": "Ingest the provided URL"})
                steps.append({"idx": 1, "tool": "summarize", "args": {}, "description": "Summarize the ingested content"})
            else:
                steps.append({"idx": 0, "tool": "rag_search", "args": {"query": text}, "description": "Search your knowledge base"})
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
                plan = await _propose_plan(text)
                plan_id = uuid.uuid4().hex
                await stream.send_json({"event": "tool_plan", "plan_id": plan_id, **plan})
            elif mtype == "confirm_plan":
                plan_id = msg.get("plan_id")
                steps = msg.get("approved_steps", [])
                # Naive: run in order 0..N if approved
                for idx in steps:
                    try:
                        step = next(s for s in msg.get("steps", []) if s.get("idx") == idx)
                    except StopIteration:
                        # If steps not included in message, re-propose
                        continue
                    await stream.send_json({"event": "tool_call", "step_idx": idx, "tool": step.get("tool")})
                    result = await _call_tool(step.get("tool"), step.get("args") or {})
                    await stream.send_json({"event": "tool_result", "step_idx": idx, **result})
            else:
                await stream.send_json({"event": "assistant_delta", "text_delta": "(scaffold)"})
                await stream.send_json({"event": "notice", "message": f"echo: {mtype}"})
    except WebSocketDisconnect:
        logger.info("Persona stream disconnected")
    except Exception as e:
        logger.warning(f"Persona stream error: {e}")
        try:
            await stream.error("internal_error", "Internal error")
        except Exception:
            pass
