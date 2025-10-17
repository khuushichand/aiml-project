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
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode, get_settings


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
    """Bi-directional placeholder stream.

    Accepts JSON text frames and echoes minimal notices.
    """
    await ws.accept()
    if not is_persona_enabled():
        await ws.send_text(json.dumps({"event": "notice", "level": "error", "message": "Persona disabled"}))
        await ws.close(code=1000)
        return
    try:
        await ws.send_text(json.dumps({"event": "notice", "message": "persona stream connected (scaffold)"}))
        # Resolve user_id from token/api_key similar to MCP ws
        user_id: Optional[str] = None
        try:
            if api_key and is_single_user_mode():
                s = get_settings()
                if api_key == s.SINGLE_USER_API_KEY:
                    user_id = str(s.SINGLE_USER_FIXED_ID)
        except Exception:
            pass
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
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = {"type": "unknown", "raw": raw}

            mtype = msg.get("type") or msg.get("event") or "unknown"
            if mtype == "user_message":
                text = (msg.get("text") or msg.get("message") or "").strip()
                plan = await _propose_plan(text)
                plan_id = uuid.uuid4().hex
                await ws.send_text(json.dumps({"event": "tool_plan", "plan_id": plan_id, **plan}))
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
                    await ws.send_text(json.dumps({"event": "tool_call", "step_idx": idx, "tool": step.get("tool")}))
                    result = await _call_tool(step.get("tool"), step.get("args") or {})
                    await ws.send_text(json.dumps({"event": "tool_result", "step_idx": idx, **result}))
            else:
                await ws.send_text(json.dumps({"event": "assistant_delta", "text_delta": "(scaffold)"}))
                await ws.send_text(json.dumps({"event": "notice", "message": f"echo: {mtype}"}))
    except WebSocketDisconnect:
        logger.info("Persona stream disconnected")
    except Exception as e:
        logger.warning(f"Persona stream error: {e}")
        try:
            await ws.close(code=1011)
        except Exception:
            pass
