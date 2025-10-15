from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
from tldw_Server_API.app.core.Scheduler import Scheduler
from tldw_Server_API.app.core.Scheduler import create_scheduler


router = APIRouter(prefix="/api/v1/scheduler/workflows", tags=["scheduler", "workflows"])


class ScheduleCreateRequest(BaseModel):
    workflow_id: Optional[int] = Field(None, description="Saved workflow ID; optional if definition snapshot is used")
    name: Optional[str] = None
    cron: str = Field(..., description="Cron expression, e.g., '*/15 * * * *'")
    timezone: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    run_mode: str = Field("async", pattern="^(async|sync)$")
    validation_mode: str = Field("block", pattern="^(block|non-block)$")
    enabled: bool = True


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    cron: Optional[str] = None
    timezone: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    run_mode: Optional[str] = Field(None, pattern="^(async|sync)$")
    validation_mode: Optional[str] = Field(None, pattern="^(block|non-block)$")
    enabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: str
    workflow_id: Optional[int]
    name: Optional[str]
    cron: str
    timezone: Optional[str]
    inputs: Dict[str, Any]
    run_mode: str
    validation_mode: str
    enabled: bool
    tenant_id: str
    user_id: str


@router.post("", response_model=Dict[str, str], status_code=201)
async def create_schedule(
    body: ScheduleCreateRequest,
    current_user: User = Depends(get_request_user),
):
    svc = get_workflows_scheduler()
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    sid = svc.create(
        tenant_id=tenant_id,
        user_id=str(current_user.id),
        workflow_id=body.workflow_id,
        name=body.name,
        cron=body.cron,
        timezone=body.timezone,
        inputs=body.inputs,
        run_mode=body.run_mode,
        validation_mode=body.validation_mode,
        enabled=body.enabled,
    )
    return {"id": sid}


@router.get("", response_model=List[ScheduleResponse])
async def list_schedules(
    owner: Optional[str] = Query(None, description="Admin-only: filter by owner user_id"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_request_user),
):
    svc = get_workflows_scheduler()
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    is_admin = bool(getattr(current_user, "is_admin", False))
    user_filter: Optional[str] = None
    if owner:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Admin-only owner filter")
        user_filter = owner
    else:
        user_filter = str(current_user.id)
    rows = svc.list(tenant_id=tenant_id, user_id=user_filter, limit=limit, offset=offset)
    out: List[ScheduleResponse] = []
    import json
    for r in rows:
        try:
            inputs = json.loads(r.inputs_json or "{}")
        except Exception:
            inputs = {}
        out.append(
            ScheduleResponse(
                id=r.id,
                workflow_id=r.workflow_id,
                name=r.name,
                cron=r.cron,
                timezone=r.timezone,
                inputs=inputs,
                run_mode=r.run_mode or "async",
                validation_mode=r.validation_mode or "block",
                enabled=bool(r.enabled),
                tenant_id=r.tenant_id,
                user_id=r.user_id,
            )
        )
    return out


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    current_user: User = Depends(get_request_user),
):
    svc = get_workflows_scheduler()
    s = svc.get(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(current_user.id) != s.user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    import json
    try:
        inputs = json.loads(s.inputs_json or "{}")
    except Exception:
        inputs = {}
    return ScheduleResponse(
        id=s.id,
        workflow_id=s.workflow_id,
        name=s.name,
        cron=s.cron,
        timezone=s.timezone,
        inputs=inputs,
        run_mode=s.run_mode or "async",
        validation_mode=s.validation_mode or "block",
        enabled=bool(s.enabled),
        tenant_id=s.tenant_id,
        user_id=s.user_id,
    )


@router.patch("/{schedule_id}", response_model=Dict[str, bool])
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdateRequest,
    current_user: User = Depends(get_request_user),
):
    svc = get_workflows_scheduler()
    s = svc.get(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(current_user.id) != s.user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    update: Dict[str, Any] = {}
    if body.name is not None:
        update["name"] = body.name
    if body.cron is not None:
        update["cron"] = body.cron
    if body.timezone is not None:
        update["timezone"] = body.timezone
    if body.inputs is not None:
        update["inputs"] = body.inputs
    if body.run_mode is not None:
        update["run_mode"] = body.run_mode
    if body.validation_mode is not None:
        update["validation_mode"] = body.validation_mode
    if body.enabled is not None:
        update["enabled"] = body.enabled
    ok = svc.update(schedule_id, update)
    return {"ok": bool(ok)}


@router.delete("/{schedule_id}", response_model=Dict[str, bool])
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_request_user),
):
    svc = get_workflows_scheduler()
    s = svc.get(schedule_id)
    if not s:
        return {"ok": False}
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(current_user.id) != s.user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    ok = svc.delete(schedule_id)
    return {"ok": bool(ok)}


@router.post("/{schedule_id}/run-now", response_model=Dict[str, str])
async def run_now(
    schedule_id: str,
    current_user: User = Depends(get_request_user),
):
    svc = get_workflows_scheduler()
    s = svc.get(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(current_user.id) != s.user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    # Submit immediate job to core Scheduler
    payload = {
        "workflow_id": s.workflow_id,
        "inputs": __import__("json").loads(s.inputs_json or "{}"),
        "user_id": s.user_id,
        "tenant_id": s.tenant_id,
        "mode": s.run_mode,
        "validation_mode": s.validation_mode,
    }
    core = await create_scheduler()  # fast path; returns existing instance if already started
    task_id = await core.submit("workflow_run", payload=payload, queue_name="workflows", metadata={"user_id": s.user_id})
    return {"task_id": task_id}

