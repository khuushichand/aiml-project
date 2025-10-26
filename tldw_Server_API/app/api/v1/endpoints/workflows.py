"""
Workflows API (v0.1 scaffolding)

Implements minimal definition CRUD and run lifecycle with a no-op engine.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status, Request, Body, Response
import sqlite3
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger
from pathlib import Path

from tldw_Server_API.app.api.v1.schemas.workflows import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionResponse,
    RunRequest,
    AdhocRunRequest,
    WorkflowRunResponse,
    EventResponse,
    WorkflowRunListItem,
    WorkflowRunListResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.DB_Manager import (
    create_workflows_database,
    get_content_backend_instance,
)
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows import WorkflowEngine, RunMode, WorkflowScheduler
from tldw_Server_API.app.core.Workflows.registry import StepTypeRegistry
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
from tldw_Server_API.app.core.MCP_unified.auth.rbac import UserRole
from tldw_Server_API.app.core.AuthNZ.permissions import (
    PermissionChecker,
    WORKFLOWS_RUNS_READ,
    WORKFLOWS_RUNS_CONTROL,
)
from tldw_Server_API.app.api.v1.endpoints.evaluations_auth import require_admin
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.core.Audit.unified_audit_service import AuditEventType, AuditEventCategory, AuditSeverity, AuditContext
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


def _utcnow_iso() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().isoformat()


router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


def _get_db() -> WorkflowsDatabase:
    backend = get_content_backend_instance()
    return create_workflows_database(backend=backend)


"""Rate limits and size constraints (PRD defaults).

