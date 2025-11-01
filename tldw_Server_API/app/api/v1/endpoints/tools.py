from __future__ import annotations

from typing import Any, Dict, Coroutine, List
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.tools import (
    ToolListResponse,
    ExecuteToolRequest,
    ExecuteToolResult,
    ToolInfo,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.permissions import PermissionChecker
from tldw_Server_API.app.core.Tools.tool_executor import ToolExecutor, ToolExecutionError

router = APIRouter()


@router.get("/tools", response_model=ToolListResponse, summary="List available tools for current user")
async def list_tools_endpoint(current_user: User = Depends(get_request_user)) -> ToolListResponse:
    try:
        executor = ToolExecutor()

        out = await executor.list_tools(
            user_id=str(current_user.id),
            client_id=str(current_user.username or current_user.id),
        )

        def _to_tool_info(t: Dict[str, Any]) -> ToolInfo | None:
            try:
                return ToolInfo(**t)
            except Exception as e:
                logger.warning(
                    f"Failed to parse tool info, falling back to best-effort mapping. Tool: {t.get('name')}, Error: {e}"
                )
                # Best-effort mapping from provided dict without re-fetching
                try:
                    return ToolInfo(
                        name=str(t.get("name", "")),
                        description=t.get("description"),
                        module=t.get("module"),
                        canExecute=bool(t.get("canExecute")),
                    )
                except Exception as e2:
                    logger.error(f"Failed to best-effort map tool info: {e2}; data={t}")
                    return None

        raw_tools = (out.get("tools") or []) if isinstance(out, dict) else []
        tools_maybe = [_to_tool_info(t) for t in raw_tools]
        tools: List[ToolInfo] = [ti for ti in tools_maybe if ti is not None]
        return ToolListResponse(tools=tools)
    except Exception as e:
        logger.error(f"tools.list failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list tools")


@router.post(
    "/tools/execute",
    response_model=ExecuteToolResult,
    summary="Execute a tool via the server",
    dependencies=[Depends(PermissionChecker("tools.execute:*"))],
)
async def execute_tool_endpoint(
    req: ExecuteToolRequest,
    current_user: User = Depends(get_request_user),
) -> ExecuteToolResult:
    try:
        executor = ToolExecutor()
        if req.dry_run:
            await executor.execute(
                user_id=str(current_user.id),
                client_id=str(current_user.username or current_user.id),
                tool_name=req.tool_name,
                arguments=req.arguments,
                idempotency_key=req.idempotency_key,
                validate_only=True,
            )
            return ExecuteToolResult(ok=True, result={"validated": True}, module=None)

        result = await executor.execute(
            user_id=str(current_user.id),
            client_id=str(current_user.username or current_user.id),
            tool_name=req.tool_name,
            arguments=req.arguments,
            idempotency_key=req.idempotency_key,
        )
        return ExecuteToolResult(ok=True, result=result.get("result", result), module=result.get("module"))
    except ToolExecutionError as te:
        logger.warning(f"tools.execute denied or invalid: {te}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(te))
    except Exception as e:
        logger.error(f"tools.execute failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Tool execution failed")
