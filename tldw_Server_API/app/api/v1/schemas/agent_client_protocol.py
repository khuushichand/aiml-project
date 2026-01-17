from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ACPSessionNewRequest(BaseModel):
    cwd: str = Field(..., description="Absolute working directory for the ACP session")
    mcp_servers: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Optional MCP server configurations"
    )


class ACPSessionNewResponse(BaseModel):
    session_id: str
    agent_capabilities: Optional[Dict[str, Any]] = None


class ACPSessionPromptRequest(BaseModel):
    session_id: str
    prompt: List[Dict[str, Any]]


class ACPSessionPromptResponse(BaseModel):
    stop_reason: Optional[str] = None
    raw_result: Dict[str, Any]


class ACPSessionCancelRequest(BaseModel):
    session_id: str


class ACPSessionCloseRequest(BaseModel):
    session_id: str


class ACPSessionUpdatesResponse(BaseModel):
    updates: List[Dict[str, Any]]
