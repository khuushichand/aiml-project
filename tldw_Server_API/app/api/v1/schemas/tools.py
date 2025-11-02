from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    module: Optional[str] = None
    inputSchema: Optional[Dict[str, Any]] = None
    canExecute: bool = Field(False, description="Whether current user can execute this tool")


class ToolListResponse(BaseModel):
    tools: List[ToolInfo]


class ExecuteToolRequest(BaseModel):
    tool_name: str = Field(..., description="Tool name (registry id)")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(
        default=None, description="Optional key for deduplicating write-capable tools"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, only checks permission and validates args when possible without executing",
    )


class ExecuteToolResult(BaseModel):
    ok: bool
    result: Optional[Any] = None
    module: Optional[str] = None
    error: Optional[str] = None