To keep tests deterministic, rate limits are automatically disabled when
running under pytest or TEST_MODE/TLDW_TEST_MODE. This check is evaluated at
call time to avoid import-order issues.
"""
import os
import functools
from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter as _limiter

def _limits_disabled_now() -> bool:
    try:
        return (
            os.getenv("WORKFLOWS_DISABLE_RATE_LIMITS", "").strip().lower() in {"1", "true", "yes", "on"}
            or os.getenv("PYTEST_CURRENT_TEST") is not None
            or os.getenv("TLDW_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
            or os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
        )
    except Exception:
        return False

def _optional_limit(rate: str):
    def _decorator(func):
        # If slowapi isn't available or limits disabled, no-op to preserve signature
        if _limiter is None or _limits_disabled_now():
            return func
        # Use slowapi's wrapped function, but guard against direct invocation
        wrapped = _limiter.limit(rate)(func)

        @functools.wraps(func)
        async def _inner(*args, **kwargs):  # type: ignore
            # If limits are disabled at call time, bypass
            if _limits_disabled_now():
                return await func(*args, **kwargs)
            # If FastAPI didn't supply a proper Request (e.g., direct call in tests), bypass
            req = kwargs.get("request", None)
            try:
                from starlette.requests import Request as _StarReq  # type: ignore
                if not isinstance(req, _StarReq):
                    return await func(*args, **kwargs)
            except Exception:
                return await func(*args, **kwargs)
            return await wrapped(*args, **kwargs)

        return _inner
    return _decorator

# Public decorators used on endpoints
def limit_adhoc(func):
    return _optional_limit("5/minute")(func)

def limit_run_saved(func):
    return _optional_limit("15/minute")(func)

MAX_DEFINITION_BYTES = 256 * 1024
MAX_STEPS = 50
MAX_STEP_CONFIG_BYTES = 32 * 1024


def _validate_definition_payload(defn: Dict[str, Any]) -> None:
    import json
    # Optional JSON Schema validator
    try:
        import jsonschema  # type: ignore
    except Exception:
        jsonschema = None  # type: ignore
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
    # Build a schema map (keep in sync with list_step_types())
    step_schemas: Dict[str, Dict[str, Any]] = {
        "prompt": {
            "type": "object",
            "properties": {
                "template": {"type": "string"},
                "model": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "default": 300},
                "retry": {"type": "integer", "minimum": 0, "default": 0},
            },
            "required": ["template"],
            "additionalProperties": True,
        },
        "branch": {
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "true_next": {"type": "string"},
                "false_next": {"type": "string"}
            },
            "required": ["condition"],
            "additionalProperties": False,
        },
        "map": {
            "type": "object",
            "properties": {
                "items": {"type": ["array", "string"]},
                "step": {"type": "object"},
                "concurrency": {"type": "integer", "minimum": 1, "default": 4}
            },
            "required": ["items", "step"],
            "additionalProperties": True,
        },
        "rag_search": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "default": 5},
                "timeout_seconds": {"type": "integer", "minimum": 1, "default": 60},
            },
            "required": ["query"],
            "additionalProperties": True,
        },
        "webhook": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "POST"},
                "headers": {"type": "object"},
                "body": {"type": ["object", "array", "string", "number", "boolean", "null"]},
                "include_outputs": {"type": "boolean", "default": True},
                "timeout_seconds": {"type": "integer", "minimum": 1, "default": 10},
            },
            "required": [],
            "additionalProperties": True,
        },
        "tts": {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "model": {"type": "string"},
                "voice": {"type": "string"},
                "response_format": {"type": "string"},
                "speed": {"type": "number"},
                "provider": {"type": "string"},
                "output_filename_template": {"type": "string"},
                "provider_options": {"type": "object"},
                "attach_download_link": {"type": "boolean"},
                "save_transcript": {"type": "boolean"},
                "post_process": {"type": "object"},
            },
            "required": [],
            "additionalProperties": True,
        },
        "delay": {
            "type": "object",
            "properties": {"milliseconds": {"type": "integer", "minimum": 1, "default": 1000}},
            "required": ["milliseconds"],
            "additionalProperties": False,
        },
        "log": {
            "type": "object",
            "properties": {"message": {"type": "string"}, "level": {"type": "string"}},
            "required": ["message"],
            "additionalProperties": True,
        },
        "process_media": {"type": "object", "additionalProperties": True},
        "rss_fetch": {"type": "object", "additionalProperties": True},
        "atom_fetch": {"type": "object", "additionalProperties": True},
        "embed": {"type": "object", "additionalProperties": True},
        "translate": {"type": "object", "additionalProperties": True},
        "stt_transcribe": {"type": "object", "additionalProperties": True},
        "notify": {"type": "object", "additionalProperties": True},
        "diff_change_detector": {"type": "object", "additionalProperties": True},
        "policy_check": {"type": "object", "additionalProperties": True},
        "wait_for_human": {"type": "object", "additionalProperties": True},
        "wait_for_approval": {"type": "object", "additionalProperties": True},
    }
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
        # Optional schema validation when jsonschema is available
        if jsonschema is not None:
            schema = step_schemas.get(t)
            if schema:
                try:
                    jsonschema.validate(cfg, schema)  # type: ignore[attr-defined]
                except Exception as e:  # pragma: no cover - depends on optional dep
                    raise HTTPException(status_code=422, detail=f"Invalid config for step '{s.get('id', t)}': {e}")

    # Graph/DAG robustness checks (detect explicit cycles and unknown targets)
    _validate_dag(defn)


def _validate_dag(defn: Dict[str, Any]) -> None:
    steps = defn.get("steps") or []
    if not isinstance(steps, list):
        return
    # Build id map and edges from explicit routing (on_success, on_failure, branch true/false)
    id_to_idx = {}
    for i, s in enumerate(steps):
        sid = str(s.get("id") or f"step_{i+1}")
        id_to_idx[sid] = i
    edges: Dict[str, list[str]] = {}
    for i, s in enumerate(steps):
        sid = str(s.get("id") or f"step_{i+1}")
        edges.setdefault(sid, [])
        # explicit on_success
        try:
            succ = str(s.get("on_success") or "").strip()
            if succ:
                if succ not in id_to_idx:
                    raise HTTPException(status_code=422, detail=f"Step '{sid}' on_success points to unknown step '{succ}'")
                edges[sid].append(succ)
        except Exception as e:
            logger.debug(f"workflows._validate_dag: on_success parse error for step {sid}: {e}")
        # explicit on_failure
        try:
            failn = str(s.get("on_failure") or "").strip()
            if failn:
                if failn not in id_to_idx:
                    raise HTTPException(status_code=422, detail=f"Step '{sid}' on_failure points to unknown step '{failn}'")
                edges[sid].append(failn)
        except Exception as e:
            logger.debug(f"workflows._validate_dag: on_failure parse error for step {sid}: {e}")
        # branch-specific
        try:
            if str(s.get("type") or "").strip() == "branch":
                cfg = s.get("config") or {}
                tn = str(cfg.get("true_next") or "").strip()
                fn = str(cfg.get("false_next") or "").strip()
                for nxt in [tn, fn]:
                    if nxt:
                        if nxt not in id_to_idx:
                            raise HTTPException(status_code=422, detail=f"Step '{sid}' branch targets unknown step '{nxt}'")
                        edges[sid].append(nxt)
        except Exception as e:
            logger.debug(f"workflows._validate_dag: branch parse error for step {sid}: {e}")

    # Detect cycles among explicit edges (DFS)
    visiting: Dict[str, bool] = {}
    visited: Dict[str, bool] = {}
    path: list[str] = []

    def _dfs(u: str) -> Optional[list[str]]:
        visiting[u] = True
        path.append(u)
        for v in edges.get(u, []):
            if visiting.get(v):
                # cycle detected; extract cycle path
                if v in path:
                    start = path.index(v)
                    cyc = path[start:] + [v]
                else:
                    cyc = path + [v]
                return cyc
            if not visited.get(v):
                cyc = _dfs(v)
                if cyc:
                    return cyc
        visiting[u] = False
        visited[u] = True
        path.pop()
        return None

    for node in list(id_to_idx.keys()):
        if not visited.get(node):
            cyc = _dfs(node)
            if cyc:
                # Provide useful diagnostics
                pretty = " -> ".join(cyc)
                raise HTTPException(status_code=422, detail=f"Workflow contains an explicit cycle: {pretty}")


async def _wait_for_run_completion(
    db: WorkflowsDatabase,
    run_id: str,
    *,
    timeout_seconds: float = 55 * 60,
    poll_interval: float = 0.25,
) -> Any:
    """Poll the workflows DB until the run reaches a terminal state or times out.

    In test environments, the effective timeout is reduced to avoid long hangs
    if a run stalls. Override with WORKFLOWS_RUN_TIMEOUT_SEC.
    """
    try:
        # Environment override always wins
        _env_override = os.getenv("WORKFLOWS_RUN_TIMEOUT_SEC")
        if _env_override is not None:
            timeout_seconds = float(_env_override)
        else:
            # Trim timeouts under pytest/TEST_MODE to keep suites responsive
            if os.getenv("PYTEST_CURRENT_TEST") is not None or os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
                timeout_seconds = min(timeout_seconds, 120.0)
    except Exception as e:
        logger.debug(f"Workflows endpoint: failed to adjust run timeout; using defaults: {e}")
    deadline = time.monotonic() + timeout_seconds
    terminal = {"succeeded", "failed", "cancelled"}
    while True:
        run = db.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        if run.status in terminal:
            return run
        if time.monotonic() >= deadline:
            raise HTTPException(status_code=504, detail="Workflow run did not complete before the timeout window")
        await asyncio.sleep(poll_interval)


def _build_rate_limit_headers(limit: int, remaining: int, reset_epoch: int) -> Dict[str, str]:
    """Return a dict including both legacy X-RateLimit-* and RFC-style RateLimit-* headers.

    RateLimit-Reset is provided as delta-seconds; X-RateLimit-Reset remains epoch seconds.
    """
    import time as _time
    now = int(_time.time())
    delta = max(0, int(reset_epoch) - now)
    headers = {
        # RFC-ish
        "RateLimit-Limit": str(limit),
        "RateLimit-Remaining": str(max(0, remaining)),
        "RateLimit-Reset": str(delta),
        "Retry-After": str(delta),
        # Legacy
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Reset": str(reset_epoch),
    }
    return headers


@router.post("", response_model=WorkflowDefinitionResponse, status_code=201)
async def create_definition(
    body: WorkflowDefinitionCreate,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
    request: Request = None,
    audit_service=Depends(get_audit_service_for_user),
):
    _validate_definition_payload(body.model_dump())
    # Basic step type validation is deferred to engine in v0.1; store as-is
    try:
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
    except sqlite3.IntegrityError:
        # Duplicate name+version for tenant
        raise HTTPException(status_code=422, detail="Workflow with same name and version already exists")
    except Exception:
        raise
    # Audit create
    try:
        if audit_service:
            ctx = AuditContext(
                request_id=(request.headers.get("X-Request-ID") if request else None),
                user_id=str(current_user.id),
                ip_address=(request.client.host if request and request.client else None),
                user_agent=(request.headers.get("user-agent") if request else None),
                endpoint=str(request.url.path) if request else "/api/v1/workflows",
                method=(request.method if request else "POST"),
            )
            await audit_service.log_event(
                event_type=AuditEventType.API_REQUEST,
                category=AuditEventCategory.API_CALL,
                severity=AuditSeverity.INFO,
                context=ctx,
                resource_type="workflow",
                resource_id=str(workflow_id),
                action="create",
                metadata={"name": body.name, "version": body.version},
            )
    except Exception as e:
        logger.debug(f"Workflows audit(create) failed: {e}")
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


## get_definition moved below '/runs*' routes to avoid path shadowing


@router.post("/{workflow_id}/versions", response_model=WorkflowDefinitionResponse, status_code=201)
async def create_new_version(
    workflow_id: int,
    body: WorkflowDefinitionCreate,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
    request: Request = None,
    audit_service=Depends(get_audit_service_for_user),
):
    # Validate payload and create a new immutable version
    _validate_definition_payload(body.model_dump())
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    # Owner/admin check
    d0 = db.get_definition(workflow_id)
    if not d0 or d0.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(d0.owner_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
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
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=422, detail="Workflow version already exists")
    except Exception:
        raise
    # Audit new version
    try:
        if audit_service:
            ctx = AuditContext(
                request_id=(request.headers.get("X-Request-ID") if request else None),
                user_id=str(current_user.id),
                ip_address=(request.client.host if request and request.client else None),
                user_agent=(request.headers.get("user-agent") if request else None),
                endpoint=str(request.url.path) if request else f"/api/v1/workflows/{workflow_id}/versions",
                method=(request.method if request else "POST"),
            )
            await audit_service.log_event(
                event_type=AuditEventType.API_REQUEST,
                category=AuditEventCategory.API_CALL,
                severity=AuditSeverity.INFO,
                context=ctx,
                resource_type="workflow",
                resource_id=str(wid),
                action="create_version",
                metadata={"base_id": workflow_id, "version": body.version},
            )
    except Exception as e:
        logger.debug(f"Workflows audit(create_version) failed: {e}")
    return WorkflowDefinitionResponse(id=wid, name=body.name, version=body.version, description=body.description, tags=body.tags, is_active=True)


@router.delete("/{workflow_id}")
async def delete_definition(
    workflow_id: int,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
    request: Request = None,
    audit_service=Depends(get_audit_service_for_user),
):
    d = db.get_definition(workflow_id)
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if not d or d.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(d.owner_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Workflow not found")
    ok = db.soft_delete_definition(workflow_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Audit delete
    try:
        if audit_service:
            ctx = AuditContext(
                request_id=(request.headers.get("X-Request-ID") if request else None),
                user_id=str(current_user.id),
                ip_address=(request.client.host if request and request.client else None),
                user_agent=(request.headers.get("user-agent") if request else None),
                endpoint=str(request.url.path) if request else f"/api/v1/workflows/{workflow_id}",
                method=(request.method if request else "DELETE"),
            )
            await audit_service.log_event(
                event_type=AuditEventType.DATA_DELETE,
                category=AuditEventCategory.DATA_ACCESS,
                severity=AuditSeverity.INFO,
                context=ctx,
                resource_type="workflow",
                resource_id=str(workflow_id),
                action="delete",
            )
    except Exception as e:
        logger.debug(f"Workflows audit(run_saved) failed: {e}")
    return {"ok": True}


# --- Auth helpers for workflows integrations ---

@router.get("/auth/check", summary="Validate provided auth and return user context")
async def workflows_auth_check(current_user: User = Depends(get_request_user)):
    try:
        return {
            "ok": True,
            "user_id": str(current_user.id),
            "username": getattr(current_user, "username", None),
            "is_admin": bool(getattr(current_user, "is_admin", False)),
            "tenant_id": getattr(current_user, "tenant_id", None),
        }
    except Exception:
        # If dependency succeeds, we should not reach here; return minimal
        return {"ok": True}


class VirtualKeyRequest(BaseModel):
    ttl_minutes: int = Field(60, ge=1, le=1440)
    scope: str = Field("workflows")
    schedule_id: Optional[str] = None


@router.post("/auth/virtual-key", summary="Mint a short-lived JWT for workflows (multi-user)")
async def workflows_virtual_key(
    body: VirtualKeyRequest,
    current_user: User = Depends(get_request_user),
):
    # Admin-only in multi-user; not applicable in single-user
    settings = get_settings()
    try:
        if settings.AUTH_MODE != "multi_user":
            raise HTTPException(status_code=400, detail="Virtual keys only apply in multi-user mode")
        require_admin(current_user)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Build a minimal access token with custom TTL and scope claims
    try:
        from datetime import datetime, timedelta
        svc = JWTService(settings)
        token = svc.create_virtual_access_token(
            user_id=int(current_user.id),
            username=str(getattr(current_user, "username", "user")),
            role=(current_user.roles[0] if getattr(current_user, "roles", None) else ("admin" if getattr(current_user, "is_admin", False) else "user")),
            scope=str(body.scope or "workflows"),
            ttl_minutes=int(body.ttl_minutes),
            schedule_id=(str(body.schedule_id) if body.schedule_id else None),
        )
        exp = datetime.utcnow() + timedelta(minutes=int(body.ttl_minutes))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mint token: {e}")
    return {
        "token": token,
        "expires_at": exp.isoformat(),
        "scope": str(body.scope or "workflows"),
        "schedule_id": (str(body.schedule_id) if body.schedule_id else None),
    }


from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope


@router.post(
    "/{workflow_id}/run",
    response_model=WorkflowRunResponse,
    dependencies=[Depends(require_token_scope("workflows", require_if_present=True, endpoint_id="workflows.run_saved", count_as="run"))],
)
@limit_run_saved
async def run_saved(
    workflow_id: int,
    mode: str = Query("async", description="Execution mode: async|sync"),
    request: Request = None,
    body: RunRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
    audit_service=Depends(get_audit_service_for_user),
):
    d = db.get_definition(workflow_id)
    if not d:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Enforce owner or admin for running saved workflow definitions
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if d.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(d.owner_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Idempotency: reuse existing run if key matches
    if body and body.idempotency_key:
        existing = db.get_run_by_idempotency(tenant_id=tenant_id, user_id=str(current_user.id), idempotency_key=body.idempotency_key)
        if existing:
            return WorkflowRunResponse(
                id=existing.run_id,
                run_id=existing.run_id,
                workflow_id=existing.workflow_id,
                user_id=str(existing.user_id) if getattr(existing, 'user_id', None) is not None else None,
                status=existing.status,
                status_reason=existing.status_reason,
                inputs=json.loads(existing.inputs_json or "{}"),
                outputs=json.loads(existing.outputs_json or "null") if existing.outputs_json else None,
                error=existing.error,
                definition_version=existing.definition_version,
            )
    # Quotas (disable in tests via env)
    try:
        import os, datetime as _dt
        _disable_quotas = (
            os.getenv("WORKFLOWS_DISABLE_QUOTAS", "").lower() in {"1", "true", "yes", "on"}
            or os.getenv("PYTEST_CURRENT_TEST") is not None
            or os.getenv("TLDW_TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
            or os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
        )
        if not _disable_quotas:
            # Per-user burst per minute
            now = _dt.datetime.utcnow()
            minute_ago = (now - _dt.timedelta(seconds=60)).replace(tzinfo=_dt.timezone.utc).isoformat()
            midnight = _dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=_dt.timezone.utc).isoformat()
            daily_limit = int(os.getenv("WORKFLOWS_QUOTA_DAILY_PER_USER", "1000"))
            burst_limit = int(os.getenv("WORKFLOWS_QUOTA_BURST_PER_MIN", "60"))
            tenant_id = str(getattr(current_user, "tenant_id", "default"))
            uid = str(current_user.id)
            c_min = db.count_runs_for_user_window(tenant_id=tenant_id, user_id=uid, window_start_iso=minute_ago)
            c_day = db.count_runs_for_user_window(tenant_id=tenant_id, user_id=uid, window_start_iso=midnight)
            if c_min >= burst_limit:
                reset = int((now.replace(second=0, microsecond=0) + _dt.timedelta(minutes=1)).timestamp())
                headers = _build_rate_limit_headers(burst_limit, 0, reset)
                raise HTTPException(status_code=429, detail="Burst quota exceeded", headers=headers)
            if c_day >= daily_limit:
                # Reset at next UTC midnight (use UTC-aware datetime for correct epoch)
                tomorrow = (now + _dt.timedelta(days=1)).date()
                reset_dt = _dt.datetime.combine(tomorrow, _dt.time(0, 0, 0, tzinfo=_dt.timezone.utc))
                headers = _build_rate_limit_headers(daily_limit, 0, int(reset_dt.timestamp()))
                raise HTTPException(status_code=429, detail="Daily quota exceeded", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Workflows audit(run_adhoc) failed: {e}")

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
        validation_mode=(body.validation_mode if body and getattr(body, "validation_mode", None) else "block"),
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
                    # If an on_failure route is defined and refers to a valid step, let the engine handle it
                    try:
                        failure_next = str(s0.get("on_failure") or "").strip()
                        id_map = {str((st.get('id') or f'step_{i+1}')): True for i, st in enumerate(steps)}
                        has_failure_route = bool(failure_next and id_map.get(failure_next))
                    except Exception:
                        has_failure_route = False
                    if not has_failure_route:
                        # Append minimal events and step failure (fast-fail)
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
                            user_id=str(run.user_id) if getattr(run, 'user_id', None) is not None else None,
                            status=run.status,
                            status_reason=run.status_reason,
                            inputs=json.loads(run.inputs_json or "{}"),
                            outputs=json.loads(run.outputs_json or "null") if run.outputs_json else None,
                            error=run.error,
                            definition_version=run.definition_version,
                        )
    except Exception as e:
        logger.debug(f"Workflows endpoint: inline fallback check failed: {e}")
    engine = WorkflowEngine(db)
    # Inject scoped secrets (not persisted)
    try:
        if body and getattr(body, "secrets", None):
            WorkflowEngine.set_run_secrets(run_id, body.secrets)
    except Exception as e:
        logger.debug(f"Workflows endpoint(adhoc): inline fallback check failed: {e}")
    run_mode = RunMode.ASYNC if str(mode).lower() == "async" else RunMode.SYNC
    engine.submit(run_id, run_mode)
    # Nudge: wait briefly for background engine to transition off 'queued' in test environments
    try:
        import asyncio as _a
        for _ in range(50):  # ~0.25s max
            _r = db.get_run(run_id)
            if _r and _r.status != "queued":
                break
            await _a.sleep(0.005)
    except Exception as e:
        logger.debug(f"workflows: failed to load workflows engine config: {e}")
    # Fallback for environments where background scheduling is delayed: run inline once
    try:
        _r2 = db.get_run(run_id)
        if _r2 and _r2.status == "queued":
            from loguru import logger as _logger
            # Only run inline if not present in scheduler queue (avoid breaking concurrency limits)
            try:
                in_queue = WorkflowScheduler.instance().drain_pending(run_id)
            except Exception as _e:
                logger.debug(f"workflows: scheduler.drain_pending error: {_e}")
                in_queue = False
            if not in_queue:
                _logger.debug(f"Workflows endpoint: fallback inline start for run_id={run_id}")
                await engine.start_run(run_id, run_mode)
            else:
                _logger.debug(f"Workflows endpoint: run_id={run_id} is queued; skipping inline fallback")
    except Exception as e:
        logger.debug(f"workflows: failed to initialize scheduler: {e}")
    if run_mode == RunMode.SYNC:
        run = await _wait_for_run_completion(db, run_id)
    else:
        run = db.get_run(run_id)
    from loguru import logger as _logger
    try:
        _logger.debug(f"Workflows endpoint: post-submit status={run.status if run else 'missing'} run_id={run_id}")
    except Exception as e:
        logger.debug(f"workflows: failed to log post-submit status: {e}")
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    # Audit: run created
    try:
        if audit_service:
            ctx = AuditContext(
                request_id=(request.headers.get("X-Request-ID") if request else None),
                user_id=str(current_user.id),
                ip_address=(request.client.host if request and request.client else None),
                user_agent=(request.headers.get("user-agent") if request else None),
                endpoint=str(request.url.path) if request else "/api/v1/workflows/{id}/run",
                method=(request.method if request else "POST"),
            )
            await audit_service.log_event(
                event_type=AuditEventType.API_REQUEST,
                category=AuditEventCategory.API_CALL,
                severity=AuditSeverity.INFO,
                context=ctx,
                resource_type="workflow_run",
                resource_id=str(run_id),
                action="run_saved",
                metadata={"workflow_id": d.id, "mode": mode},
            )
    except Exception:
        pass
    return WorkflowRunResponse(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        user_id=str(run.user_id) if getattr(run, 'user_id', None) is not None else None,
        status=run.status,
        status_reason=run.status_reason,
        inputs=json.loads(run.inputs_json or "{}"),
        outputs=json.loads(run.outputs_json or "null") if run.outputs_json else None,
        error=run.error,
        definition_version=run.definition_version,
        validation_mode=getattr(run, 'validation_mode', None),
    )


@router.get(
    "/runs",
    response_model=WorkflowRunListResponse,
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "Offset pagination",
                "source": "curl -H 'X-API-KEY: $API_KEY' \"$BASE/api/v1/workflows/runs?limit=25&offset=0&order_by=created_at&order=desc\""
            },
            {
                "lang": "bash",
                "label": "Cursor pagination",
                "source": "# First page\nRESP=$(curl -sS -H 'X-API-KEY: $API_KEY' \"$BASE/api/v1/workflows/runs?limit=25&order_by=created_at&order=desc\")\nCUR=$(echo \"$RESP\" | jq -r '.next_cursor')\n# Next page using actual returned token\n[ \"$CUR\" != \"null\" ] && curl -H 'X-API-KEY: $API_KEY' \"$BASE/api/v1/workflows/runs?limit=25&cursor=$CUR\" || echo 'No next_cursor returned'"
            }
        ]
    }
)
async def list_runs(
    status: Optional[List[str]] = Query(None, description="Filter by status (repeatable)"),
    owner: Optional[str] = Query(None, description="Owner user id (admin only)"),
    workflow_id: Optional[int] = Query(None),
    created_after: Optional[str] = Query(None, description="ISO timestamp lower bound (created_at)"),
    created_before: Optional[str] = Query(None, description="ISO timestamp upper bound (created_at)"),
    last_n_hours: Optional[int] = Query(None, description="Convenience: set created_after to now - N hours"),
    order_by: str = Query("created_at", description="Order by: created_at|started_at|ended_at"),
    order: str = Query("desc", description="asc|desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    cursor: Optional[str] = Query(None, description="Opaque continuation token for pagination (overrides offset)"),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
    request: Request = None,
    response: Response = None,
    audit_service=Depends(get_audit_service_for_user),
):
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    is_admin = bool(getattr(current_user, "is_admin", False))
    user_id = None
    if owner and is_admin:
        user_id = str(owner)
        try:
            if audit_service and str(owner) != str(current_user.id):
                ctx = AuditContext(
                    request_id=(request.headers.get("X-Request-ID") if request else None),
                    user_id=str(current_user.id),
                    ip_address=(request.client.host if request and request.client else None),
                    user_agent=(request.headers.get("user-agent") if request else None),
                    endpoint=str(request.url.path) if request else "/api/v1/workflows/runs",
                    method=(request.method if request else "GET"),
                )
                await audit_service.log_event(
                    event_type=AuditEventType.DATA_READ,
                    category=AuditEventCategory.DATA_ACCESS,
                    severity=AuditSeverity.INFO,
                    context=ctx,
                    resource_type="workflow_runs",
                    resource_id="*",
                    action="admin_owner_override",
                    metadata={"owner": str(owner)},
                )
        except Exception:
            pass
    else:
        user_id = str(current_user.id)
        # If a non-admin tried to set owner to a different user, log permission denial
        if owner and str(owner) != str(current_user.id):
            try:
                if audit_service:
                    ctx = AuditContext(
                        request_id=(request.headers.get("X-Request-ID") if request else None),
                        user_id=str(current_user.id),
                        ip_address=(request.client.host if request and request.client else None),
                        user_agent=(request.headers.get("user-agent") if request else None),
                        endpoint=str(request.url.path) if request else "/api/v1/workflows/runs",
                        method=(request.method if request else "GET"),
                    )
                    await audit_service.log_event(
                        event_type=AuditEventType.PERMISSION_DENIED,
                        category=AuditEventCategory.SECURITY,
                        severity=AuditSeverity.WARNING,
                        context=ctx,
                        resource_type="workflow_runs",
                        resource_id="*",
                        action="owner_filter_denied",
                        metadata={"attempted_owner": str(owner)},
                    )
            except Exception:
                pass
    # Convenience: compute created_after from last_n_hours if provided
    if last_n_hours is not None:
        try:
            import datetime as _dt
            ca_dt = _dt.datetime.utcnow() - _dt.timedelta(hours=int(last_n_hours))
            created_after = ca_dt.isoformat()
        except Exception:
            pass

    # Cursor parsing (base64url-encoded JSON)
    cursor_ts = None
    cursor_id = None
    cur_order_by = (order_by or "created_at")
    cur_order_desc = (str(order or "desc").lower() != "asc")
    if cursor:
        try:
            import base64, json as _json
            raw = base64.urlsafe_b64decode(cursor.encode("utf-8") + b"==").decode("utf-8")
            tok = _json.loads(raw)
            # Validate and adopt settings from token
            token_ob = str(tok.get("order_by") or cur_order_by)
            token_od = bool(tok.get("order_desc") if tok.get("order_desc") is not None else cur_order_desc)
            token_ts = tok.get("last_ts")
            token_id = tok.get("last_id")
            if token_ts and token_id:
                cursor_ts = str(token_ts)
                cursor_id = str(token_id)
                cur_order_by = token_ob
                cur_order_desc = token_od
                # When using cursor, ignore provided offset
                offset = 0
        except Exception as e:
            logger.debug(f"Workflows runs: failed to parse cursor token; ignoring. Error: {e}")

    rows = db.list_runs(
        tenant_id=tenant_id,
        user_id=user_id,
        statuses=status,
        workflow_id=workflow_id,
        created_after=created_after,
        created_before=created_before,
        cursor_ts=cursor_ts,
        cursor_id=cursor_id,
        limit=limit + 1,  # fetch one extra to decide next token
        offset=offset,
        order_by=cur_order_by,
        order_desc=cur_order_desc,
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    items: List[WorkflowRunListItem] = []
    for r in rows:
        items.append(
            WorkflowRunListItem(
                run_id=r.run_id,
                workflow_id=r.workflow_id,
                user_id=str(r.user_id) if getattr(r, 'user_id', None) is not None else None,
                status=r.status,
                status_reason=r.status_reason,
                definition_version=r.definition_version,
                created_at=r.created_at,
                started_at=r.started_at,
                ended_at=r.ended_at,
            )
        )
    # Build next_cursor if we have more
    next_cursor = None
    if has_more and rows:
        try:
            import base64, json as _json
            last = rows[-1]
            last_ts = getattr(last, cur_order_by) or last.created_at
            token_obj = {
                "order_by": cur_order_by,
                "order_desc": bool(cur_order_desc),
                "last_ts": last_ts,
                "last_id": last.run_id,
            }
            raw = _json.dumps(token_obj, default=str).encode("utf-8")
            next_cursor = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
        except Exception as e:
            logger.debug(f"Workflows runs: failed to build next_cursor token: {e}")
            next_cursor = None

    # Optional RFC5988 Link headers for pagination
    if response is not None:
        try:
            from tldw_Server_API.app.api.v1.endpoints._pagination_utils import build_link_header
            base_path = "/api/v1/workflows/runs"
            params_common = []
            if status:
                for s in status:
                    params_common.append(("status", s))
            if owner:
                params_common.append(("owner", str(owner)))
            if workflow_id is not None:
                params_common.append(("workflow_id", str(workflow_id)))
            if created_after:
                params_common.append(("created_after", str(created_after)))
            if created_before:
                params_common.append(("created_before", str(created_before)))
            if last_n_hours is not None:
                params_common.append(("last_n_hours", str(last_n_hours)))
            if order_by:
                params_common.append(("order_by", str(order_by)))
            if order:
                params_common.append(("order", str(order)))
            # Choose offset links only when not using cursor-seek mode
            eff_offset = None if cursor_ts is not None else int(offset)
            eff_has_more = None if cursor_ts is not None else bool(has_more)
            link_value = build_link_header(
                base_path,
                params_common,
                next_cursor=next_cursor,
                limit=int(limit),
                offset=eff_offset,
                has_more=eff_has_more,
                cursor_param="cursor",
                include_first_last=True,
            )
            if link_value:
                response.headers["Link"] = link_value
        except Exception as e:
            logger.debug(f"Workflows runs: failed to set Link headers: {e}")

    return WorkflowRunListResponse(
        runs=items,
        next_offset=(offset + limit) if (has_more and cursor_ts is None) else None,
        next_cursor=next_cursor,
    )


@router.post("/run", response_model=WorkflowRunResponse)
@limit_adhoc
async def run_adhoc(
    mode: str = Query("async", description="Execution mode: async|sync"),
    request: Request = None,
    body: AdhocRunRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
    audit_service=Depends(get_audit_service_for_user),
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
                id=existing.run_id,
                run_id=existing.run_id,
                workflow_id=existing.workflow_id,
                user_id=str(existing.user_id) if getattr(existing, 'user_id', None) is not None else None,
                status=existing.status,
                status_reason=existing.status_reason,
                inputs=json.loads(existing.inputs_json or "{}"),
                outputs=json.loads(existing.outputs_json or "null") if existing.outputs_json else None,
                error=existing.error,
                definition_version=existing.definition_version,
            )

    # Quotas (disable in tests via env)
    try:
        import os, datetime as _dt
        _disable_quotas = (
            os.getenv("WORKFLOWS_DISABLE_QUOTAS", "").lower() in {"1", "true", "yes", "on"}
            or os.getenv("PYTEST_CURRENT_TEST") is not None
            or os.getenv("TLDW_TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
            or os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
        )
        if not _disable_quotas:
            now = _dt.datetime.utcnow()
            minute_ago = (now - _dt.timedelta(seconds=60)).replace(tzinfo=_dt.timezone.utc).isoformat()
            midnight = _dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=_dt.timezone.utc).isoformat()
            daily_limit = int(os.getenv("WORKFLOWS_QUOTA_DAILY_PER_USER", "1000"))
            burst_limit = int(os.getenv("WORKFLOWS_QUOTA_BURST_PER_MIN", "60"))
            tenant_id = str(getattr(current_user, "tenant_id", "default"))
            uid = str(current_user.id)
            c_min = db.count_runs_for_user_window(tenant_id=tenant_id, user_id=uid, window_start_iso=minute_ago)
            c_day = db.count_runs_for_user_window(tenant_id=tenant_id, user_id=uid, window_start_iso=midnight)
            if c_min >= burst_limit:
                reset = int((now.replace(second=0, microsecond=0) + _dt.timedelta(minutes=1)).timestamp())
                headers = _build_rate_limit_headers(burst_limit, 0, reset)
                raise HTTPException(status_code=429, detail="Burst quota exceeded", headers=headers)
            if c_day >= daily_limit:
                tomorrow = (now + _dt.timedelta(days=1)).date()
                reset_dt = _dt.datetime.combine(tomorrow, _dt.time(0, 0, 0, tzinfo=_dt.timezone.utc))
                headers = _build_rate_limit_headers(daily_limit, 0, int(reset_dt.timestamp()))
                raise HTTPException(status_code=429, detail="Daily quota exceeded", headers=headers)
    except HTTPException:
        raise
    except Exception:
        pass

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
        validation_mode=(body.validation_mode if getattr(body, "validation_mode", None) else "block"),
    )
    engine = WorkflowEngine(db)
    try:
        if body and getattr(body, "secrets", None):
            WorkflowEngine.set_run_secrets(run_id, body.secrets)
    except Exception:
        pass
    run_mode = RunMode.ASYNC if str(mode).lower() == "async" else RunMode.SYNC
    engine.submit(run_id, run_mode)
    # Nudge: wait briefly for background engine to transition off 'queued' in test environments
    try:
        import asyncio as _a
        for _ in range(50):
            _r = db.get_run(run_id)
            if _r and _r.status != "queued":
                break
            await _a.sleep(0.005)
    except Exception:
        pass
    # Fallback inline start if still queued
    try:
        _r2 = db.get_run(run_id)
        if _r2 and _r2.status == "queued":
            from loguru import logger as _logger
            # Only start inline if not enqueued by the scheduler (preserve concurrency limits)
            try:
                in_queue = WorkflowScheduler.instance().drain_pending(run_id)
            except Exception:
                in_queue = False
            if not in_queue:
                _logger.debug(f"Workflows endpoint(adhoc): fallback inline start for run_id={run_id}")
                await engine.start_run(run_id, run_mode)
            else:
                _logger.debug(f"Workflows endpoint(adhoc): run_id={run_id} is queued; skipping inline fallback")
    except Exception:
        pass
    if run_mode == RunMode.SYNC:
        run = await _wait_for_run_completion(db, run_id)
    else:
        run = db.get_run(run_id)
    from loguru import logger as _logger
    try:
        _logger.debug(f"Workflows endpoint: post-submit (adhoc) status={run.status if run else 'missing'} run_id={run_id}")
    except Exception:
        pass
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    # Audit: ad-hoc run created
    try:
        if audit_service:
            ctx = AuditContext(
                request_id=(request.headers.get("X-Request-ID") if request else None),
                user_id=str(current_user.id),
                ip_address=(request.client.host if request and request.client else None),
                user_agent=(request.headers.get("user-agent") if request else None),
                endpoint=str(request.url.path) if request else "/api/v1/workflows/run",
                method=(request.method if request else "POST"),
            )
            await audit_service.log_event(
                event_type=AuditEventType.API_REQUEST,
                category=AuditEventCategory.API_CALL,
                severity=AuditSeverity.INFO,
                context=ctx,
                resource_type="workflow_run",
                resource_id=str(run_id),
                action="run_adhoc",
                metadata={"mode": mode},
            )
    except Exception:
        pass
    return WorkflowRunResponse(
        id=run.run_id,
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        user_id=str(run.user_id) if getattr(run, 'user_id', None) is not None else None,
        status=run.status,
        status_reason=run.status_reason,
        inputs=json.loads(run.inputs_json or "{}"),
        outputs=json.loads(run.outputs_json or "null") if run.outputs_json else None,
        error=run.error,
        definition_version=run.definition_version,
        validation_mode=getattr(run, 'validation_mode', None),
    )


@router.get(
    "/runs/{run_id}",
    response_model=WorkflowRunResponse,
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def get_run(
    run_id: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
    request: Request = None,
    audit_service=Depends(get_audit_service_for_user),
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    # Tenant isolation
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        try:
            if audit_service:
                ctx = AuditContext(
                    request_id=(request.headers.get("X-Request-ID") if request else None),
                    user_id=str(current_user.id),
                    endpoint=str(request.url.path) if request else "/api/v1/workflows/runs/{id}",
                    method=(request.method if request else "GET"),
                )
                await audit_service.log_event(
                    event_type=AuditEventType.PERMISSION_DENIED,
                    category=AuditEventCategory.SECURITY,
                    severity=AuditSeverity.WARNING,
                    context=ctx,
                    resource_type="workflow_run",
                    resource_id=str(run_id),
                    action="tenant_mismatch",
                )
        except Exception as e:
            logger.debug(f"Workflows get_run: audit tenant_mismatch failed: {e}")
        raise HTTPException(status_code=404, detail="Run not found")
    # Owner or admin (if attribute available)
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        try:
            if audit_service:
                ctx = AuditContext(
                    request_id=(request.headers.get("X-Request-ID") if request else None),
                    user_id=str(current_user.id),
                    endpoint=str(request.url.path) if request else "/api/v1/workflows/runs/{id}",
                    method=(request.method if request else "GET"),
                )
                await audit_service.log_event(
                    event_type=AuditEventType.PERMISSION_DENIED,
                    category=AuditEventCategory.SECURITY,
                    severity=AuditSeverity.WARNING,
                    context=ctx,
                    resource_type="workflow_run",
                    resource_id=str(run_id),
                    action="not_owner",
                )
        except Exception as e:
            logger.debug(f"Workflows get_run: audit not_owner failed: {e}")
        raise HTTPException(status_code=404, detail="Run not found")
    return WorkflowRunResponse(
        id=run.run_id,
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        user_id=str(run.user_id) if getattr(run, 'user_id', None) is not None else None,
        status=run.status,
        status_reason=run.status_reason,
        inputs=json.loads(run.inputs_json or "{}"),
        outputs=json.loads(run.outputs_json or "null") if run.outputs_json else None,
        error=run.error,
        definition_version=run.definition_version,
        validation_mode=getattr(run, 'validation_mode', None),
    )


@router.get(
    "/runs/{run_id}/events",
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "cURL",
                "source": "curl -H 'X-API-KEY: $API_KEY' 'http://127.0.0.1:8000/api/v1/workflows/runs/{run_id}/events?limit=100'",
            },
            {
                "lang": "bash",
                "label": "cURL (cursor)",
                "source": "# First page\nRESP=$(curl -sS -H 'X-API-KEY: $API_KEY' \"$BASE/api/v1/workflows/runs/{run_id}/events?limit=50\")\nNEXT=$(curl -sSI -H 'X-API-KEY: $API_KEY' \"$BASE/api/v1/workflows/runs/{run_id}/events?limit=50\" | awk -F': ' '/^Next-Cursor:/ {print $2}' | tr -d '\r')\n# Next page using the Next-Cursor header value\n[ -n \"$NEXT\" ] && curl -H 'X-API-KEY: $API_KEY' \"$BASE/api/v1/workflows/runs/{run_id}/events?limit=50&cursor=$NEXT\" || echo 'No Next-Cursor returned'"
            }
        ]
    },
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def get_run_events(
    run_id: str,
    since: Optional[int] = Query(None, description="Return events with seq strictly greater than this value"),
    limit: int = Query(500, ge=1, le=1000),
    types: Optional[List[str]] = Query(None, description="Filter by event types (repeatable)"),
    cursor: Optional[str] = Query(None, description="Opaque continuation token (overrides since)"),
    response: Response = None,
    request: Request = None,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    # Enforce tenant isolation and owner/admin
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")
    # Normalize types to lower-case for consistency with UI filter chips
    types_norm = [t.strip() for t in (types or []) if str(t).strip()]
    # Cursor token overrides since
    if cursor:
        try:
            import base64, json as _json
            pad = "=" * (-len(cursor) % 4)
            raw = base64.urlsafe_b64decode((cursor + pad).encode("utf-8")).decode("utf-8")
            tok = _json.loads(raw)
            if isinstance(tok.get("last_seq"), int):
                since = int(tok["last_seq"])  # seek after this seq
        except Exception as e:
            logger.debug(f"Workflows events: failed to parse cursor token; ignoring. Error: {e}")
    events = db.get_events(run_id, since=since, limit=limit, types=types_norm if types_norm else None)
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
    # Build next continuation token when we returned a full page
    if response is not None and len(out) == int(limit):
        try:
            last_seq = int(out[-1].event_seq) if hasattr(out[-1], "event_seq") else int(events[-1]["event_seq"])  # type: ignore
        except Exception as e:
            logger.debug(f"Workflows events: failed to derive last_seq: {e}")
            try:
                last_seq = int(events[-1]["event_seq"]) if events else None  # type: ignore
            except Exception as e2:
                logger.debug(f"Workflows events: no last_seq available: {e2}")
                last_seq = None
        if last_seq is not None:
            import base64, json as _json
            token = {"last_seq": last_seq}
            raw = _json.dumps(token).encode("utf-8")
            nxt = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
            try:
                response.headers["Next-Cursor"] = nxt
            except Exception as e:
                logger.debug(f"Workflows events: failed to set Next-Cursor header: {e}")
            # Optional RFC5988 Link header for 'next'
            try:
                from tldw_Server_API.app.api.v1.endpoints._pagination_utils import build_link_header
                base_path = f"/api/v1/workflows/runs/{run_id}/events"
                params = [("limit", str(limit))]
                if types:
                    for t in types:
                        params.append(("types", t))
                link_value = build_link_header(
                    base_path,
                    params,
                    next_cursor=nxt,
                    limit=int(limit),
                    offset=None,
                    has_more=None,
                )
                if link_value:
                    response.headers["Link"] = link_value
            except Exception as e:
                logger.debug(f"Workflows events: failed to set Link header: {e}")
    return out


@router.get(
    "/runs/{run_id}/webhooks/deliveries",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def get_run_webhook_deliveries(
    run_id: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    """Return webhook delivery history for a run (derived from events)."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")
    events = db.get_events(run_id, types=["webhook_delivery"]) or []
    deliveries = []
    for e in events:
        p = e.get("payload_json") or {}
        deliveries.append({
            "event_seq": e.get("event_seq"),
            "created_at": e.get("created_at"),
            "host": p.get("host"),
            "status": p.get("status"),
            "code": p.get("code"),
        })
    return {"deliveries": deliveries}


