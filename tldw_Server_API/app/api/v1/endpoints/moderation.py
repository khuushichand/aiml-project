# moderation.py
# Description: Admin endpoints for Moderation settings (per-user overrides and blocklist)

from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Response
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin
from tldw_Server_API.app.api.v1.schemas.moderation_schemas import (
    ModerationUserOverride,
    ModerationBlocklistUpdate,
    ModerationUserOverridesResponse,
    BlocklistManagedResponse,
    BlocklistManagedItem,
    BlocklistAppendRequest,
    BlocklistAppendResponse,
    BlocklistDeleteResponse,
    BlocklistLintRequest,
    BlocklistLintResponse,
    BlocklistLintItem,
    ModerationTestRequest,
    ModerationTestResponse,
    ModerationSettingsResponse,
    ModerationSettingsUpdate,
)
from tldw_Server_API.app.core.Moderation.moderation_service import get_moderation_service


router = APIRouter()


@router.get("/moderation/users", response_model=ModerationUserOverridesResponse, summary="List all per-user moderation overrides", tags=["moderation"])
async def list_user_overrides(_: Any = Depends(require_admin)):
    svc = get_moderation_service()
    return {"overrides": svc.list_user_overrides()}


@router.get("/moderation/users/{user_id}", response_model=dict, summary="Get per-user moderation override", tags=["moderation"])
async def get_user_override(user_id: str, _: Any = Depends(require_admin)):
    svc = get_moderation_service()
    data = svc.list_user_overrides().get(str(user_id))
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
    return data


@router.put("/moderation/users/{user_id}", response_model=dict, summary="Set per-user moderation override", tags=["moderation"])
async def set_user_override(user_id: str, override: ModerationUserOverride, _: Any = Depends(require_admin)):
    svc = get_moderation_service()
    status_info = svc.set_user_override(user_id, override.model_dump(exclude_none=True))
    if not status_info or not status_info.get("ok"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=status_info.get("error", "Failed to persist override"))
    data = svc.list_user_overrides().get(str(user_id), {})
    # Surface whether the change was persisted
    if isinstance(data, dict):
        data = {**data, "persisted": bool(status_info.get("persisted", False))}
    return data


@router.delete("/moderation/users/{user_id}", summary="Delete per-user moderation override", tags=["moderation"])
async def delete_user_override(user_id: str, _: Any = Depends(require_admin)):
    svc = get_moderation_service()
    status_info = svc.delete_user_override(user_id)
    if not status_info or not status_info.get("ok"):
        detail = status_info.get("error", "Override not found or failed to delete")
        code = status.HTTP_404_NOT_FOUND if status_info.get("error") == "not found" else status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=code, detail=detail)
    return {"status": "deleted", "persisted": bool(status_info.get("persisted", False))}


@router.get("/moderation/blocklist", response_model=list, summary="Get current blocklist lines", tags=["moderation"])
async def get_blocklist(_: Any = Depends(require_admin)):
    svc = get_moderation_service()
    return svc.get_blocklist_lines()


@router.put("/moderation/blocklist", summary="Replace blocklist with provided lines", tags=["moderation"])
async def update_blocklist(data: ModerationBlocklistUpdate, _: Any = Depends(require_admin)):
    svc = get_moderation_service()
    ok = svc.set_blocklist_lines(data.lines or [])
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist blocklist")
    return {"status": "ok", "count": len(data.lines or [])}


@router.get(
    "/moderation/policy/effective",
    summary="Inspect effective moderation policy for a user",
    tags=["moderation"],
)
async def get_effective_policy(user_id: Optional[str] = Query(None, description="User ID to compute effective policy; optional"), _: Any = Depends(require_admin)):
    svc = get_moderation_service()
    try:
        snapshot = svc.effective_policy_snapshot(user_id)
        return snapshot
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to compute effective policy: {e}")


@router.post(
    "/moderation/reload",
    summary="Reload moderation configuration from disk",
    tags=["moderation"],
)
async def reload_moderation(_: Any = Depends(require_admin)):
    svc = get_moderation_service()
    try:
        svc.reload()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to reload moderation: {e}")


@router.get(
    "/moderation/settings",
    response_model=ModerationSettingsResponse,
    summary="Get runtime moderation settings and effective state",
    tags=["moderation"],
)
async def get_moderation_settings(_: Any = Depends(require_admin)):
    svc = get_moderation_service()
    try:
        data = svc.get_settings()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/moderation/settings",
    response_model=ModerationSettingsResponse,
    summary="Update runtime moderation settings (non-persistent)",
    tags=["moderation"],
)
async def update_moderation_settings(body: ModerationSettingsUpdate, _: Any = Depends(require_admin)):
    svc = get_moderation_service()
    try:
        data = svc.update_settings(pii_enabled=body.pii_enabled, categories_enabled=body.categories_enabled, persist=bool(body.persist))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/moderation/blocklist/managed",
    response_model=BlocklistManagedResponse,
    summary="Managed blocklist listing with version",
    tags=["moderation"],
)
async def get_blocklist_managed(response: Response, _: Any = Depends(require_admin)):
    svc = get_moderation_service()
    state = svc.get_blocklist_state()
    # Set ETag header for clients to use with If-Match
    response.headers["ETag"] = state.get("version", "")
    items = [BlocklistManagedItem(**it) for it in (state.get("items") or [])]
    return BlocklistManagedResponse(version=state.get("version", ""), items=items)


