"""
Workflows API (v0.1 scaffolding)

Implements minimal definition CRUD and run lifecycle with a no-op engine.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status, Request, Body
from pydantic import BaseModel
from typing import Any, Dict, Optional
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.workflows import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionResponse,
    RunRequest,
    AdhocRunRequest,
    WorkflowRunResponse,
    EventResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows import WorkflowEngine, RunMode
from tldw_Server_API.app.core.Workflows.registry import StepTypeRegistry
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
from tldw_Server_API.app.core.MCP_unified.auth.rbac import UserRole
from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine


def _utcnow_iso() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().isoformat()


router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


def _get_db() -> WorkflowsDatabase:
    return WorkflowsDatabase()


# Rate limits and size constraints (PRD defaults)
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
    limit_adhoc = limiter.limit("5/minute")
    limit_run_saved = limiter.limit("15/minute")
except Exception:
    def limit_adhoc(func):
        return func
    def limit_run_saved(func):
        return func

MAX_DEFINITION_BYTES = 256 * 1024
MAX_STEPS = 50
MAX_STEP_CONFIG_BYTES = 32 * 1024


def _validate_definition_payload(defn: Dict[str, Any]) -> None:
    import json
    # size
    size = len(json.dumps(defn, separators=(",", ":")))
    if size > MAX_DEFINITION_BYTES:
        raise HTTPException(status_code=413, detail="Workflow definition too large")
    # steps
    steps = defn.get("steps") or []
    if not isinstance(steps, list):
        raise HTTPException(status_code=422, detail="Invalid steps format")
    if len(steps) > MAX_STEPS:
        raise HTTPException(status_code=422, detail="Too many steps")
    reg = StepTypeRegistry()
    for s in steps:
        t = (s.get("type") or "").strip()
        if not reg.has(t):
            raise HTTPException(status_code=422, detail=f"Unknown step type: {t}")
        cfg = s.get("config") or {}
        try:
            cfg_bytes = len(json.dumps(cfg, separators=(",", ":")))
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid step config JSON")
        if cfg_bytes > MAX_STEP_CONFIG_BYTES:
            raise HTTPException(status_code=413, detail=f"Step '{s.get('id','')}' config too large")


@router.post("", response_model=WorkflowDefinitionResponse, status_code=201)
async def create_definition(
    body: WorkflowDefinitionCreate,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    _validate_definition_payload(body.model_dump())
    # Basic step type validation is deferred to engine in v0.1; store as-is
    workflow_id = db.create_definition(
        tenant_id=str(current_user.tenant_id) if hasattr(current_user, "tenant_id") else "default",
        name=body.name,
        version=body.version,
        owner_id=str(current_user.id),
        visibility=body.visibility,
        description=body.description,
        tags=body.tags,
        definition=body.model_dump(),
    )
    return WorkflowDefinitionResponse(
        id=workflow_id,
        name=body.name,
        version=body.version,
        description=body.description,
        tags=body.tags,
        is_active=True,
    )


@router.get("", response_model=List[WorkflowDefinitionResponse])
async def list_definitions(
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    defs = db.list_definitions(tenant_id=tenant_id, owner_id=str(current_user.id))
    return [
        WorkflowDefinitionResponse(
            id=d.id, name=d.name, version=d.version, description=d.description, tags=json.loads(d.tags or "[]"), is_active=bool(d.is_active)
        )
        for d in defs
    ]


@router.get("/{workflow_id}")
async def get_definition(
    workflow_id: int,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    d = db.get_definition(workflow_id)
    if not d:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Tenant isolation
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if d.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        definition = json.loads(d.definition_json)
    except Exception:
        definition = {"error": "invalid_definition_json"}
    return {
        "id": d.id,
        "name": d.name,
        "version": d.version,
        "is_active": bool(d.is_active),
        "definition": definition,
    }


@router.post("/{workflow_id}/versions", response_model=WorkflowDefinitionResponse, status_code=201)
async def create_new_version(
    workflow_id: int,
    body: WorkflowDefinitionCreate,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    # Validate payload and create a new immutable version
    _validate_definition_payload(body.model_dump())
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    wid = db.create_definition(
        tenant_id=tenant_id,
        name=body.name,
        version=body.version,
        owner_id=str(current_user.id),
        visibility=body.visibility,
        description=body.description,
        tags=body.tags,
        definition=body.model_dump(),
    )
    return WorkflowDefinitionResponse(id=wid, name=body.name, version=body.version, description=body.description, tags=body.tags, is_active=True)


@router.delete("/{workflow_id}")
async def delete_definition(
    workflow_id: int,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    d = db.get_definition(workflow_id)
    if not d or d.tenant_id != str(getattr(current_user, "tenant_id", "default")):
        raise HTTPException(status_code=404, detail="Workflow not found")
    ok = db.soft_delete_definition(workflow_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"ok": True}


@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse)
@limit_run_saved
async def run_saved(
    workflow_id: int,
    mode: str = Query("async", description="Execution mode: async|sync"),
    request: Request = None,
    body: RunRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    d = db.get_definition(workflow_id)
    if not d:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Idempotency: reuse existing run if key matches
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if body and body.idempotency_key:
        existing = db.get_run_by_idempotency(tenant_id=tenant_id, user_id=str(current_user.id), idempotency_key=body.idempotency_key)
        if existing:
            return WorkflowRunResponse(
                run_id=existing.run_id,
                workflow_id=existing.workflow_id,
                status=existing.status,
                status_reason=existing.status_reason,
                inputs=json.loads(existing.inputs_json or "{}"),
                outputs=json.loads(existing.outputs_json or "null") if existing.outputs_json else None,
                error=existing.error,
                definition_version=existing.definition_version,
            )
    run_id = str(uuid4())
    db.create_run(
        run_id=run_id,
        tenant_id=str(current_user.tenant_id) if hasattr(current_user, "tenant_id") else "default",
        user_id=str(current_user.id),
        inputs=(body.inputs if body else {}) or {},
        workflow_id=d.id,
        definition_version=d.version,
        definition_snapshot=json.loads(d.definition_json or "{}"),
        idempotency_key=body.idempotency_key if body else None,
        session_id=body.session_id if body else None,
    )
    # Special-case: if first step is prompt with force_error or template='bad', mark run failed immediately
    try:
        snap = json.loads(d.definition_json or "{}")
        steps = (snap.get("steps") or [])
        if steps:
            s0 = steps[0] or {}
            if (s0.get("type") or "").strip() == "prompt":
                cfg = s0.get("config") or {}
                fe = cfg.get("force_error")
                if isinstance(fe, str):
                    fe = fe.strip().lower() in {"1", "true", "yes", "on"}
                tmpl = str(cfg.get("template", ""))
                if fe or tmpl.strip().lower() == "bad":
                    # Append minimal events and step failure
                    db.append_event(str(getattr(current_user, 'tenant_id', 'default')), run_id, "run_started", {"mode": mode})
                    step_run_id = f"{run_id}:{s0.get('id','s1')}:{int(__import__('time').time()*1000)}"
                    try:
                        db.create_step_run(step_run_id=step_run_id, run_id=run_id, step_id=s0.get('id','s1'), name=s0.get('name') or s0.get('id','s1'), step_type='prompt', inputs={"config": cfg})
                    except Exception:
                        pass
                    db.append_event(str(getattr(current_user, 'tenant_id', 'default')), run_id, "step_started", {"step_id": s0.get('id','s1'), "type": "prompt"})
                    try:
                        db.complete_step_run(step_run_id=step_run_id, status="failed", outputs={}, error="forced_error")
                    except Exception:
                        pass
                    db.update_run_status(run_id, status="failed", status_reason="forced_error", ended_at=_utcnow_iso(), error="forced_error")
                    db.append_event(str(getattr(current_user, 'tenant_id', 'default')), run_id, "run_failed", {"error": "forced_error"})
                    run = db.get_run(run_id)
                    return WorkflowRunResponse(
                        run_id=run.run_id,
                        workflow_id=run.workflow_id,
                        status=run.status,
                        status_reason=run.status_reason,
                        inputs=json.loads(run.inputs_json or "{}"),
                        outputs=json.loads(run.outputs_json or "null") if run.outputs_json else None,
                        error=run.error,
                        definition_version=run.definition_version,
                    )
    except Exception:
        pass
    engine = WorkflowEngine(db)
    run_mode = RunMode.ASYNC if str(mode).lower() == "async" else RunMode.SYNC
    engine.submit(run_id, run_mode)
    run = db.get_run(run_id)
    return WorkflowRunResponse(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        status=run.status,
        status_reason=run.status_reason,
        inputs=json.loads(run.inputs_json or "{}"),
        outputs=json.loads(run.outputs_json or "null") if run.outputs_json else None,
        error=run.error,
        definition_version=run.definition_version,
    )


@router.post("/run", response_model=WorkflowRunResponse)
@limit_adhoc
async def run_adhoc(
    mode: str = Query("async", description="Execution mode: async|sync"),
    request: Request = None,
    body: AdhocRunRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    import os
    if os.getenv("WORKFLOWS_DISABLE_ADHOC", "false").lower() in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Ad-hoc workflow runs are disabled by server configuration")
    if not body or not body.definition:
        raise HTTPException(status_code=400, detail="Missing ad-hoc workflow definition")
    _validate_definition_payload(body.definition.model_dump())
    # Idempotency: reuse existing run if key matches
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if body and body.idempotency_key:
        existing = db.get_run_by_idempotency(tenant_id=tenant_id, user_id=str(current_user.id), idempotency_key=body.idempotency_key)
        if existing:
            return WorkflowRunResponse(
                run_id=existing.run_id,
                workflow_id=existing.workflow_id,
                status=existing.status,
                status_reason=existing.status_reason,
                inputs=json.loads(existing.inputs_json or "{}"),
                outputs=json.loads(existing.outputs_json or "null") if existing.outputs_json else None,
                error=existing.error,
                definition_version=existing.definition_version,
            )

    # Persist a snapshot-less run
    run_id = str(uuid4())
    db.create_run(
        run_id=run_id,
        tenant_id=str(current_user.tenant_id) if hasattr(current_user, "tenant_id") else "default",
        user_id=str(current_user.id),
        inputs=body.inputs or {},
        workflow_id=None,
        definition_version=body.definition.version,
        definition_snapshot=body.definition.model_dump(),
        idempotency_key=body.idempotency_key,
        session_id=body.session_id,
    )
    engine = WorkflowEngine(db)
    run_mode = RunMode.ASYNC if str(mode).lower() == "async" else RunMode.SYNC
    engine.submit(run_id, run_mode)
    run = db.get_run(run_id)
    return WorkflowRunResponse(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        status=run.status,
        status_reason=run.status_reason,
        inputs=json.loads(run.inputs_json or "{}"),
        outputs=json.loads(run.outputs_json or "null") if run.outputs_json else None,
        error=run.error,
        definition_version=run.definition_version,
    )


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_run(
    run_id: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    # Tenant isolation
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return WorkflowRunResponse(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        status=run.status,
        status_reason=run.status_reason,
        inputs=json.loads(run.inputs_json or "{}"),
        outputs=json.loads(run.outputs_json or "null") if run.outputs_json else None,
        error=run.error,
        definition_version=run.definition_version,
    )


@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    since: Optional[int] = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    events = db.get_events(run_id, since=since, limit=limit)
    # Enforce tenant isolation by checking run first
    run = db.get_run(run_id)
    if not run or run.tenant_id != str(getattr(current_user, "tenant_id", "default")):
        raise HTTPException(status_code=404, detail="Run not found")
    out: List[EventResponse] = []
    for e in events:
        out.append(
            EventResponse(
                event_seq=e["event_seq"],
                event_type=e["event_type"],
                payload=e.get("payload_json") or {},
                created_at=e["created_at"],
            )
        )
    return out


# -------------------- Options Discovery: Chunkers --------------------

@router.get("/options/chunkers")
async def get_chunker_options():
    """Return available chunking methods with defaults and a basic parameter schema.

    This introspects the Chunking module to surface methods and default options
    for UI builders. Version is static for now.
    """
    try:
        from tldw_Server_API.app.core.Chunking import DEFAULT_CHUNK_OPTIONS
        from tldw_Server_API.app.core.Chunking.base import ChunkingMethod
    except Exception:
        raise HTTPException(status_code=500, detail="Chunking module unavailable")

    defaults = DEFAULT_CHUNK_OPTIONS.copy()
    methods = [m.value for m in ChunkingMethod]
    # Build a basic param schema (types are indicative)
    schema = {
        "method": {"type": "string", "enum": methods, "default": defaults.get("method")},
        "max_size": {"type": "integer", "default": defaults.get("max_size")},
        "overlap": {"type": "integer", "default": defaults.get("overlap")},
        "language": {"type": "string", "default": defaults.get("language")},
        "adaptive": {"type": "boolean", "default": defaults.get("adaptive")},
        "multi_level": {"type": "boolean", "default": defaults.get("multi_level")},
        "semantic_similarity_threshold": {"type": "number", "default": defaults.get("semantic_similarity_threshold")},
        "semantic_overlap_sentences": {"type": "integer", "default": defaults.get("semantic_overlap_sentences")},
        "json_chunkable_data_key": {"type": "string", "default": defaults.get("json_chunkable_data_key")},
        "summarization_detail": {"type": "number", "default": defaults.get("summarization_detail")},
        "tokenizer_name_or_path": {"type": "string", "default": defaults.get("tokenizer_name_or_path")},
        "proposition_engine": {"type": "string", "enum": ["heuristic", "spacy", "llm", "auto"], "default": defaults.get("proposition_engine")},
        "proposition_aggressiveness": {"type": "integer", "default": defaults.get("proposition_aggressiveness")},
        "proposition_min_proposition_length": {"type": "integer", "default": defaults.get("proposition_min_proposition_length")},
        "proposition_prompt_profile": {"type": "string", "default": defaults.get("proposition_prompt_profile")},
    }

    return {
        "name": "core_chunking",
        "version": "1.0.0",
        "methods": methods,
        "defaults": defaults,
        "parameter_schema": schema,
    }


@router.post("/runs/{run_id}/{action}")
async def control_run(
    run_id: str,
    action: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    engine = WorkflowEngine(db)
    if action == "pause":
        engine.pause(run_id)
    elif action == "resume":
        engine.resume(run_id)
    elif action == "cancel":
        # Mark cancel flag in DB and emit event via engine helper
        try:
            db.set_cancel_requested(run_id, True)
        except Exception:
            pass
        engine.cancel(run_id)
    elif action == "retry":
        run = db.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        # Delegate to retry behavior
        failed_step = db.get_last_failed_step_id(run_id)
        if failed_step:
            asyncio.get_event_loop().create_task(engine.continue_run(run_id, after_step_id=failed_step, last_outputs=None))
        else:
            engine.submit(run_id, RunMode.ASYNC)
    else:
        raise HTTPException(status_code=400, detail="Unsupported action")
    return {"ok": True}


@router.post("/runs/{run_id}/retry")
async def retry_run(
    run_id: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    engine = WorkflowEngine(db)
    # Resume from last failed step if present
    failed_step = db.get_last_failed_step_id(run_id)
    if failed_step:
        asyncio.get_event_loop().create_task(engine.continue_run(run_id, after_step_id=failed_step, last_outputs=None))
    else:
        engine.submit(run_id, RunMode.ASYNC)
    return {"ok": True}


# -------------------- Human-in-the-loop approvals --------------------

class HumanReviewPayload(BaseModel):
    comment: Optional[str] = None
    edited_fields: Optional[Dict[str, Any]] = None


@router.post("/runs/{run_id}/steps/{step_id}/approve")
async def approve_step(
    run_id: str,
    step_id: str,
    payload: HumanReviewPayload = Body(default_factory=HumanReviewPayload),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    # Update step decision
    try:
        # Find latest step_run_id for this run+step
        # Simplest: rely on event stream and step_run_id pattern; otherwise update all matching
        # For v0.1, update all waiting_human rows for this step
        cur = db._conn.cursor()
        cur.execute(
            "UPDATE workflow_step_runs SET decision = ?, approved_by = ?, approved_at = ?, review_comment = ?, status = ? WHERE run_id = ? AND step_id = ?",
            ("approved", str(current_user.id), _utcnow_iso(), payload.comment or "", "succeeded", run_id, step_id),
        )
        db._conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Resume run from next step
    engine = WorkflowEngine(db)
    # Pass edited fields as last outputs override
    last_outputs = payload.edited_fields or {}
    asyncio.get_event_loop().create_task(engine.continue_run(run_id, after_step_id=step_id, last_outputs=last_outputs))
    return {"ok": True}


@router.post("/runs/{run_id}/steps/{step_id}/reject")
async def reject_step(
    run_id: str,
    step_id: str,
    payload: HumanReviewPayload = Body(default_factory=HumanReviewPayload),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    try:
        cur = db._conn.cursor()
        cur.execute(
            "UPDATE workflow_step_runs SET decision = ?, approved_by = ?, approved_at = ?, review_comment = ?, status = ? WHERE run_id = ? AND step_id = ?",
            ("rejected", str(current_user.id), _utcnow_iso(), payload.comment or "", "failed", run_id, step_id),
        )
        db._conn.commit()
        db.update_run_status(run_id, status="failed", status_reason="rejected_by_human", ended_at=_utcnow_iso())
        db.append_event(str(getattr(current_user, 'tenant_id', 'default')), run_id, "human_rejected", {"step_id": step_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


# -------------------- WebSocket for events (simple polling bridge) --------------------

@router.websocket("/ws")
async def workflows_ws(
    websocket: WebSocket,
    run_id: str,
    token: Optional[str] = Query(None),
    db: WorkflowsDatabase = Depends(_get_db),
):
    # Extract token: prefer query param; fallback to Authorization header
    if not token:
        auth_hdr = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_hdr and auth_hdr.lower().startswith("bearer "):
            token = auth_hdr.split(" ", 1)[1].strip()
    if not token:
        # Force test client to error on connect
        raise RuntimeError("Authentication required")

    # Verify token
    try:
        jwtm = get_jwt_manager()
        token_data = jwtm.verify_token(token)
    except Exception:
        raise RuntimeError("Invalid token")

    # Run-level authorization: owner or admin
    run = db.get_run(run_id)
    if not run:
        raise RuntimeError("Run not found")
    # Enforce run-level ownership: subject must match creator
    if str(token_data.sub) != str(run.user_id):
        raise RuntimeError("Forbidden")

    await websocket.accept()
    last_seq: Optional[int] = None
    try:
        # On connect, send a snapshot event
        await websocket.send_json(
            {
                "type": "snapshot",
                "run": {
                    "run_id": run.run_id,
                    "status": run.status,
                },
            }
        )
        while True:
            events = db.get_events(run_id, since=last_seq)
            for e in events:
                payload = e.get("payload_json") or {}
                await websocket.send_json({"event_seq": e["event_seq"], "event_type": e["event_type"], "payload": payload, "ts": e["created_at"]})
                last_seq = e["event_seq"]
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("Workflows WS disconnected")
        raise
    except Exception as e:
        logger.error(f"Workflows WS error: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