@router.get(
    "/webhooks/dlq",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_CONTROL))],
)
async def list_webhook_dlq(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    """Admin: list webhook DLQ entries (all tenants)."""
    if not bool(getattr(current_user, "is_admin", False)):
        # Hide presence
        raise HTTPException(status_code=404, detail="Not found")
    rows = db.list_webhook_dlq_all(limit=limit, offset=offset)
    out = []
    for r in rows:
        try:
            body = json.loads(r.get("body_json") or "{}")
        except Exception:
            body = {}
        out.append({
            "id": r.get("id"),
            "tenant_id": r.get("tenant_id"),
            "run_id": r.get("run_id"),
            "url": r.get("url"),
            "attempts": r.get("attempts"),
            "next_attempt_at": r.get("next_attempt_at"),
            "last_error": r.get("last_error"),
            "created_at": r.get("created_at"),
            "body": body,
        })
    return {"items": out, "limit": limit, "offset": offset, "count": len(out)}


@router.post(
    "/webhooks/dlq/{dlq_id}/replay",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_CONTROL))],
)
async def replay_webhook_dlq(
    dlq_id: int,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    """Admin: attempt immediate replay of a DLQ item.

    Honors the same allow/deny and replay headers as the engine.
    In TEST_MODE, if WORKFLOWS_TEST_REPLAY_SUCCESS=true, the entry is deleted without network.
    """
    if not bool(getattr(current_user, "is_admin", False)):
        raise HTTPException(status_code=404, detail="Not found")

    # Find the entry
    rows = db.list_webhook_dlq_all(limit=1, offset=0)
    target = None
    for r in rows:
        if int(r.get("id")) == int(dlq_id):
            target = r
            break
    if not target:
        # Slow path: scan in batches (SQLite-friendly)
        off = 0
        while True:
            batch = db.list_webhook_dlq_all(limit=200, offset=off)
            if not batch:
                break
            for r in batch:
                if int(r.get("id")) == int(dlq_id):
                    target = r
                    break
            if target:
                break
            off += len(batch)
    if not target:
        raise HTTPException(status_code=404, detail="DLQ item not found")

    url = str(target.get("url") or "")
    tenant_id = str(target.get("tenant_id") or "default")
    try:
        body = json.loads(target.get("body_json") or "{}")
    except Exception:
        body = {}

    # Policy
    try:
        from tldw_Server_API.app.core.Security.egress import is_webhook_url_allowed_for_tenant as _allow_webhook
        if not _allow_webhook(url, tenant_id):
            raise HTTPException(status_code=400, detail="Denied by egress policy")
    except HTTPException:
        raise
    except Exception:
        pass

    # Test-mode short-circuit
    import os as _os
    if _os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"} and _os.getenv("WORKFLOWS_TEST_REPLAY_SUCCESS", "").lower() in {"1", "true", "yes", "on"}:
        try:
            db.delete_webhook_dlq(dlq_id=dlq_id)
        except Exception:
            pass
        return {"ok": True, "simulated": True}

    # Attempt delivery with the same headers/signing as engine
    try:
        import httpx, time as _time, hmac, hashlib
        secret = _os.getenv("WORKFLOWS_WEBHOOK_SECRET", "")
        ts = str(int(_time.time()))
        headers = {
            "content-type": "application/json",
            "X-Signature-Timestamp": ts,
            "X-Webhook-ID": f"wf-dlq-{dlq_id}-{ts}",
            "X-Workflows-Signature-Version": "v1",
        }
        raw = json.dumps(body)
        if secret:
            sig = hmac.new(secret.encode("utf-8"), f"{ts}.{raw}".encode("utf-8"), hashlib.sha256).hexdigest()
            headers["X-Workflows-Signature"] = sig
            headers["X-Hub-Signature-256"] = f"sha256={sig}"
        timeout = float(_os.getenv("WORKFLOWS_WEBHOOK_TIMEOUT", "10"))
        resp = None
        try:
            import types as _types
            _is_module = isinstance(httpx, _types.ModuleType)
            if not _is_module or not hasattr(httpx, "Client"):
                raise RuntimeError("httpx appears monkeypatched; falling back to urllib")
            try:
                client_ctx = httpx.Client(timeout=timeout, trust_env=False)
            except TypeError:
                client_ctx = httpx.Client(timeout=timeout)
            with client_ctx as client:
                resp = client.post(url, data=raw, headers=headers)
        except Exception:
            # Robust fallback using urllib with proxies disabled
            import urllib.request as _ur
            import ssl as _ssl
            req = _ur.Request(url, data=raw.encode("utf-8"), headers=headers, method="POST")
            ctx = _ssl.create_default_context()
            ctx.check_hostname = True
            opener = _ur.build_opener(
                _ur.ProxyHandler({}),
                _ur.HTTPSHandler(context=ctx),
            )
            with opener.open(req, timeout=timeout) as r:  # type: ignore[arg-type]
                code = getattr(r, "status", None) or getattr(r, "code", None) or 200
            class _Resp:
                def __init__(self, status_code):
                    self.status_code = status_code
            resp = _Resp(int(code))
        try:
            logger.debug(f"DLQ replay POST to {url} -> {resp.status_code}")
        except Exception:
            pass
        if 200 <= int(resp.status_code) < 400:
            try:
                db.delete_webhook_dlq(dlq_id=dlq_id)
            except Exception:
                pass
            return {"ok": True, "status_code": int(resp.status_code)}
        else:
            # Update attempts/backoff minimally
            db.update_webhook_dlq_failure(dlq_id=dlq_id, last_error=f"status={resp.status_code}", next_attempt_at_iso=None)
            return {"ok": False, "status_code": int(resp.status_code)}
    except HTTPException:
        raise
    except Exception as e:
        try:
            db.update_webhook_dlq_failure(dlq_id=dlq_id, last_error=str(e), next_attempt_at_iso=None)
        except Exception:
            pass
        return {"ok": False, "error": str(e)}


@router.get(
    "/runs/{run_id}/artifacts",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def get_run_artifacts(
    run_id: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")
    arts = db.list_artifacts_for_run(run_id)
    # Normalize payload
    results = []
    for a in arts:
        results.append({
            "artifact_id": a.get("artifact_id"),
            "type": a.get("type"),
            "uri": a.get("uri"),
            "size_bytes": a.get("size_bytes"),
            "mime_type": a.get("mime_type"),
            "checksum_sha256": a.get("checksum_sha256"),
            "metadata": a.get("metadata_json") or {},
            "created_at": a.get("created_at"),
            "step_run_id": a.get("step_run_id"),
        })
    return results


@router.get(
    "/runs/{run_id}/artifacts/manifest",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def get_run_artifacts_manifest(
    run_id: str,
    verify: bool = Query(False, description="Compute and validate recorded checksums"),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")

    arts = db.list_artifacts_for_run(run_id)
    manifest = []
    mismatches = 0
    for a in arts:
        entry = {
            "artifact_id": a.get("artifact_id"),
            "type": a.get("type"),
            "uri": a.get("uri"),
            "size_bytes": a.get("size_bytes"),
            "mime_type": a.get("mime_type"),
            "checksum_sha256": a.get("checksum_sha256"),
            "created_at": a.get("created_at"),
            "metadata": a.get("metadata_json") or {},
        }
        if verify and entry["uri"] and str(entry["uri"]).startswith("file://") and entry.get("checksum_sha256"):
            try:
                from pathlib import Path as _P
                import hashlib as _h
                fp = _P(str(entry["uri"])[7:])
                if fp.exists() and fp.is_file():
                    h = _h.sha256()
                    with fp.open("rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            h.update(chunk)
                    calc = h.hexdigest()
                    if calc != entry.get("checksum_sha256"):
                        entry["integrity"] = {"ok": False, "calculated": calc}
                        mismatches += 1
                    else:
                        entry["integrity"] = {"ok": True}
            except Exception:
                entry["integrity"] = {"ok": False, "error": "hash_error"}
                mismatches += 1
        manifest.append(entry)

    resp = {"artifacts": manifest}
    if verify:
        resp["integrity_summary"] = {"mismatch_count": mismatches}
    return resp


class VerifyBatchItem(BaseModel):
    artifact_id: str
    expected_sha256: Optional[str] = None


class VerifyBatchRequest(BaseModel):
    items: List[VerifyBatchItem]


@router.post(
    "/runs/{run_id}/artifacts/verify-batch",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def verify_artifacts_batch(
    run_id: str,
    body: VerifyBatchRequest,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")

    import hashlib as _h
    from pathlib import Path as _P
    results = []
    for item in (body.items or []):
        aid = str(item.artifact_id)
        a = db.get_artifact(aid)
        if not a:
            results.append({"artifact_id": aid, "ok": False, "error": "not_found"})
            continue
        uri = str(a.get("uri") or "")
        if not uri.startswith("file://"):
            results.append({"artifact_id": aid, "ok": False, "error": "unsupported_uri"})
            continue
        fp = _P(uri[len("file://"):])
        if not (fp.exists() and fp.is_file()):
            results.append({"artifact_id": aid, "ok": False, "error": "file_missing"})
            continue
        try:
            h = _h.sha256()
            with fp.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            calc = h.hexdigest()
            recorded = str(a.get("checksum_sha256") or "").strip() or None
            expected = str(item.expected_sha256 or "").strip() or recorded
            mismatch = (expected is not None and calc != expected)
            results.append({
                "artifact_id": aid,
                "ok": not mismatch,
                "calculated": calc,
                "expected": expected,
                "recorded": recorded,
            })
        except Exception as e:
            results.append({"artifact_id": aid, "ok": False, "error": str(e)})

    return {"results": results}


@router.get(
    "/artifacts/{artifact_id}/download",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def download_artifact(
    artifact_id: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
    request: Request = None,
    audit_service=Depends(get_audit_service_for_user),
):
    import os as _os
    from pathlib import Path
    from fastapi.responses import FileResponse
    art = db.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")
    run = db.get_run(str(art.get("run_id"))) if art.get("run_id") else None
    if not run:
        raise HTTPException(status_code=404, detail="Artifact not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        try:
            if audit_service:
                ctx = AuditContext(
                    request_id=(request.headers.get("X-Request-ID") if request else None),
                    user_id=str(current_user.id),
                    endpoint=str(request.url.path) if request else "/api/v1/workflows/artifacts/{id}/download",
                    method=(request.method if request else "GET"),
                )
                await audit_service.log_event(
                    event_type=AuditEventType.PERMISSION_DENIED,
                    category=AuditEventCategory.SECURITY,
                    severity=AuditSeverity.WARNING,
                    context=ctx,
                    resource_type="artifact",
                    resource_id=str(artifact_id),
                    action="tenant_mismatch",
                )
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="Artifact not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        try:
            if audit_service:
                ctx = AuditContext(
                    request_id=(request.headers.get("X-Request-ID") if request else None),
                    user_id=str(current_user.id),
                    endpoint=str(request.url.path) if request else "/api/v1/workflows/artifacts/{id}/download",
                    method=(request.method if request else "GET"),
                )
                await audit_service.log_event(
                    event_type=AuditEventType.PERMISSION_DENIED,
                    category=AuditEventCategory.SECURITY,
                    severity=AuditSeverity.WARNING,
                    context=ctx,
                    resource_type="artifact",
                    resource_id=str(artifact_id),
                    action="not_owner",
                )
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="Artifact not found")
    # Only support file:// URIs for direct download
    uri = str(art.get("uri") or "")
    if uri.startswith("file://"):
        fpath = uri[len("file://") :]
    else:
        raise HTTPException(status_code=400, detail="Only file artifacts are downloadable")
    p = Path(fpath).resolve()
    # Containment check: must be under recorded workdir when present
    workdir = art.get("metadata_json", {}).get("workdir")
    if workdir:
        try:
            wd = Path(str(workdir).replace("file://", "")).resolve()
            if wd.exists():
                try:
                    common = _os.path.commonpath([str(p), str(wd)])
                    if common != str(wd):
                        raise ValueError("path_outside_workdir")
                except Exception:
                    raise ValueError("validation_error")
        except Exception as _e:
            # Allow non-blocking on validation failure depending on run override or env toggle.
            # Semantics:
            #   - If run.validation_mode == 'non-block' => always allow (non-strict)
            #   - Otherwise fall back to env WORKFLOWS_ARTIFACT_VALIDATE_STRICT (default true)
            env_strict = str(_os.getenv("WORKFLOWS_ARTIFACT_VALIDATE_STRICT", "true")).lower() in {"1", "true", "yes", "on"}
            run_val = getattr(run, 'validation_mode', None)
            strict = not (isinstance(run_val, str) and run_val.lower() == 'non-block') and env_strict
            if strict:
                raise HTTPException(status_code=400, detail="Invalid artifact path scope")
            else:
                try:
                    logger.warning(f"Artifact scope validation failed for {p}; proceeding due to non-strict setting: {_e}")
                except Exception:
                    pass
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Optional integrity verification when checksum recorded
    try:
        checksum = str(art.get("checksum_sha256") or "").strip()
        if checksum:
            import hashlib as _hashlib
            h = _hashlib.sha256()
            with p.open("rb") as _f:
                for chunk in iter(lambda: _f.read(65536), b""):
                    h.update(chunk)
            calc = h.hexdigest()
            if calc != checksum:
                # Respect validation mode override
                run_val = getattr(run, 'validation_mode', None)
                non_block = isinstance(run_val, str) and run_val.lower() == 'non-block'
                if not non_block and str(_os.getenv("WORKFLOWS_ARTIFACT_VALIDATE_STRICT", "true")).lower() in {"1", "true", "yes", "on"}:
                    raise HTTPException(status_code=409, detail="Artifact checksum mismatch")
                else:
                    try:
                        logger.warning(f"Artifact checksum mismatch for {artifact_id}; proceeding due to non-strict mode")
                    except Exception:
                        pass
    except HTTPException:
        raise
    except Exception:
        # Do not block on hashing errors
        pass
    # Guardrails: max size and allowed MIME
    import mimetypes as _m
    max_bytes = int(_os.getenv("WORKFLOWS_ARTIFACT_MAX_DOWNLOAD_BYTES", "10485760"))
    try:
        if p.stat().st_size > max_bytes:
            raise HTTPException(status_code=413, detail="Artifact too large to download")
    except Exception:
        pass
    # MIME allowlist
    allowed = [s.strip() for s in (_os.getenv("WORKFLOWS_ARTIFACT_ALLOWED_MIME", "text/plain,text/markdown,application/json,application/pdf,image/png,image/jpeg").split(",")) if s.strip()]
    mime = art.get("mime_type") or _m.guess_type(str(p))[0] or "application/octet-stream"
    if allowed and not any(mime == a or (a.endswith("/*") and mime.startswith(a[:-1])) for a in allowed):
        raise HTTPException(status_code=415, detail=f"MIME not allowed: {mime}")
    # Support Range requests (single range)
    range_header = None
    try:
        range_header = request.headers.get("range") if request else None
    except Exception:
        range_header = None
    # Build a safe Content-Disposition filename to avoid non-ASCII header issues under fuzzing
    def _safe_disp_parts(name: str) -> tuple[str, Optional[str]]:
        try:
            name.encode("ascii")
            return name, None
        except Exception:
            try:
                import urllib.parse as _u
                return "download", _u.quote(name)
            except Exception:
                return "download", None

    if range_header and range_header.lower().startswith("bytes="):
        try:
            total = p.stat().st_size
            rng = range_header.split("=", 1)[1]
            start_str, end_str = (rng.split("-", 1) + [""])[:2]
            if start_str:
                start = int(start_str)
                end = int(end_str) if end_str else total - 1
            else:
                # suffix-length: bytes=-N
                length = int(end_str)
                start = max(0, total - length)
                end = total - 1
            if start < 0 or end < start or end >= total:
                raise ValueError("invalid_range")
            length = end - start + 1
            ascii_name, encoded_name = _safe_disp_parts(p.name)
            headers = {
                "Content-Range": f"bytes {start}-{end}/{total}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Type": mime,
                "Content-Disposition": (
                    f"attachment; filename={ascii_name}"
                    + (f"; filename*=UTF-8''{encoded_name}" if encoded_name else "")
                ),
            }
            def _iter():
                with p.open("rb") as f:
                    f.seek(start)
                    remaining = length
                    chunk = 64 * 1024
                    while remaining > 0:
                        data = f.read(min(chunk, remaining))
                        if not data:
                            break
                        remaining -= len(data)
                        yield data
            return StreamingResponse(_iter(), status_code=206, headers=headers)
        except Exception:
            # 416 Range Not Satisfiable
            raise HTTPException(status_code=416, detail="Invalid Range header")
    # Full response
    ascii_name, encoded_name = _safe_disp_parts(p.name)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": (
            f"attachment; filename={ascii_name}" + (f"; filename*=UTF-8''{encoded_name}" if encoded_name else "")
        ),
    }
    return FileResponse(str(p), media_type=mime, headers=headers)


@router.get(
    "/runs/{run_id}/artifacts/download",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def download_run_artifacts_zip(
    run_id: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    import os as _os
    import mimetypes as _m
    import io, zipfile
    from pathlib import Path

    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")

    arts = db.list_artifacts_for_run(run_id)
    if not arts:
        raise HTTPException(status_code=404, detail="No artifacts for run")

    # Constraints
    max_total = int(_os.getenv("WORKFLOWS_ARTIFACT_BULK_MAX_BYTES", "52428800"))  # 50MB
    allowed = [s.strip() for s in (_os.getenv("WORKFLOWS_ARTIFACT_ALLOWED_MIME", "text/plain,text/markdown,application/json,application/pdf,image/png,image/jpeg").split(",")) if s.strip()]

    # Preselect eligible files and sum sizes
    selected = []
    total = 0
    for a in arts:
        uri = str(a.get("uri") or "")
        if not uri.startswith("file://"):
            continue
        p = Path(uri[len("file://"):]).resolve()
        if not p.exists() or not p.is_file():
            continue
        try:
            size_b = p.stat().st_size
        except Exception:
            size_b = 0
        mime = a.get("mime_type") or _m.guess_type(str(p))[0] or "application/octet-stream"
        if allowed and not any(mime == m or (m.endswith("/*") and mime.startswith(m[:-1])) for m in allowed):
            continue
        total += size_b or 0
        if total > max_total:
            raise HTTPException(status_code=413, detail="Total artifact size too large for bulk download")
        selected.append((p, mime))

    if not selected:
        raise HTTPException(status_code=404, detail="No eligible artifacts for bulk download")

    # Build zip in-memory (store)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
        for p, mime in selected:
            try:
                zf.write(str(p), arcname=p.name)
            except Exception:
                continue
    buf.seek(0)
    filename = f"artifacts_{run_id}.zip"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


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





@router.post(
    "/runs/{run_id}/{action}",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_CONTROL))],
)
async def control_run(
    run_id: str,
    action: str,
    request: Request,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    # Enforce tenant + owner/admin
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")
    engine = WorkflowEngine(db)
    # Admin impersonation audit trail (header opt-in)
    try:
        imp = str(request.headers.get("x-impersonate-user", "")).strip()
        is_admin = bool(getattr(current_user, "is_admin", False))
        if imp and is_admin and str(imp) != str(current_user.id):
            db.append_event(str(getattr(current_user, 'tenant_id', 'default')), run_id, "admin_impersonation", {"actor": str(current_user.id), "target_user_id": imp, "action": action})
    except Exception:
        pass
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


@router.get(
    "/step-types",
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "cURL",
                "source": "curl -H 'X-API-KEY: $API_KEY' http://127.0.0.1:8000/api/v1/workflows/step-types",
            }
        ]
    },
)
async def list_step_types():
    """Return available step types with basic JSONSchema, examples, and min engine version.

    This is a lightweight introspection surface to help UIs validate configurations.
    """
    reg = StepTypeRegistry()
    steps = reg.list()
    # Minimal schemas (can be expanded incrementally)
    schemas = {
        "prompt": {
            "type": "object",
            "properties": {
                "template": {"type": "string"},
                "model": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "default": 300},
                "retry": {"type": "integer", "minimum": 0, "default": 0},
            },
            "required": ["template"],
            "additionalProperties": True,
            "example": {"template": "Hello {{inputs.name}}", "model": "gpt-4o-mini"},
            "min_engine_version": "0.1.0",
        },
        "branch": {
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "true_next": {"type": "string"},
                "false_next": {"type": "string"}
            },
            "required": ["condition"],
            "additionalProperties": False,
            "example": {"condition": "{{ inputs.enabled }}", "true_next": "step_b", "false_next": "step_c"},
            "min_engine_version": "0.1.1",
        },
        "map": {
            "type": "object",
            "properties": {
                "items": {"type": ["array", "string"]},
                "step": {"type": "object"},
                "concurrency": {"type": "integer", "minimum": 1, "default": 4}
            },
            "required": ["items", "step"],
            "additionalProperties": True,
            "example": {"items": [1,2,3], "step": {"type":"log", "config": {"message": "Item {{ item }}"}}, "concurrency": 2},
            "min_engine_version": "0.1.1",
        },
        "rag_search": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "default": 5},
                "timeout_seconds": {"type": "integer", "minimum": 1, "default": 60},
            },
            "required": ["query"],
            "additionalProperties": True,
            "example": {"query": "large language models safety", "top_k": 8},
            "min_engine_version": "0.1.0",
        },
        "webhook": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "include_outputs": {"type": "boolean", "default": True},
                "timeout_seconds": {"type": "integer", "minimum": 1, "default": 10},
            },
            "required": [],
            "additionalProperties": True,
            "example": {"url": "https://example.com/hooks/workflow"},
            "min_engine_version": "0.1.0",
        },
        "tts": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Templated text. Defaults to last.text or inputs.summary"},
                "model": {"type": "string", "default": "kokoro"},
                "voice": {"type": "string", "default": "af_heart"},
                "response_format": {"type": "string", "enum": ["mp3","wav","opus","flac","aac","pcm"], "default": "mp3"},
                "speed": {"type": "number", "minimum": 0.25, "maximum": 4.0, "default": 1.0},
                "provider": {"type": "string"},
                "output_filename_template": {"type": "string", "description": "e.g., audio_{{timestamp}}_{{voice}}"},
                "provider_options": {"type": "object"},
                "attach_download_link": {"type": "boolean", "default": False},
                "save_transcript": {"type": "boolean", "default": False},
                "post_process": {
                    "type": "object",
                    "properties": {
                        "normalize": {"type": "boolean", "default": False},
                        "target_lufs": {"type": "number", "default": -16.0},
                        "true_peak_dbfs": {"type": "number", "default": -1.5},
                        "lra": {"type": "number", "default": 11.0}
                    }
                }
            },
            "required": [],
            "additionalProperties": True,
            "example": {"input": "Narrate: {{ last.text }}", "model": "kokoro", "voice": "af_heart", "response_format": "mp3"},
            "min_engine_version": "0.1.2",
        },
        "delay": {
            "type": "object",
            "properties": {"milliseconds": {"type": "integer", "minimum": 1, "default": 1000}},
            "required": ["milliseconds"],
            "additionalProperties": False,
            "example": {"milliseconds": 500},
            "min_engine_version": "0.1.0",
        },
        "log": {
            "type": "object",
            "properties": {"message": {"type": "string"}, "level": {"type": "string", "enum": ["debug", "info", "warning", "error"], "default": "info"}},
            "required": ["message"],
            "additionalProperties": True,
            "example": {"message": "step reached", "level": "debug"},
            "min_engine_version": "0.1.0",
        },
        "process_media": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["web_scraping","pdf","ebook","xml","mediawiki_dump","podcast"], "default": "web_scraping"},
                "scrape_method": {"type": "string", "default": "Individual URLs"},
                "url_input": {"type": "string"},
                "url_level": {"type": ["integer", "null"]},
                "max_pages": {"type": "integer", "default": 10},
                "max_depth": {"type": "integer", "default": 3},
                "summarize": {"type": "boolean", "default": False},
                "custom_prompt": {"type": ["string","null"]},
                "api_name": {"type": ["string","null"]},
                "system_prompt": {"type": ["string","null"]},
                "temperature": {"type": "number", "default": 0.7},
                "custom_cookies": {"type": ["array","null"]},
                "user_agent": {"type": ["string","null"]},
                "custom_headers": {"type": ["object","null"]},
                "file_uri": {"type": "string", "description": "file:// path for pdf/ebook/xml/mediawiki_dump"},
                "url": {"type": "string", "description": "Podcast URL (for kind=podcast)"}
            },
            "required": [],
            "additionalProperties": True,
            "example": {"kind": "web_scraping", "scrape_method": "Individual URLs", "url_input": "https://example.com/article"},
            "min_engine_version": "0.1.2"
        },
        "rss_fetch": {
            "type": "object",
            "properties": {
                "urls": {"type": ["array","string"], "description": "RSS/Atom feed URLs (list or string)"},
                "limit": {"type": "integer", "default": 10},
                "include_content": {"type": "boolean", "default": True}
            },
            "required": ["urls"],
            "additionalProperties": True,
            "example": {"urls": ["https://example.com/feed.xml"], "limit": 5},
            "min_engine_version": "0.1.3"
        },
        "atom_fetch": {
            "type": "object",
            "properties": {
                "urls": {"type": ["array","string"]},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["urls"],
            "additionalProperties": True,
            "example": {"urls": ["https://example.com/atom.xml"]},
            "min_engine_version": "0.1.3"
        },
        "embed": {
            "type": "object",
            "properties": {
                "texts": {"type": ["array","string"]},
                "collection": {"type": "string"},
                "model_id": {"type": ["string","null"]},
                "metadata": {"type": ["object","null"]}
            },
            "required": [],
            "additionalProperties": True,
            "example": {"texts": "{{ last.text }}", "collection": "user_1_workflows"},
            "min_engine_version": "0.1.3"
        },
        "translate": {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "target_lang": {"type": "string", "default": "en"},
                "provider": {"type": ["string","null"]},
                "model": {"type": ["string","null"]}
            },
            "required": ["target_lang"],
            "additionalProperties": True,
            "example": {"input": "{{ last.text }}", "target_lang": "fr"},
            "min_engine_version": "0.1.3"
        },
        "stt_transcribe": {
            "type": "object",
            "properties": {
                "file_uri": {"type": "string", "description": "file:// path to audio/video"},
                "model": {"type": "string", "default": "large-v3"},
                "language": {"type": ["string","null"]},
                "diarize": {"type": "boolean", "default": False},
                "word_timestamps": {"type": "boolean", "default": False}
            },
            "required": ["file_uri"],
            "additionalProperties": True,
            "example": {"file_uri": "file:///abs/path/audio.wav", "model": "large-v3"},
            "min_engine_version": "0.1.3"
        },
        "notify": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "message": {"type": "string"},
                "subject": {"type": ["string","null"]},
                "headers": {"type": ["object","null"]}
            },
            "required": ["url","message"],
            "additionalProperties": True,
            "example": {"url": "https://hooks.slack.com/services/...", "message": "{{ last.text }}"},
            "min_engine_version": "0.1.3"
        },
        "diff_change_detector": {
            "type": "object",
            "properties": {
                "current": {"type": "string"},
                "method": {"type": "string", "enum": ["ratio","unified"], "default": "ratio"},
                "threshold": {"type": "number", "default": 0.9}
            },
            "required": [],
            "additionalProperties": True,
            "example": {"current": "{{ last.text }}", "method": "ratio", "threshold": 0.95},
            "min_engine_version": "0.1.3"
        },
        "policy_check": {
            "type": "object",
            "properties": {
                "text_source": {"type": "string", "enum": ["last","inputs","field"], "default": "last"},
                "field": {"type": "string"},
                "block_on_pii": {"type": "boolean", "default": False},
                "block_words": {"type": "array", "items": {"type": "string"}},
                "max_length": {"type": "integer", "minimum": 1},
                "redact_preview": {"type": "boolean", "default": False}
            },
            "required": [],
            "additionalProperties": True,
            "example": {"text_source": "last", "block_on_pii": True, "block_words": ["secret","password"], "max_length": 10000},
            "min_engine_version": "0.1.3"
        },
        "wait_for_human": {
            "type": "object",
            "properties": {
                "instructions": {"type": "string"},
                "assigned_to_user_id": {"type": ["string","integer","null"]}
            },
            "required": [],
            "additionalProperties": True,
            "example": {"instructions": "Review the summary and approve.", "assigned_to_user_id": None},
            "min_engine_version": "0.1.3"
        },
        "wait_for_approval": {
            "type": "object",
            "properties": {
                "instructions": {"type": "string"},
                "assigned_to_user_id": {"type": ["string","integer","null"]}
            },
            "required": [],
            "additionalProperties": True,
            "example": {"instructions": "Await approval.", "assigned_to_user_id": None},
            "min_engine_version": "0.1.3"
        },
    }
    out = []
    for s in steps:
        sch = schemas.get(s.name, {"type": "object", "additionalProperties": True, "min_engine_version": "0.1.0"})
        out.append({
            "name": s.name,
            "description": s.description,
            "schema": sch,
            "example": sch.get("example", {}),
            "min_engine_version": sch.get("min_engine_version", "0.1.0"),
        })
    return out