@router.post(
    "/moderation/blocklist/append",
    response_model=BlocklistAppendResponse,
    summary="Append a blocklist line (optimistic concurrency)",
    tags=["moderation"],
)
async def append_blocklist_line(
    payload: BlocklistAppendRequest,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    _: Any = Depends(require_admin),
):
    if not if_match:
        raise HTTPException(status_code=428, detail="If-Match header is required")
    svc = get_moderation_service()
    ok, state = svc.append_blocklist_line(if_match, payload.line)
    if not ok:
        if state.get("conflict"):
            raise HTTPException(status_code=status.HTTP_412_PRECONDITION_FAILED, detail="Version conflict")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=state.get("error", "Unknown error"))
    version = str(state.get("version", ""))
    items = state.get("items") or []
    # New index is last
    index = len(items) - 1
    response.headers["ETag"] = version
    return BlocklistAppendResponse(version=version, index=index, count=len(items))


@router.delete(
    "/moderation/blocklist/{item_id}",
    response_model=BlocklistDeleteResponse,
    summary="Delete a blocklist entry by index (optimistic concurrency)",
    tags=["moderation"],
)
async def delete_blocklist_item(
    item_id: int,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    _: Any = Depends(require_admin),
):
    if not if_match:
        raise HTTPException(status_code=428, detail="If-Match header is required")
    svc = get_moderation_service()
    ok, state = svc.delete_blocklist_index(if_match, item_id)
    if not ok:
        if state.get("conflict"):
            raise HTTPException(status_code=status.HTTP_412_PRECONDITION_FAILED, detail="Version conflict")
        detail = state.get("error", "Unknown error")
        code = status.HTTP_400_BAD_REQUEST if detail == "index out of range" else status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=code, detail=detail)
    version = str(state.get("version", ""))
    items = state.get("items") or []
    response.headers["ETag"] = version
    return BlocklistDeleteResponse(version=version, count=len(items))


@router.post(
    "/moderation/blocklist/lint",
    response_model=BlocklistLintResponse,
    summary="Validate blocklist lines without persisting",
    tags=["moderation"],
)
async def lint_blocklist(
    payload: BlocklistLintRequest,
    _: Any = Depends(require_admin),
):
    svc = get_moderation_service()
    lines = []
    if payload.lines:
        lines = payload.lines
    elif payload.line:
        lines = [payload.line]
    else:
        raise HTTPException(status_code=400, detail="Provide 'lines' or 'line'")
    try:
        res = svc.lint_blocklist_lines(lines)
        items = [BlocklistLintItem(**it) for it in (res.get("items") or [])]
        return BlocklistLintResponse(items=items, valid_count=int(res.get("valid_count", 0)), invalid_count=int(res.get("invalid_count", 0)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/moderation/test",
    response_model=ModerationTestResponse,
    summary="Test moderation against sample text for a user",
    tags=["moderation"],
)
async def test_moderation(payload: ModerationTestRequest, _: Any = Depends(require_admin)):
    svc = get_moderation_service()
    eff = svc.get_effective_policy(payload.user_id)

    # Determine phase enablement
    phase_enabled = eff.enabled and (eff.input_enabled if payload.phase == 'input' else eff.output_enabled)
    if not phase_enabled:
        return ModerationTestResponse(flagged=False, action='pass', sample=None, redacted_text=None, effective=eff.to_dict())
    if hasattr(svc, 'evaluate_action'):
        eval_res = svc.evaluate_action(payload.text, eff, payload.phase)
        if isinstance(eval_res, tuple) and len(eval_res) >= 3:
            action, redacted, sample = eval_res[0], eval_res[1], eval_res[2]
            category = eval_res[3] if len(eval_res) >= 4 else None
        else:
            action, redacted, sample = eval_res  # type: ignore
            category = None
        flagged = (action != 'pass')
        return ModerationTestResponse(flagged=flagged, action=action if action else 'pass', sample=sample, redacted_text=redacted, effective=eff.to_dict(), category=category)
    else:
        flagged, sample = svc.check_text(payload.text, eff)
        if not flagged:
            return ModerationTestResponse(flagged=False, action='pass', sample=None, redacted_text=None, effective=eff.to_dict())
        action = eff.input_action if payload.phase == 'input' else eff.output_action
        redacted = svc.redact_text(payload.text, eff) if action == 'redact' else None
        return ModerationTestResponse(flagged=True, action=action, sample=sample, redacted_text=redacted, effective=eff.to_dict())