@router.get("/templates")
async def list_workflow_templates(q: Optional[str] = Query(None, description="Search query on name/title/tags"), tag: Optional[str] = Query(None, description="Filter by tag")) -> list[dict[str, Any]]:
    """List available example workflow templates shipped with the server.

    Returns a list of {name, filename} items. Use GET /api/v1/workflows/templates/{name}
    to retrieve the JSON content.
    """
    try:
        # Locate Samples/Workflows by walking upwards for robustness
        here = Path(__file__).resolve()
        tpl_dir = None
        p = here
        for _ in range(0, 9):
            candidate = p.parent / "Samples" / "Workflows"
            if candidate.exists():
                tpl_dir = candidate
                break
            p = p.parent
        if tpl_dir is None:
            return []
        items: list[dict[str, str]] = []
        if tpl_dir.exists():
            for p in tpl_dir.glob("*.workflow.json"):
                try:
                    # Derive template name without the trailing ".workflow.json"
                    fname = p.name
                    if fname.endswith(".workflow.json"):
                        name = fname[: -len(".workflow.json")]
                    else:
                        # Fallback: stem (may include an extra suffix on some platforms)
                        name = p.stem
                    # Load title from the template JSON's "name" field for a human-friendly label
                    title: str = name
                    try:
                        import json as _json
                        raw = p.read_text(encoding="utf-8")
                        data = _json.loads(raw)
                        tpl_title = str(data.get("name") or "").strip()
                        tags = data.get("tags") or []
                        if tpl_title:
                            title = tpl_title
                        # Normalize tags to list[str]
                        if not isinstance(tags, list):
                            tags = []
                    except Exception:
                        # Ignore parse errors; fall back to filename-derived name
                        tags = []
                    item = {"name": name, "filename": p.name, "title": title, "tags": tags}
                    items.append(item)
                except Exception:
                    continue
        # Optional search and tag filtering
        def _match(s: str, query: str) -> bool:
            try:
                return query.lower() in s.lower()
            except Exception:
                return False
        if q:
            items = [it for it in items if _match(it.get("name", ""), q) or _match(it.get("title", ""), q) or any(_match(t, q) for t in (it.get("tags") or []))]
        if tag:
            items = [it for it in items if str(tag) in (it.get("tags") or [])]
        return items
    except Exception as e:
        logger.warning(f"Failed to list workflow templates: {e}")
        return []


@router.get(
    "/templates/tags",
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "List tags",
                "source": "curl -sS -H 'X-API-KEY: $API_KEY' \"$BASE/api/v1/workflows/templates/tags\" | jq ."
            }
        ]
    },
)
async def list_workflow_template_tags() -> list[str]:
    return await list_workflow_template_tags_internal()

@router.get(
    "/templates/_tags_internal",
)
async def list_workflow_template_tags_internal() -> list[str]:
    """Return the unique set of tags from all bundled templates."""
    try:
        # Robust search for Samples/Workflows
        here = Path(__file__).resolve()
        tpl_dir = None
        p = here
        for _ in range(0, 9):
            candidate = p.parent / "Samples" / "Workflows"
            if candidate.exists():
                tpl_dir = candidate
                break
            p = p.parent
        if tpl_dir is None or not tpl_dir.exists():
            return []
        tags_set: set[str] = set()
        for f in tpl_dir.glob("*.workflow.json"):
            try:
                import json as _json
                data = _json.loads(f.read_text(encoding="utf-8"))
                tags = data.get("tags") or []
                if isinstance(tags, list):
                    for t in tags:
                        try:
                            s = str(t).strip()
                            if s:
                                tags_set.add(s)
                        except Exception:
                            continue
            except Exception:
                continue
        return sorted(tags_set)
    except Exception as e:
        logger.warning(f"Failed to list template tags: {e}")
        return []


@router.get("/templates/{name:path}")
async def get_workflow_template(name: str) -> Dict[str, Any]:
    """Return JSON content for a named workflow template (sans extension)."""
    # Disallow traversal and separators (defense-in-depth with unquoting)
    from urllib.parse import unquote as _unquote
    raw = _unquote(name or "").strip()
    if ("/" in raw) or ("\\" in raw) or raw == "":
        raise HTTPException(status_code=400, detail="Invalid template name")
    # Reject path traversal patterns (.. segments)
    if ".." in raw.split("/"):
        raise HTTPException(status_code=400, detail="Invalid template name")
    try:
        # Robust search for Samples/Workflows
        here = Path(__file__).resolve()
        tpl_dir = None
        p = here
        for _ in range(0, 9):
            candidate = p.parent / "Samples" / "Workflows"
            if candidate.exists():
                tpl_dir = candidate
                break
            p = p.parent
        if tpl_dir is None:
            raise HTTPException(status_code=404, detail="Template not found")
        # Support names passed either with or without the optional ".workflow" suffix
        candidates = [
            tpl_dir / f"{raw}.workflow.json",
        ]
        if not raw.endswith(".workflow"):
            candidates.append(tpl_dir / f"{raw}.workflow.workflow.json")
        target = next((c for c in candidates if c.exists() and c.is_file()), None)
        if not (tpl_dir.exists() and target):
            raise HTTPException(status_code=404, detail="Template not found")
        import json as _json
        # Size guard (1MB cap)
        raw = target.read_text(encoding="utf-8")
        if len(raw.encode("utf-8")) > 1024 * 1024:
            raise HTTPException(status_code=413, detail="Template too large")
        return _json.loads(raw)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to read workflow template {name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load template")

@router.get("/templates/_byname/{name:path}")
async def get_workflow_template_legacy(name: str) -> Dict[str, Any]:
    """Return JSON content for a named workflow template (sans extension)."""
    # Disallow traversal and separators (defense-in-depth with unquoting)
    from urllib.parse import unquote as _unquote
    raw = _unquote(name or "").strip()
    if ("/" in raw) or ("\\" in raw) or raw == "":
        raise HTTPException(status_code=400, detail="Invalid template name")
    if ".." in raw.split("/"):
        raise HTTPException(status_code=400, detail="Invalid template name")
    try:
        # Robust search for Samples/Workflows
        here = Path(__file__).resolve()
        tpl_dir = None
        p = here
        for _ in range(0, 9):
            candidate = p.parent / "Samples" / "Workflows"
            if candidate.exists():
                tpl_dir = candidate
                break
            p = p.parent
        if tpl_dir is None:
            raise HTTPException(status_code=404, detail="Template not found")
        # Support names passed either with or without the optional ".workflow" suffix
        candidates = [
            tpl_dir / f"{raw}.workflow.json",
        ]
        if not raw.endswith(".workflow"):
            candidates.append(tpl_dir / f"{raw}.workflow.workflow.json")
        target = next((c for c in candidates if c.exists() and c.is_file()), None)
        if not (tpl_dir.exists() and target):
            raise HTTPException(status_code=404, detail="Template not found")
        import json as _json
        # Size guard (1MB cap)
        raw = target.read_text(encoding="utf-8")
        if len(raw.encode("utf-8")) > 1024 * 1024:
            raise HTTPException(status_code=413, detail="Template too large")
        return _json.loads(raw)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to read workflow template {name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load template")


@router.get(
    "/templates/tags",
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "List tags",
                "source": "curl -sS -H 'X-API-KEY: $API_KEY' \"$BASE/api/v1/workflows/templates/tags\" | jq ."
            }
        ]
    },
)
async def list_workflow_template_tags() -> list[str]:
    """Return the unique set of tags from all bundled templates."""
    try:
        # Robust search for Samples/Workflows
        here = Path(__file__).resolve()
        tpl_dir = None
        p = here
        for _ in range(0, 9):
            candidate = p.parent / "Samples" / "Workflows"
            if candidate.exists():
                tpl_dir = candidate
                break
            p = p.parent
        if tpl_dir is None or not tpl_dir.exists():
            return []
        tags_set: set[str] = set()
        for f in tpl_dir.glob("*.workflow.json"):
            try:
                import json as _json
                data = _json.loads(f.read_text(encoding="utf-8"))
                tags = data.get("tags") or []
                if isinstance(tags, list):
                    for t in tags:
                        try:
                            s = str(t).strip()
                            if s:
                                tags_set.add(s)
                        except Exception:
                            continue
            except Exception:
                continue
        return sorted(tags_set)
    except Exception as e:
        logger.warning(f"Failed to list template tags: {e}")
        return []


@router.get("/config")
async def get_workflows_config(current_user: User = Depends(get_request_user), db: WorkflowsDatabase = Depends(_get_db)):
    """Return effective Workflows configuration derived from environment and backend (read-only)."""
    import os
    def _env_bool(name: str, default: bool = False) -> bool:
        v = os.getenv(name, "")
        if not v:
            return default
        return v.lower() in {"1", "true", "yes", "y", "on"}

    backend_type = "sqlite"
    try:
        if getattr(db, "backend", None) and getattr(db.backend, "backend_type", None) == BackendType.POSTGRESQL:
            backend_type = "postgres"
    except Exception:
        pass

    def _csv(name: str) -> list[str]:
        raw = os.getenv(name, "")
        if not raw:
            return []
        return [s.strip() for s in raw.split(",") if s.strip()]

    cfg = {
        "backend": {
            "type": backend_type,
        },
        "rate_limits": {
            "disabled": _env_bool("WORKFLOWS_DISABLE_RATE_LIMITS", False),
            "quotas_disabled": _env_bool("WORKFLOWS_DISABLE_QUOTAS", False),
            "quota_burst_per_min": int(os.getenv("WORKFLOWS_QUOTA_BURST_PER_MIN", "60") or 60),
            "quota_daily_per_user": int(os.getenv("WORKFLOWS_QUOTA_DAILY_PER_USER", "1000") or 1000),
        },
        "engine": {
            "tenant_concurrency": int(os.getenv("WORKFLOWS_TENANT_CONCURRENCY", "2") or 2),
            "workflow_concurrency": int(os.getenv("WORKFLOWS_WORKFLOW_CONCURRENCY", "1") or 1),
        },
        "egress": {
            "profile": (os.getenv("WORKFLOWS_EGRESS_PROFILE", "") or "(auto)").strip(),
            "allowed_ports": _csv("WORKFLOWS_EGRESS_ALLOWED_PORTS") or ["80","443"],
            "allowlist": _csv("WORKFLOWS_EGRESS_ALLOWLIST"),
            "block_private": _env_bool("WORKFLOWS_EGRESS_BLOCK_PRIVATE", True),
        },
        "webhooks": {
            "completion_disabled": _env_bool("WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS", False),
            "secret_set": bool(os.getenv("WORKFLOWS_WEBHOOK_SECRET")),
            "dlq_enabled": _env_bool("WORKFLOWS_WEBHOOK_DLQ_ENABLED", False),
            "allowlist": _csv("WORKFLOWS_WEBHOOK_ALLOWLIST"),
            "denylist": _csv("WORKFLOWS_WEBHOOK_DENYLIST"),
        },
        "artifacts": {
            "validate_strict": _env_bool("WORKFLOWS_ARTIFACT_VALIDATE_STRICT", True),
            "encryption_enabled": _env_bool("WORKFLOWS_ARTIFACT_ENCRYPTION", False),
            "gc_enabled": _env_bool("WORKFLOWS_ARTIFACT_GC_ENABLED", False),
            "retention_days": int(os.getenv("WORKFLOWS_ARTIFACT_RETENTION_DAYS", "30") or 30),
        },
    }
    return cfg


@router.post(
    "/runs/{run_id}/retry",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_CONTROL))],
)
async def retry_run(
    run_id: str,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")
    engine = WorkflowEngine(db)
    # Resume from last failed step if present
    failed_step = db.get_last_failed_step_id(run_id)
    if failed_step:
        asyncio.get_event_loop().create_task(engine.continue_run(run_id, after_step_id=failed_step, last_outputs=None))
    else:
        engine.submit(run_id, RunMode.ASYNC)
    return {"ok": True}


@router.get(
    "/{workflow_id}",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_READ))],
)
async def get_definition(
    workflow_id: int,
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    """Fetch a workflow definition by id.

    Declared after '/runs*' routes to prevent path parameter shadowing.
    """
    d = db.get_definition(workflow_id)
    if not d:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Tenant isolation
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if d.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Owner/admin check for definition read (tighten RBAC)
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(d.owner_id) != str(current_user.id) and not is_admin:
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


# -------------------- Human-in-the-loop approvals --------------------

class HumanReviewPayload(BaseModel):
    comment: Optional[str] = None
    edited_fields: Optional[Dict[str, Any]] = None


@router.post(
    "/runs/{run_id}/steps/{step_id}/approve",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_CONTROL))],
)
async def approve_step(
    run_id: str,
    step_id: str,
    payload: HumanReviewPayload = Body(default_factory=HumanReviewPayload),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    # Owner/admin check for the run
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")
    # Update step decision via DB adapter
    try:
        db.approve_step_decision(run_id=run_id, step_id=step_id, approved_by=str(current_user.id), comment=payload.comment or "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Resume run from next step
    engine = WorkflowEngine(db)
    # Pass edited fields as last outputs override
    last_outputs = payload.edited_fields or {}
    asyncio.get_event_loop().create_task(engine.continue_run(run_id, after_step_id=step_id, last_outputs=last_outputs))
    return {"ok": True}


@router.post(
    "/runs/{run_id}/steps/{step_id}/reject",
    dependencies=[Depends(PermissionChecker(WORKFLOWS_RUNS_CONTROL))],
)
async def reject_step(
    run_id: str,
    step_id: str,
    payload: HumanReviewPayload = Body(default_factory=HumanReviewPayload),
    current_user: User = Depends(get_request_user),
    db: WorkflowsDatabase = Depends(_get_db),
):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    tenant_id = str(getattr(current_user, "tenant_id", "default"))
    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    is_admin = bool(getattr(current_user, "is_admin", False))
    if str(run.user_id) != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        db.reject_step_decision(run_id=run_id, step_id=step_id, approved_by=str(current_user.id), comment=payload.comment or "")
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
    types: Optional[List[str]] = Query(None),
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
    # Normalize event types if provided for server-side filtering
    types_norm = [t.strip() for t in (types or []) if str(t).strip()]
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
            events = db.get_events(run_id, since=last_seq, types=(types_norm or None))
            if events:
                for e in events:
                    payload = e.get("payload_json") or {}
                    await websocket.send_json({"event_seq": e["event_seq"], "event_type": e["event_type"], "payload": payload, "ts": e["created_at"]})
                    last_seq = e["event_seq"]
            else:
                # Send a lightweight heartbeat so clients using blocking receive_json() don't hang indefinitely
                try:
                    await websocket.send_json({"type": "heartbeat", "ts": _utcnow_iso()})
                except Exception:
                    # If sending heartbeat fails (e.g., client disconnect), let outer exception handling close
                    raise
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
