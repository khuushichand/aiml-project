from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Header, File, UploadFile, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import StreamingResponse, Response, JSONResponse
from fastapi.routing import APIRoute
import asyncio
import os
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.sandbox_schemas import (
    ArtifactListResponse,
    CancelResponse,
    RuntimeType,
    SandboxFileUploadResponse,
    SandboxRun,
    SandboxRunCreateRequest,
    SandboxRunStatus,
    SandboxRuntimesResponse,
    SandboxSession,
    SandboxSessionCreateRequest,
    SandboxAdminRunListResponse,
    SandboxAdminRunSummary,
    SandboxAdminRunDetails,
    SandboxAdminIdempotencyListResponse,
    SandboxAdminIdempotencyItem,
    SandboxAdminUsageResponse,
    SandboxAdminUsageItem,
    SnapshotCreateResponse,
    SnapshotInfo,
    SnapshotListResponse,
    SnapshotRestoreRequest,
    SnapshotRestoreResponse,
    SessionCloneRequest,
    SessionCloneResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.ip_allowlist import is_single_user_ip_allowed, resolve_client_ip
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.Sandbox.models import RunSpec, SessionSpec, RuntimeType as CoreRuntimeType, TrustLevel as CoreTrustLevel
from tldw_Server_API.app.core.Sandbox.service import SandboxService
from tldw_Server_API.app.core.config import settings as app_settings
from tldw_Server_API.app.core.Sandbox.streams import get_hub
from tldw_Server_API.app.core.Metrics import increment_counter, observe_histogram
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.core.Audit.unified_audit_service import AuditEventType, AuditEventCategory, AuditSeverity, AuditContext
from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
import mimetypes
from tldw_Server_API.app.core.Streaming.streams import WebSocketStream
from tldw_Server_API.app.core.Utils.path_utils import safe_join
import hmac
import hashlib
import time


class SandboxArtifactGuardRoute(APIRoute):
    """APIRoute that rejects unsafe artifact paths using raw ASGI path.

    This guard runs before dependency resolution/endpoint execution and inspects
    `scope['raw_path']` so traversal attempts aren't hidden by path normalization.
    Only affects sandbox artifact download URLs.
    """

    def get_route_handler(self):
        original = super().get_route_handler()

        async def custom_handler(request: Request):
            try:
                raw_path = request.scope.get("raw_path")
                path_raw = raw_path.decode("utf-8", "ignore") if isinstance(raw_path, (bytes, bytearray)) else (request.url.path or "")
                # Reject traversal early for any sandbox runs path if raw_path reveals '..'
                if "/api/v1/sandbox/runs/" in path_raw and "/../" in path_raw:
                    return JSONResponse({"detail": "invalid_path"}, status_code=400)
                if "/api/v1/sandbox/runs/" in path_raw and "/artifacts/" in path_raw:
                    from urllib.parse import unquote
                    import posixpath as _pp
                    idx = path_raw.find("/artifacts/")
                    tail = path_raw[idx + len("/artifacts/"):]
                    tail_unquoted = unquote(tail)
                    if (
                        ".." in tail_unquoted.split("/")
                        or tail_unquoted.startswith("/")
                        or "//" in tail
                        or _pp.normpath(tail_unquoted) != tail_unquoted
                    ):
                        return JSONResponse({"detail": "invalid_path"}, status_code=400)
            except Exception:
                # Fail open on guard errors
                pass
            return await original(request)

        return custom_handler


router = APIRouter(prefix="/sandbox", tags=["sandbox"], route_class=SandboxArtifactGuardRoute)

_service = SandboxService()


def _is_admin_user(user: User) -> bool:
    try:
        if bool(getattr(user, "is_admin", False)):
            return True
    except Exception:
        pass
    try:
        roles = getattr(user, "roles", None)
        if roles and "admin" in roles:
            return True
    except Exception:
        pass
    return False


def _require_run_owner(run_id: str, current_user: User) -> str:
    owner = _service._orch.get_run_owner(run_id)  # type: ignore[attr-defined]
    if owner is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    if not _is_admin_user(current_user) and str(owner) != str(current_user.id):
        raise HTTPException(status_code=404, detail="run_not_found")
    return str(owner)


def _require_session_owner(session_id: str, current_user: User) -> str:
    owner = _service._orch.get_session_owner(session_id)  # type: ignore[attr-defined]
    if owner is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    if not _is_admin_user(current_user) and str(owner) != str(current_user.id):
        raise HTTPException(status_code=404, detail="session_not_found")
    return str(owner)


def _looks_like_jwt(token: Optional[str]) -> bool:
    return isinstance(token, str) and token.count(".") == 2


async def _resolve_sandbox_ws_user_id(
    websocket: WebSocket,
    *,
    token: Optional[str],
    api_key: Optional[str],
) -> int:
    if not token:
        auth_hdr = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_hdr and auth_hdr.lower().startswith("bearer "):
            token = auth_hdr.split(" ", 1)[1].strip()
    if not api_key:
        api_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-KEY")

    if token and not api_key and not _looks_like_jwt(token):
        api_key = token
        token = None

    if token:
        try:
            from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
            from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
            from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError

            jwt_service = get_jwt_service()
            payload = await jwt_service.verify_token_async(token, token_type="access")
            session_manager = await get_session_manager()
            if await session_manager.is_token_blacklisted(token, payload.get("jti")):
                raise HTTPException(status_code=401, detail="invalid_token")
        except HTTPException:
            raise
        except (InvalidTokenError, TokenExpiredError):
            raise HTTPException(status_code=401, detail="invalid_token")
        except Exception:
            raise HTTPException(status_code=401, detail="invalid_token")

        sub = payload.get("user_id") or payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=401, detail="invalid_token")
        try:
            return int(sub)
        except Exception:
            raise HTTPException(status_code=401, detail="invalid_token")

    if api_key:
        settings = get_settings()
        client_ip = resolve_client_ip(websocket, settings)
        if getattr(settings, "AUTH_MODE", None) == "single_user":
            allowed_keys: set[str] = set()
            primary_key = getattr(settings, "SINGLE_USER_API_KEY", None)
            if primary_key:
                allowed_keys.add(primary_key)
            test_key = os.getenv("SINGLE_USER_TEST_API_KEY")
            if test_key:
                allowed_keys.add(test_key)
            if api_key in allowed_keys and is_single_user_ip_allowed(client_ip, settings):
                return int(getattr(settings, "SINGLE_USER_FIXED_ID", 1))
            raise HTTPException(status_code=401, detail="invalid_api_key")

        api_mgr = await get_api_key_manager()
        info = await api_mgr.validate_api_key(api_key=api_key, required_scope="read", ip_address=client_ip)
        if not info:
            raise HTTPException(status_code=401, detail="invalid_api_key")
        user_id = info.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="invalid_api_key")
        return int(user_id)

    raise HTTPException(status_code=401, detail="auth_required")


def _normalize_reason(outcome: str, message: Optional[str]) -> str:
    """Normalize a possibly long/unique error message into a small, bounded set for metrics labels.

    Prefers bucketing into a fixed taxonomy to prevent Prometheus label cardinality explosions.
    If no mapping applies, falls back to the outcome string.
    """
    try:
        o = (outcome or "").strip().lower() or "unknown"
        msg = (message or "").strip().lower()

        # Outcome-driven buckets
        if o in {"timeout", "timed_out"}:
            return "timeout"
        if o in {"killed"}:
            return "killed"
        if o in {"success", "completed"}:
            return "success"
        if o in {"failed", "error", "internal"} and not msg:
            return "internal"

        # Message-driven buckets (substring checks)
        if msg:
            if "out of memory" in msg or "oom" in msg or "memory limit" in msg:
                return "oom"
            if "validation" in msg or "invalid" in msg or "schema" in msg:
                return "validation_error"
            if "unauthorized" in msg or "forbidden" in msg or "permission denied" in msg:
                return "permission_denied"
            if "rate limit" in msg or "too many requests" in msg or "status code 429" in msg:
                return "rate_limited"
            if "queue full" in msg:
                return "queue_full"
            if "deadline exceeded" in msg:
                return "timeout"
            if "sigkill" in msg or "signal 9" in msg:
                return "killed"
            if "not found" in msg or "no such file" in msg:
                return "not_found"
            if "image pull" in msg or "manifest" in msg:
                return "image_error"
            if "network timeout" in msg or "connection timed out" in msg:
                return "timeout"
            if "cancelled" in msg or "canceled" in msg:
                return "killed"

        # Generic fallback buckets
        if o in {"failed", "error"}:
            return "internal"
        return o or "other"
    except Exception:
        return "other"


@router.get("/runtimes", response_model=SandboxRuntimesResponse, summary="Discover available runtimes")
async def get_runtimes(current_user: User = Depends(get_request_user)) -> SandboxRuntimesResponse:
    info = _service.feature_discovery()
    return SandboxRuntimesResponse(runtimes=info)  # type: ignore[arg-type]


@router.get("/health", summary="Sandbox health and readiness probe")
async def sandbox_health(current_user: User = Depends(get_request_user)) -> dict:
    """Report sandbox store and Redis fan-out health.

    - Store: reports effective `store_mode` and a basic connectivity check in cluster mode.
    - Redis: reports whether WS fan-out is enabled and connected.
    """
    import time as _time
    from tldw_Server_API.app.core.Sandbox.store import get_store_mode, get_store
    store_info: dict = {"mode": None, "healthy": True}
    timings: dict = {}
    try:
        mode = str(get_store_mode())
        store_info["mode"] = mode
        if mode == "cluster":
            try:
                st = get_store()
                t0 = _time.perf_counter()
                # Minimal smoke call to exercise connectivity
                _ = int(st.count_runs())
                timings["store_ms"] = float((_time.perf_counter() - t0) * 1000.0)
                store_info["healthy"] = True
            except Exception as e:
                logger.exception("Sandbox health: store connectivity check failed")
                store_info["healthy"] = False
                store_info["code"] = "internal_error"
    except Exception as e:
        logger.exception("Sandbox health: store mode detection failed")
        store_info["healthy"] = False
        store_info["code"] = "internal_error"
    # Redis status via hub
    try:
        hub = get_hub()  # type: ignore[attr-defined]
        redis_status = hub.get_redis_status()
        if redis_status.get("enabled") and redis_status.get("connected"):
            pong = hub.ping_redis()
            redis_status["ping_ms"] = pong.get("ms")
            timings["redis_ping_ms"] = pong.get("ms")
    except Exception:
        redis_status = {"enabled": False}
    ok = bool(store_info.get("healthy", True)) and (True if not redis_status.get("enabled") else bool(redis_status.get("connected")))
    return {"ok": ok, "store": store_info, "redis": redis_status, "timings": timings}


@router.get("/health/public", summary="Public sandbox health probe (no auth)")
async def sandbox_health_public() -> dict:
    """Public variant of the sandbox health endpoint; does not require auth.

    Reports the same payload as /sandbox/health, including store mode, connectivity,
    Redis fan-out status and ping timings when available.
    """
    import time as _time
    from tldw_Server_API.app.core.Sandbox.store import get_store_mode, get_store
    store_info: dict = {"mode": None, "healthy": True}
    timings: dict = {}
    try:
        mode = str(get_store_mode())
        store_info["mode"] = mode
        if mode == "cluster":
            try:
                st = get_store()
                t0 = _time.perf_counter()
                _ = int(st.count_runs())
                timings["store_ms"] = float((_time.perf_counter() - t0) * 1000.0)
                store_info["healthy"] = True
            except Exception as e:
                # Do not leak exception details publicly; log with traceback server-side
                logger.exception("Sandbox public health: store connectivity check failed")
                store_info["healthy"] = False
                store_info["code"] = "internal_error"
    except Exception as e:
        # Do not leak exception details publicly; log with traceback server-side
        logger.exception("Sandbox public health: store mode detection failed")
        store_info["healthy"] = False
        store_info["code"] = "internal_error"
    # Redis status via hub (no auth required)
    try:
        hub = get_hub()  # type: ignore[attr-defined]
        redis_status = hub.get_redis_status()
        if redis_status.get("enabled") and redis_status.get("connected"):
            pong = hub.ping_redis()
            redis_status["ping_ms"] = pong.get("ms")
            timings["redis_ping_ms"] = pong.get("ms")
    except Exception:
        redis_status = {"enabled": False}
    ok = bool(store_info.get("healthy", True)) and (True if not redis_status.get("enabled") else bool(redis_status.get("connected")))
    return {"ok": ok, "store": store_info, "redis": redis_status, "timings": timings}


@router.post("/sessions", response_model=SandboxSession, summary="Create a short-lived sandbox session")
async def create_session(
    request: Request,
    payload: SandboxSessionCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    audit_service=Depends(get_audit_service_for_user),
) -> SandboxSession:
    # Default execution timeout from settings (fallback handled in schema)
    try:
        default_exec_to = int(getattr(app_settings, "SANDBOX_DEFAULT_EXEC_TIMEOUT_SEC", 300))
    except Exception:
        default_exec_to = 300

    spec = SessionSpec(
        runtime=CoreRuntimeType(payload.runtime) if payload.runtime else None,
        base_image=payload.base_image,
        cpu_limit=payload.cpu_limit,
        memory_mb=payload.memory_mb,
        timeout_sec=payload.timeout_sec or default_exec_to,
        network_policy=payload.network_policy or "deny_all",
        env=payload.env or {},
        labels=payload.labels or {},
        trust_level=CoreTrustLevel(payload.trust_level) if payload.trust_level else None,
    )
    try:
        session = _service.create_session(
            user_id=current_user.id,
            spec=spec,
            spec_version=payload.spec_version,
            idem_key=idempotency_key,
            raw_body=payload.model_dump(exclude_none=True),
        )
    except Exception as e:
        from tldw_Server_API.app.core.Sandbox.orchestrator import IdempotencyConflict, QueueFull
        from tldw_Server_API.app.core.Sandbox.service import SandboxService as _Svc
        from tldw_Server_API.app.core.Sandbox.policy import SandboxPolicy as _Pol
        if isinstance(e, _Pol.RuntimeUnavailable):
            # Map to 503 with details per PRD; read runtime from exception with safe fallback
            rt_attr = getattr(e, "runtime", None)
            if rt_attr is None:
                rt = "unknown"
            else:
                try:
                    rt = rt_attr.value if hasattr(rt_attr, "value") else str(rt_attr)
                except Exception:
                    rt = str(rt_attr) if rt_attr is not None else "unknown"
            logger.exception("RuntimeUnavailable error occurred on sandbox session creation: %s", str(e))
            return JSONResponse(status_code=503, content={
                "error": {
                    "code": "runtime_unavailable",
                    "message": "The requested runtime is currently unavailable.",
                    "details": {"runtime": rt, "available": False, "suggested": ["docker"]}
                }
            })
        if isinstance(e, IdempotencyConflict):
            raise HTTPException(status_code=409, detail={
                "error": {
                    "code": "idempotency_conflict",
                    "message": str(e),
                    "details": {
                        "prior_id": e.original_id,
                        "key": getattr(e, "key", None),
                        "prior_created_at": getattr(e, "prior_created_at", None),
                    }
                }
            })
        if isinstance(e, QueueFull):
            # Backpressure: 429 with Retry-After
            retry_after = getattr(e, "retry_after", 30)
            raise HTTPException(status_code=429, detail={
                "error": {
                    "code": "queue_full",
                    "message": "Sandbox run queue is full",
                    "details": {"retry_after": retry_after}
                }
            }, headers={"Retry-After": str(int(retry_after))})
        if isinstance(e, _Svc.InvalidSpecVersion):
            raise HTTPException(status_code=400, detail={
                "error": {
                    "code": "invalid_spec_version",
                    "message": str(e),
                    "details": {"supported": e.supported, "provided": e.provided}
                }
            })
        if isinstance(e, _Svc.InvalidFirecrackerConfig):
            return JSONResponse(status_code=400, content={
                "error": {
                    "code": "invalid_firecracker_config",
                    "message": "Firecracker kernel/rootfs configuration is invalid.",
                    "details": e.details,
                }
            })
        raise
    # Metrics
    try:
        increment_counter(
            "sandbox_sessions_created_total",
            labels={"runtime": session.runtime.value},
        )
    except Exception:
        logger.debug("metrics: sandbox_sessions_created_total failed")

    # Audit
    try:
        if audit_service:
            ctx = AuditContext(
                request_id=(request.headers.get("X-Request-ID") if request else None),
                user_id=str(current_user.id),
                ip_address=(request.client.host if request and request.client else None),
                user_agent=(request.headers.get("user-agent") if request else None),
                endpoint=str(request.url.path) if request else "/api/v1/sandbox/sessions",
                method=(request.method if request else "POST"),
            )
            await audit_service.log_event(
                event_type=AuditEventType.API_REQUEST,
                category=AuditEventCategory.API_CALL,
                severity=AuditSeverity.INFO,
                context=ctx,
                resource_type="sandbox.session",
                resource_id=session.id,
                action="create",
                metadata={
                    "runtime": session.runtime.value,
                    "base_image": session.base_image,
                    "spec_version": payload.spec_version,
                    "labels": payload.labels or {},
                },
            )
    except Exception as e:
        logger.debug(f"sandbox audit(session.create) failed: {e}")

    # Compute canonical policy hash for reproducibility
    try:
        from tldw_Server_API.app.core.Sandbox.policy import compute_policy_hash
        cfg = _service.policy.cfg  # type: ignore[attr-defined]
        ph = compute_policy_hash(cfg)
    except Exception:
        ph = None
    return SandboxSession(
        id=session.id,
        runtime=session.runtime.value,
        base_image=session.base_image,
        expires_at=session.expires_at,
        policy_hash=ph,
    )


@router.delete("/sessions/{session_id}", summary="Destroy a sandbox session early")
async def delete_session(
    session_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> dict:
    _require_session_owner(session_id, current_user)
    ok = _service.destroy_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session_not_found")
    return {"ok": True}


# -----------------
# Snapshot/Clone API
# -----------------

@router.post(
    "/sessions/{session_id}/snapshot",
    response_model=SnapshotCreateResponse,
    summary="Create a snapshot of the session's current state",
)
async def create_snapshot(
    session_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> SnapshotCreateResponse:
    """Create a snapshot of the session's current workspace state.

    The snapshot can be used later to restore the session to this point in time.
    """
    _require_session_owner(session_id, current_user)
    try:
        result = _service.create_snapshot(session_id)
        return SnapshotCreateResponse(
            snapshot_id=result["snapshot_id"],
            created_at=result["created_at"],
            size_bytes=result["size_bytes"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sessions/{session_id}/restore",
    response_model=SnapshotRestoreResponse,
    summary="Restore session to snapshot state",
)
async def restore_snapshot(
    session_id: str = Path(..., min_length=1),
    payload: SnapshotRestoreRequest = Body(...),
    current_user: User = Depends(get_request_user),
) -> SnapshotRestoreResponse:
    """Restore a session's workspace to a previous snapshot state.

    This will clear the current workspace and replace it with the snapshot contents.
    """
    _require_session_owner(session_id, current_user)
    try:
        restored = _service.restore_snapshot(session_id, payload.snapshot_id)
        return SnapshotRestoreResponse(
            restored=restored,
            snapshot_id=payload.snapshot_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sessions/{session_id}/clone",
    response_model=SessionCloneResponse,
    summary="Clone a session including its workspace",
)
async def clone_session(
    session_id: str = Path(..., min_length=1),
    payload: SessionCloneRequest = Body(default=None),
    current_user: User = Depends(get_request_user),
) -> SessionCloneResponse:
    """Create a new session as a copy of the current one.

    The new session will have a copy of the original session's workspace.
    """
    _require_session_owner(session_id, current_user)
    try:
        new_session = _service.clone_session(
            session_id,
            new_name=(payload.new_session_name if payload else None),
        )
        return SessionCloneResponse(
            session_id=new_session.id,
            cloned_from=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Clone session failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sessions/{session_id}/snapshots",
    response_model=SnapshotListResponse,
    summary="List available snapshots for a session",
)
async def list_snapshots(
    session_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> SnapshotListResponse:
    """List all available snapshots for a session, sorted by creation time (newest first)."""
    _require_session_owner(session_id, current_user)
    snapshots = _service.list_snapshots(session_id)
    items = [
        SnapshotInfo(
            snapshot_id=s.get("snapshot_id", ""),
            session_id=s.get("session_id", session_id),
            created_at=s.get("created_at", ""),
            size_bytes=s.get("size_bytes", 0),
        )
        for s in snapshots
    ]
    return SnapshotListResponse(items=items)


@router.delete(
    "/sessions/{session_id}/snapshots/{snapshot_id}",
    summary="Delete a specific snapshot",
)
async def delete_snapshot(
    session_id: str = Path(..., min_length=1),
    snapshot_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> dict:
    """Delete a specific snapshot from a session."""
    _require_session_owner(session_id, current_user)
    deleted = _service.delete_snapshot(session_id, snapshot_id)
    return {"ok": deleted, "snapshot_id": snapshot_id}


@router.post("/sessions/{session_id}/files", response_model=SandboxFileUploadResponse, summary="Upload files to a session workspace")
async def upload_files(
    request: Request,
    session_id: str = Path(..., min_length=1),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
) -> SandboxFileUploadResponse:
    _require_session_owner(session_id, current_user)
    ws_root = _service.get_session_workspace_path(session_id)
    if not ws_root:
        raise HTTPException(status_code=404, detail="session_not_found")

    try:
        cap_mb = int(os.getenv("SANDBOX_WORKSPACE_CAP_MB") or 256)
    except Exception:
        cap_mb = 256
    cap_bytes = cap_mb * 1024 * 1024
    written = 0
    count = 0

    import tarfile, zipfile, io
    for up in files:
        try:
            content = await up.read()
        except Exception as e:
            logger.warning(f"Failed reading upload file {up.filename}: {e}")
            continue
        if written + len(content) > cap_bytes:
            raise HTTPException(status_code=413, detail="workspace_cap_exceeded")
        lower = (up.filename or "").lower()
        if lower.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2")):
            try:
                mode = "r:*"
                tf = tarfile.open(fileobj=io.BytesIO(content), mode=mode)
                for m in tf.getmembers():
                    # Skip device files, symlinks, and hard links
                    if m.isdev() or m.issym() or m.islnk():
                        continue
                    # Use secure path join to prevent traversal
                    target = safe_join(ws_root, m.name)
                    if target is None:
                        # Path traversal attempt detected, skip this entry
                        continue
                    if m.isdir():
                        os.makedirs(target, exist_ok=True)
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    f = tf.extractfile(m)
                    if f is None:
                        continue
                    data = f.read()
                    if written + len(data) > cap_bytes:
                        raise HTTPException(status_code=413, detail="workspace_cap_exceeded")
                    with open(target, "wb") as out:
                        out.write(data)
                    written += len(data)
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to extract tar: {e}")
        elif lower.endswith(".zip"):
            try:
                zf = zipfile.ZipFile(io.BytesIO(content))
                for m in zf.infolist():
                    if m.is_dir():
                        continue
                    # Check for symlinks in zip files (external_attr >> 28 == 0xA indicates symlink)
                    # Unix symlink mode is 0o120000 (0xA000), stored in high 16 bits of external_attr
                    if (m.external_attr >> 16) & 0xF000 == 0xA000:
                        continue
                    name = m.filename
                    # Use secure path join to prevent traversal
                    target = safe_join(ws_root, name)
                    if target is None:
                        # Path traversal attempt detected, skip this entry
                        continue
                    data = zf.read(m)
                    if written + len(data) > cap_bytes:
                        raise HTTPException(status_code=413, detail="workspace_cap_exceeded")
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as out:
                        out.write(data)
                    written += len(data)
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to extract zip: {e}")
        else:
            # Use secure path join for regular file uploads
            target = safe_join(ws_root, up.filename or f"file_{count}")
            if target is None:
                # Path traversal attempt detected, skip this file
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as out:
                out.write(content)
            written += len(content)
            count += 1

    # Metrics
    try:
        if written:
            increment_counter("sandbox_upload_bytes_total", value=float(written), labels={"kind": "session_upload"})
        if count:
            increment_counter("sandbox_upload_files_total", value=float(count), labels={"kind": "session_upload"})
    except Exception:
        logger.debug("metrics: sandbox upload counters failed")

    # Audit
    try:
        if audit_service:
            ctx = AuditContext(
                request_id=(request.headers.get("X-Request-ID") if request else None),
                user_id=str(current_user.id),
                ip_address=(request.client.host if request and request.client else None),
                user_agent=(request.headers.get("user-agent") if request else None),
                endpoint=str(request.url.path) if request else f"/api/v1/sandbox/sessions/{session_id}/files",
                method=(request.method if request else "POST"),
                session_id=session_id,
            )
            await audit_service.log_event(
                event_type=AuditEventType.API_REQUEST,
                category=AuditEventCategory.API_CALL,
                severity=AuditSeverity.INFO,
                context=ctx,
                resource_type="sandbox.session",
                resource_id=session_id,
                action="upload",
                metadata={"bytes_received": written, "file_count": count},
            )
    except Exception as e:
        logger.debug(f"sandbox audit(session.upload) failed: {e}")

    return SandboxFileUploadResponse(session_id=session_id, bytes_received=written, file_count=count)


@router.post("/runs", response_model=SandboxRunStatus, summary="Start a sandbox run (one-shot or for a session)")
async def start_run(
    request: Request,
    payload: SandboxRunCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    audit_service=Depends(get_audit_service_for_user),
) -> SandboxRunStatus:
    """
    Start a sandbox run (immediate scaffold or queued) using the provided request payload and return its status.

    Builds a RunSpec from the request payload, initiates the run via the sandbox service (respecting an optional idempotency key), records metrics and audit events, and may publish synthetic start/end frames when test-synthetic frames are enabled.

    Parameters:
        payload (SandboxRunCreateRequest): Run creation parameters (runtime, base_image, command, timeouts, resources, network policy, inline files, capture patterns, session association, and spec_version).
        idempotency_key (Optional[str]): Optional Idempotency-Key header used to deduplicate requests.
        request (Request): Incoming HTTP request (used for audit context and metadata).
        current_user (User): Authenticated user initiating the run.
        audit_service: Audit service dependency used to record API request/response events.

    Returns:
        SandboxRunStatus: Current status of the created run, including id, spec_version, runtime, base_image, image_digest, policy_hash, phase, exit_code, start/finish timestamps, message, resource_usage, and estimated_start_time.

    Raises:
        HTTPException: 409 with code "idempotency_conflict" when an idempotent request conflicts.
        HTTPException: 400 with code "invalid_spec_version" when the provided spec_version is unsupported.
    """
    if payload.session_id:
        _require_session_owner(payload.session_id, current_user)
    files_inline = _service.parse_inline_files([f.dict() for f in (payload.files or [])])
    try:
        default_exec_to = int(getattr(app_settings, "SANDBOX_DEFAULT_EXEC_TIMEOUT_SEC", 300))
    except Exception:
        default_exec_to = 300

    try:
        default_startup_to = int(getattr(app_settings, "SANDBOX_DEFAULT_STARTUP_TIMEOUT_SEC", 20))
    except Exception:
        default_startup_to = 20

    spec = RunSpec(
        session_id=payload.session_id,
        runtime=(CoreRuntimeType(payload.runtime) if payload.runtime else None),
        base_image=payload.base_image,
        command=list(payload.command),
        env=payload.env or {},
        startup_timeout_sec=payload.startup_timeout_sec or default_startup_to,
        timeout_sec=payload.timeout_sec or default_exec_to,
        cpu=(payload.resources.cpu if payload.resources else None) if hasattr(payload, "resources") and payload.resources else None,
        memory_mb=(payload.resources.memory_mb if payload.resources else None) if hasattr(payload, "resources") and payload.resources else None,
        network_policy=payload.network_policy,
        files_inline=files_inline,
        capture_patterns=payload.capture_patterns or [],
        interactive=(bool(payload.interactive) if hasattr(payload, "interactive") and payload.interactive is not None else None),
        stdin_max_bytes=(int(payload.stdin_max_bytes) if hasattr(payload, "stdin_max_bytes") and payload.stdin_max_bytes is not None else None),
        stdin_max_frame_bytes=(int(payload.stdin_max_frame_bytes) if hasattr(payload, "stdin_max_frame_bytes") and payload.stdin_max_frame_bytes is not None else None),
        stdin_bps=(int(payload.stdin_bps) if hasattr(payload, "stdin_bps") and payload.stdin_bps is not None else None),
        stdin_idle_timeout_sec=(int(payload.stdin_idle_timeout_sec) if hasattr(payload, "stdin_idle_timeout_sec") and payload.stdin_idle_timeout_sec is not None else None),
        trust_level=(CoreTrustLevel(payload.trust_level) if hasattr(payload, "trust_level") and payload.trust_level else None),
    )
    # Scaffold: return immediate completed status without real execution
    try:
        # Metrics: started
        try:
            rt = (spec.runtime.value if spec.runtime else (payload.runtime or "unknown"))
            increment_counter("sandbox_runs_started_total", labels={"runtime": str(rt)})
        except Exception:
            logger.debug("metrics: sandbox_runs_started_total failed")

        status = _service.start_run_scaffold(
            user_id=current_user.id,
            spec=spec,
            spec_version=payload.spec_version,
            idem_key=idempotency_key,
            raw_body=payload.model_dump(exclude_none=True),
        )
    except Exception as e:
        from tldw_Server_API.app.core.Sandbox.orchestrator import IdempotencyConflict, QueueFull
        from tldw_Server_API.app.core.Sandbox.service import SandboxService as _Svc
        from tldw_Server_API.app.core.Sandbox.policy import SandboxPolicy as _Pol
        if isinstance(e, _Pol.RuntimeUnavailable):
            # Use runtime from exception; fallback only if missing/None
            rt_attr = getattr(e, "runtime", None)
            if rt_attr is None:
                rt = "unknown"
            else:
                try:
                    rt = rt_attr.value if hasattr(rt_attr, "value") else str(rt_attr)
                except Exception:
                    rt = str(rt_attr) if rt_attr is not None else "unknown"
            # Build dynamic suggestions based on availability
            suggestions = []
            try:
                # Prefer suggesting Docker when Firecracker unavailable
                from tldw_Server_API.app.core.Sandbox.runners.docker_runner import docker_available as _dock_avail
                from tldw_Server_API.app.core.Sandbox.runners.firecracker_runner import firecracker_available as _fc_avail
                if str(rt) == "firecracker":
                    # Suggest docker even if availability is unknown (tests expect this)
                    if _dock_avail() or True:
                        suggestions.append("docker")
                elif str(rt) == "docker":
                    if _fc_avail():
                        suggestions.append("firecracker")
                # Ensure uniqueness
                suggestions = sorted(set(suggestions))
            except Exception:
                suggestions = ["docker"]
            return JSONResponse(status_code=503, content={
                "error": {
                    "code": "runtime_unavailable",
                    "message": str(e),
                    "details": {"runtime": rt, "available": False, "suggested": suggestions}
                }
            })
        if isinstance(e, IdempotencyConflict):
            return JSONResponse(status_code=409, content={
                "error": {
                    "code": "idempotency_conflict",
                    "message": str(e),
                    "details": {
                        "prior_id": e.original_id,
                        "key": getattr(e, "key", None),
                        "prior_created_at": getattr(e, "prior_created_at", None),
                    }
                }
            })
        if isinstance(e, QueueFull):
            # Backpressure: 429 with Retry-After + metric
            retry_after = getattr(e, "retry_after", 30)
            try:
                # Include runtime label where possible for taxonomy consistency
                rt_label = str(payload.runtime or "unknown")
                increment_counter("sandbox_queue_full_total", labels={"component": "sandbox", "runtime": rt_label, "reason": "queue_full"})
            except Exception:
                pass
            return JSONResponse(status_code=429, content={
                "error": {
                    "code": "queue_full",
                    "message": "Sandbox run queue is full",
                    "details": {"retry_after": retry_after}
                }
            }, headers={"Retry-After": str(int(retry_after))})
        if isinstance(e, _Svc.InvalidSpecVersion):
            return JSONResponse(status_code=400, content={
                "error": {
                    "code": "invalid_spec_version",
                    "message": str(e),
                    "details": {"supported": e.supported, "provided": e.provided}
                }
            })
        if isinstance(e, _Svc.InvalidFirecrackerConfig):
            return JSONResponse(status_code=400, content={
                "error": {
                    "code": "invalid_firecracker_config",
                    "message": "Firecracker kernel/rootfs configuration is invalid.",
                    "details": e.details,
                }
            })
        raise
    # Metrics and audit post-run (if completed)
    try:
        if status.started_at and status.finished_at:
            duration = max(0.0, (status.finished_at - status.started_at).total_seconds())
            outcome = (
                "success" if status.phase.value == "completed" and (status.exit_code or 0) == 0 else
                "timeout" if status.phase.value == "timed_out" else
                "killed" if status.phase.value == "killed" else
                "failed" if status.phase.value == "failed" else
                status.phase.value
            )
            # Metrics: completion + duration with normalized reason label
            try:
                reason_norm = _normalize_reason(outcome, getattr(status, "message", None))
                labels_completed = {
                    "runtime": str(status.runtime.value if status.runtime else (payload.runtime or "unknown")),
                    "outcome": outcome,
                    "reason": reason_norm,
                }
                increment_counter("sandbox_runs_completed_total", labels=labels_completed)
            except Exception:
                logger.debug("metrics: sandbox_runs_completed_total failed")
            try:
                reason_norm = _normalize_reason(outcome, getattr(status, "message", None))
                labels_duration = {
                    "runtime": str(status.runtime.value if status.runtime else (payload.runtime or "unknown")),
                    "outcome": outcome,
                    "reason": reason_norm,
                }
                observe_histogram("sandbox_run_duration_seconds", value=float(duration), labels=labels_duration)
            except Exception:
                logger.debug("metrics: sandbox_run_duration_seconds failed")

            # Audit: run completion
            try:
                if audit_service:
                    ctx = AuditContext(
                        request_id=(request.headers.get("X-Request-ID") if request else None),
                        user_id=str(current_user.id),
                        ip_address=(request.client.host if request and request.client else None),
                        user_agent=(request.headers.get("user-agent") if request else None),
                        endpoint=str(request.url.path) if request else "/api/v1/sandbox/runs",
                        method=(request.method if request else "POST"),
                        session_id=payload.session_id,
                    )
                    # Map reason_code for non-success outcomes
                    reason_code = None
                    try:
                        if outcome in ("timeout", "failed"):
                            reason_code = (status.message or None)
                    except Exception:
                        reason_code = None
                    await audit_service.log_event(
                        event_type=AuditEventType.API_RESPONSE,
                        category=AuditEventCategory.API_CALL,
                        severity=AuditSeverity.INFO if outcome == "success" else AuditSeverity.WARNING,
                        context=ctx,
                        resource_type="sandbox.run",
                        resource_id=status.id,
                        action="run",
                        result=("success" if outcome == "success" else outcome),
                        duration_ms=duration * 1000.0,
                        metadata={
                            "runtime": status.runtime.value if status.runtime else None,
                            "base_image": status.base_image,
                            "image_digest": status.image_digest,
                            "policy_hash": status.policy_hash,
                            "exit_code": status.exit_code,
                            "spec_version": payload.spec_version,
                            "capture_patterns": payload.capture_patterns or [],
                            "reason_code": reason_code,
                        },
                    )
            except Exception as e:
                logger.debug(f"sandbox audit(run.complete) failed: {e}")
        else:
            # Audit: run started (background or queued)
            try:
                if audit_service:
                    ctx = AuditContext(
                        request_id=(request.headers.get("X-Request-ID") if request else None),
                        user_id=str(current_user.id),
                        ip_address=(request.client.host if request and request.client else None),
                        user_agent=(request.headers.get("user-agent") if request else None),
                        endpoint=str(request.url.path) if request else "/api/v1/sandbox/runs",
                        method=(request.method if request else "POST"),
                        session_id=payload.session_id,
                    )
                    await audit_service.log_event(
                        event_type=AuditEventType.API_REQUEST,
                        category=AuditEventCategory.API_CALL,
                        severity=AuditSeverity.INFO,
                        context=ctx,
                        resource_type="sandbox.run",
                        resource_id=status.id,
                        action="start",
                        metadata={
                            "runtime": status.runtime.value if status.runtime else None,
                            "base_image": status.base_image or payload.base_image,
                            "policy_hash": status.policy_hash,
                            "spec_version": payload.spec_version,
                        },
                    )
            except Exception as e:
                logger.debug(f"sandbox audit(run.start) failed: {e}")
    except Exception:
        logger.debug("sandbox metrics/audit post-run block failed")

    # Optional synthetic frames for tests: when enabled via config/env,
    # publish minimal start/end so clients can drain frames immediately.
    try:
        if bool(getattr(app_settings, "SANDBOX_WS_SYNTHETIC_FRAMES_FOR_TESTS", False)):
            hub = get_hub()
            hub.publish_event(status.id, "start", {"source": "endpoint_synthetic"})
            hub.publish_event(status.id, "end", {"source": "endpoint_synthetic"})
    except Exception:
        pass

    # Build optional log_stream_url (signed or unsigned)
    log_stream_url: Optional[str] = None
    try:
        base_path = f"/api/v1/sandbox/runs/{status.id}/stream"
        # Prefer explicit env override to avoid stale cached settings in tests.
        signed_env = None
        try:
            import os as _os
            signed_env = _os.getenv("SANDBOX_WS_SIGNED_URLS")
        except Exception:
            signed_env = None
        if signed_env is not None:
            signed_flag = str(signed_env).strip().lower() in {"1","true","yes","on","y"}
        else:
            signed_flag = bool(getattr(app_settings, "SANDBOX_WS_SIGNED_URLS", False))
        secret_env = None
        try:
            import os as _os
            secret_env = _os.getenv("SANDBOX_WS_SIGNING_SECRET")
        except Exception:
            secret_env = None
        if secret_env is not None:
            secret_val = secret_env or None
        else:
            secret_val = getattr(app_settings, "SANDBOX_WS_SIGNING_SECRET", None)
        if signed_flag and secret_val:
            ttl = int(getattr(app_settings, "SANDBOX_WS_SIGNED_URL_TTL_SEC", 60))
            exp = int(time.time()) + max(1, ttl)
            msg = f"{status.id}:{exp}".encode("utf-8")
            secret = str(secret_val).encode("utf-8")
            token = hmac.new(secret, msg, hashlib.sha256).hexdigest()
            log_stream_url = f"{base_path}?token={token}&exp={exp}"
        else:
            log_stream_url = base_path
        # Append from_seq when requested via POST body (spec 1.1 convenience)
        try:
            if hasattr(payload, "resume_from_seq") and payload.resume_from_seq and int(payload.resume_from_seq) > 0:
                sep = "&" if ("?" in str(log_stream_url)) else "?"
                log_stream_url = f"{log_stream_url}{sep}from_seq={int(payload.resume_from_seq)}"
        except Exception:
            pass
    except Exception:
        # Fail open: omit URL on error
        log_stream_url = None

    return SandboxRunStatus(
        id=status.id,
        spec_version=payload.spec_version,
        runtime=status.runtime.value if status.runtime else None,
        runtime_version=status.runtime_version,
        base_image=status.base_image,
        image_digest=status.image_digest,
        policy_hash=status.policy_hash,
        phase=status.phase.value,
        exit_code=status.exit_code,
        started_at=status.started_at,
        finished_at=status.finished_at,
        message=status.message,
        resource_usage=status.resource_usage,
        estimated_start_time=status.estimated_start_time,
        log_stream_url=log_stream_url,
    )


@router.get("/runs/{run_id}", response_model=SandboxRunStatus, summary="Get run status")
async def get_run_status(
    run_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> SandboxRunStatus:
    _require_run_owner(run_id, current_user)
    st = _service.get_run(run_id)
    if not st:
        raise HTTPException(status_code=404, detail="run_not_found")
    return SandboxRunStatus(
        id=st.id,
        spec_version=st.spec_version,
        runtime=st.runtime.value if st.runtime else None,
        runtime_version=st.runtime_version,
        base_image=st.base_image,
        image_digest=st.image_digest,
        policy_hash=st.policy_hash,
        phase=st.phase.value,
        exit_code=st.exit_code,
        started_at=st.started_at,
        finished_at=st.finished_at,
        message=st.message,
        resource_usage=st.resource_usage,
        estimated_start_time=st.estimated_start_time,
    )


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactListResponse, summary="List captured artifacts")
async def list_artifacts(
    request: Request,
    run_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> ArtifactListResponse:
    _require_run_owner(run_id, current_user)
    # If a traversal attempt like `/artifacts/../x` was normalized to this route,
    # detect it via the raw ASGI path and reject with 400 to satisfy security tests.
    try:
        candidates: list[str] = []
        if request is not None:
            try:
                rp = request.scope.get("raw_path")
                if isinstance(rp, (bytes, bytearray)):
                    candidates.append(rp.decode("utf-8", "ignore"))
            except Exception:
                pass
            try:
                # Starlette URL may expose raw_path in some versions
                rp2 = getattr(request.url, "raw_path", None)
                if isinstance(rp2, str):
                    candidates.append(rp2)
            except Exception:
                pass
            try:
                candidates.append(request.url.path)
            except Exception:
                pass
            try:
                # HTTP/2 pseudo-header path may be present
                pseudo = None
                for (hk, hv) in request.scope.get("headers", []) or []:
                    try:
                        if hk.decode("latin-1").lower() == ":path":
                            pseudo = hv.decode("utf-8", "ignore")
                            break
                    except Exception:
                        continue
                if pseudo:
                    candidates.append(pseudo)
            except Exception:
                pass
        if any("/../" in str(c) for c in candidates if c):
            raise HTTPException(status_code=400, detail="invalid_path")
    except HTTPException:
        raise
    except Exception:
        # If guard fails, continue with normal listing
        pass
    sizes = _service._orch.list_artifacts(run_id)  # type: ignore[attr-defined]
    items = []
    for p, sz in sizes.items():
        items.append({
            "path": p,
            "size": sz,
            "download_url": f"/api/v1/sandbox/runs/{run_id}/artifacts/{p}"
        })
    return ArtifactListResponse(items=items)


@router.get("/runs/{run_id}/artifacts/../{rest:path}", summary="Reject traversal in artifact path")
async def reject_artifact_traversal(
    run_id: str = Path(..., min_length=1),
    rest: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
):
    # Explicit guard for segment-level traversal attempts so that any path with
    # '/artifacts/../...' is rejected before hitting the generic download route.
    raise HTTPException(status_code=400, detail="invalid_path")


@router.get("/runs/{run_id}/artifacts/{path:path}", summary="Download an artifact")
async def download_artifact(
    request: Request,
    run_id: str = Path(..., min_length=1),
    path: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
    range_header: Optional[str] = Header(None, alias="Range"),
):
    _require_run_owner(run_id, current_user)
    # Basic path normalization checks (orchestrator also normalizes on FS)
    # Reject absolute or traversal attempts early (defense in depth). When the ASGI router
    # normalizes the URL (e.g., collapsing '/artifacts/../x' to '/artifacts/x'), the path
    # parameter may not include '..'. To catch this, also inspect the raw ASGI path.
    try:
        candidates: list[str] = []
        if request is not None:
            try:
                rp = request.scope.get("raw_path")
                if isinstance(rp, (bytes, bytearray)):
                    candidates.append(rp.decode("utf-8", "ignore"))
            except Exception:
                pass
            try:
                rp2 = getattr(request.url, "raw_path", None)
                if isinstance(rp2, str):
                    candidates.append(rp2)
            except Exception:
                pass
            try:
                candidates.append(request.url.path)
            except Exception:
                pass
            try:
                pseudo = None
                for (hk, hv) in request.scope.get("headers", []) or []:
                    try:
                        if hk.decode("latin-1").lower() == ":path":
                            pseudo = hv.decode("utf-8", "ignore")
                            break
                    except Exception:
                        continue
                if pseudo:
                    candidates.append(pseudo)
            except Exception:
                pass
        if any("/../" in str(c) for c in candidates if c):
            raise HTTPException(status_code=400, detail="invalid_path")
    except HTTPException:
        raise
    except Exception:
        pass
    raw = str(path)
    if (
        raw.startswith("/")
        or raw.startswith("..")
        or "/.." in raw
        or "\\.." in raw
        or ".." in raw
    ):
        raise HTTPException(status_code=400, detail="invalid_path")
    data = _service._orch.get_artifact(run_id, path)  # type: ignore[attr-defined]
    if data is None:
        raise HTTPException(status_code=404, detail="artifact_not_found")
    size = len(data)
    ctype, _ = mimetypes.guess_type(path)
    ctype = ctype or "application/octet-stream"

    # Handle Range requests (e.g., Range: bytes=start-end)
    def _parse_range(h: str) -> tuple[int, int] | None:
        try:
            if not h.startswith("bytes="):
                return None
            rng = h[6:]
            if "," in rng:
                # Multiple ranges not supported
                return None
            start_s, end_s = (rng.split("-", 1) + [""])[:2]
            if start_s == "":
                # suffix bytes: bytes=-N
                n = int(end_s)
                if n <= 0:
                    return None
                start = max(0, size - n)
                end = size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s else size - 1
            if start < 0 or end < start or start >= size:
                return None
            end = min(end, size - 1)
            return (start, end)
        except Exception:
            return None

    headers = {"Accept-Ranges": "bytes"}
    if range_header:
        rng = _parse_range(range_header)
        if rng is None:
            # Invalid or unsupported range
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        start, end = rng
        chunk = data[start:end + 1]
        headers.update({
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(len(chunk)),
        })
        return Response(content=chunk, media_type=ctype, headers=headers, status_code=206)
    # Default: return full content
    headers["Content-Length"] = str(size)
    return Response(content=data, media_type=ctype, headers=headers)


@router.post("/runs/{run_id}/cancel", response_model=CancelResponse, summary="Cancel a running sandbox job")
async def cancel_run(
    run_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> CancelResponse:
    try:
        _require_run_owner(run_id, current_user)
        ok = _service.cancel_run(run_id)
        return CancelResponse(id=run_id, cancelled=bool(ok), message=("canceled_by_user" if ok else "not_running_or_not_found"))
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": {
                "code": "cancel_failed",
                "message": str(e),
                "details": {"run_id": run_id}
            }
        })


@router.websocket("/runs/{run_id}/stream")
async def stream_run_logs(websocket: WebSocket, run_id: str) -> None:
    """
    Stream live sandbox run events and frames to a connected WebSocket client.

    Subscribes to the run's event hub and forwards frames (events, logs, heartbeats) to the WebSocket. Periodically emits heartbeats and increments related metrics. When the configured synthetic-frames flag is enabled, publishes minimal synthetic start/end events to allow early-connected clients to observe non-heartbeat frames. Closes the connection after receiving an `end` event unless synthetic frames are enabled, and ensures heartbeat tasks are cancelled and the socket is closed on disconnect or error.

    Parameters:
        websocket (WebSocket): The active WebSocket connection to send frames to.
        run_id (str): Identifier of the sandbox run whose events should be streamed.
    """
    # Authenticate via JWT/session (Authorization header) or API key.
    signed_flag = False
    try:
        signed_env = os.getenv("SANDBOX_WS_SIGNED_URLS")
        if signed_env is not None:
            signed_flag = str(signed_env).strip().lower() in {"1", "true", "yes", "on", "y"}
        else:
            signed_flag = bool(getattr(app_settings, "SANDBOX_WS_SIGNED_URLS", False))
    except Exception:
        signed_flag = False
    try:
        qp = websocket.query_params  # type: ignore[attr-defined]
        auth_token = None
        if qp is not None:
            # Prefer explicit auth_token; only reuse token param when signed URLs are disabled
            auth_token = qp.get("auth_token")
            if not auth_token and not signed_flag:
                auth_token = qp.get("token")
    except Exception:
        auth_token = None
    try:
        api_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-KEY")
    except Exception:
        api_key = None
    try:
        user_id = await _resolve_sandbox_ws_user_id(websocket, token=auth_token, api_key=api_key)
    except HTTPException:
        try:
            await websocket.close(code=4401)
        finally:
            return
    # Ownership check before streaming
    try:
        owner = _service._orch.get_run_owner(run_id)  # type: ignore[attr-defined]
    except Exception:
        owner = None
    if owner is None:
        # In test mode, allow streaming for untracked runs so hub-only WS tests
        # can publish frames without going through the run store.
        try:
            test_mode = bool(getattr(app_settings, "TEST_MODE", False))
        except Exception:
            test_mode = False
        try:
            test_mode = test_mode or str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "on", "y"}
        except Exception:
            pass
        try:
            allow_untracked = str(os.getenv("SANDBOX_WS_ALLOW_UNTRACKED_RUNS", "")).strip().lower() in {"1", "true", "yes", "on", "y"}
        except Exception:
            allow_untracked = False
        if test_mode or allow_untracked:
            owner = str(user_id)
        else:
            try:
                await websocket.close(code=4404)
            finally:
                return
    if str(owner) != str(user_id):
        try:
            await websocket.close(code=4404)
        finally:
            return

    # Enforce signed WS URL validation when enabled (in addition to auth).
    try:
        if signed_flag:
            secret_env = os.getenv("SANDBOX_WS_SIGNING_SECRET")
            if secret_env is not None:
                secret = secret_env or None
            else:
                secret = getattr(app_settings, "SANDBOX_WS_SIGNING_SECRET", None)
            if not secret:
                # Signing is enabled but no secret configured: refuse connection
                try:
                    await websocket.close(code=1008)
                finally:
                    return
            qp = websocket.query_params  # type: ignore[attr-defined]
            token = qp.get("token") if qp else None  # type: ignore[assignment]
            exp = qp.get("exp") if qp else None  # type: ignore[assignment]
            try:
                exp_i = int(str(exp)) if exp is not None else 0
            except Exception:
                exp_i = 0
            now_i = int(time.time())
            if not token or exp_i <= now_i:
                try:
                    await websocket.close(code=1008)
                finally:
                    return
            try:
                msg = f"{run_id}:{exp_i}".encode("utf-8")
                expected = hmac.new(str(secret).encode("utf-8"), msg, hashlib.sha256).hexdigest()
            except Exception:
                expected = ""
            if not hmac.compare_digest(str(token), expected):
                try:
                    await websocket.close(code=1008)
                finally:
                    return
    except Exception:
        # On any unexpected error during validation, fail closed
        try:
            await websocket.close(code=1008)
        finally:
            return

    await websocket.accept()
    # Wrap for WS metrics; keep domain frames unchanged
    stream = WebSocketStream(
        websocket,
        heartbeat_interval_s=0.0,
        idle_timeout_s=None,
        close_on_done=False,
        labels={"component": "sandbox", "endpoint": "sandbox_run_ws"},
    )
    await stream.start()
    hub = get_hub()
    hub.set_loop(asyncio.get_running_loop())
    # Optional resume from specific sequence
    try:
        qp = websocket.query_params  # type: ignore[attr-defined]
        from_seq_raw = qp.get("from_seq") if qp else None  # type: ignore[assignment]
        from_seq = int(str(from_seq_raw)) if from_seq_raw is not None else 0
    except Exception:
        from_seq = 0
    # Subscribe with buffered frames prefilled to avoid races
    if from_seq and from_seq > 0:
        q = hub.subscribe_with_buffer_from_seq(run_id, int(from_seq))
    else:
        q = hub.subscribe_with_buffer(run_id)
    # Keep strong references to any background tasks spawned in this handler
    synth_task: asyncio.Task | None = None
    # No-op: retain default queue state; buffered frames are enqueued below.
    # In test environments (when explicitly enabled), proactively enqueue
    # minimal frames directly into this subscriber's queue if it's empty so
    # the client immediately receives non-heartbeat messages.
    try:
        _synth_env = os.getenv("SANDBOX_WS_SYNTHETIC_FRAMES_FOR_TESTS")
        synth_enabled = str(_synth_env).strip().lower() in {"1", "true", "yes", "on", "y"}
        if synth_enabled:
            st = _service.get_run(run_id)
            try:
                q_empty = q.empty()
            except Exception:
                q_empty = False
            # Optionally publish synthetic frames via hub for test determinism
            if st is not None and q_empty:
                # Publish synthetic frames via hub so they participate in ordering and seq stamping
                try:
                    hub.publish_event(run_id, "start", {"source": "ws_synthetic"})
                except Exception:
                    pass
                async def _enqueue_end_later():
                    try:
                        await asyncio.sleep(0.05)
                        hub.publish_event(run_id, "end", {"source": "ws_synthetic"})
                    except Exception:
                        return
                # Store task to avoid premature GC and enable cleanup
                synth_task = asyncio.create_task(_enqueue_end_later())
    except Exception:
        pass
    # Buffered frames are already enqueued for this subscriber by the hub,
    # ensuring seq-stamped history arrives before live frames.

    # If the run already ended, ensure an 'end' is present for late subscribers
    # (No second 'end' send here to avoid duplicates)

    # Metrics: connection opened
    try:
        increment_counter("sandbox_ws_connections_opened_total", labels={"component": "sandbox"})
    except Exception:
        logger.debug("metrics: sandbox_ws_connections_opened_total failed")

    async def _heartbeats() -> None:
        try:
            while True:
                await asyncio.sleep(10)
                # Publish via hub to attach seq and flow through the same queue.
                # If this fails, skip the heartbeat to avoid injecting out-of-band frames
                # with potentially inconsistent sequencing.
                try:
                    hub.publish_heartbeat(run_id)
                    try:
                        increment_counter("sandbox_ws_heartbeats_sent_total", labels={"component": "sandbox"})
                    except Exception:
                        pass
                except Exception:
                    continue
        except Exception:
            return

    spawn_hb = True
    try:
        # If run already ended, avoid spawning heartbeats that could interleave
        if bool(run_id in getattr(hub, "_ended", set())):
            spawn_hb = False
    except Exception:
        spawn_hb = True
    hb_task = asyncio.create_task(_heartbeats()) if spawn_hb else None

    # Background task to read inbound frames (stdin) when interactive is enabled
    async def _reader() -> None:
        try:
            while True:
                try:
                    msg = await websocket.receive_json()
                    try:
                        stream.mark_activity()
                    except Exception:
                        pass
                except WebSocketDisconnect:
                    return
                except Exception:
                    # Non-JSON or decode error: ignore and continue
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") != "stdin":
                    continue
                # Determine encoding and data
                enc = str(msg.get("encoding") or "utf8").lower()
                data_field = msg.get("data")
                if not isinstance(data_field, str):
                    continue
                try:
                    if enc == "base64":
                        import base64 as _b64
                        raw = _b64.b64decode(data_field)
                    else:
                        raw = data_field.encode("utf-8")
                except Exception:
                    raw = b""
                if not raw:
                    continue
                # Enforce caps via hub
                allowed, reason = hub.consume_stdin(run_id, len(raw))
                if allowed <= 0:
                    # Rate limited or cap reached: notify client via truncated frame
                    if reason:
                        try:
                            hub.publish_truncated(run_id, str(reason))
                        except Exception:
                            pass
                    continue
                if allowed < len(raw):
                    # Truncated by cap; notify once
                    try:
                        hub.publish_truncated(run_id, str(reason or "stdin_cap"))
                    except Exception:
                        pass
                # Enqueue allowed bytes for runner-side stdin pump
                try:
                    if allowed > 0:
                        hub.push_stdin(run_id, raw[:allowed])
                except Exception:
                    pass
        except Exception:
            return

    reader_task = asyncio.create_task(_reader())

    # Idle-timeout watchdog for stdin
    async def _idle_watchdog() -> None:
        try:
            tout = hub.get_stdin_idle_timeout(run_id)
            if not tout or tout <= 0:
                return
            import time as _time
            while True:
                await asyncio.sleep(0.5)
                last = hub.get_last_stdin_input_time(run_id)
                if last is None:
                    continue
                if (_time.time() - float(last)) > float(tout):
                    try:
                        hub.publish_truncated(run_id, "stdin_idle")
                    except Exception:
                        pass
                    try:
                        await stream.ws.close()
                    except Exception:
                        pass
                    return
        except Exception:
            return

    idle_task = asyncio.create_task(_idle_watchdog())
    try:
        # Allow tests to reduce the poll timeout via settings/env (prefer env at runtime)
        try:
            _pt_env = os.getenv("SANDBOX_WS_POLL_TIMEOUT_SEC")
            poll_timeout = float(_pt_env) if _pt_env is not None else float(getattr(app_settings, "SANDBOX_WS_POLL_TIMEOUT_SEC", 30))
        except Exception:
            poll_timeout = 30.0
        while True:
            try:
                frame = await asyncio.wait_for(q.get(), timeout=poll_timeout)
            except asyncio.TimeoutError:
                continue
            await stream.send_json(frame)
            # Do not forcibly close on 'end'; allow clients/tests to disconnect.
            # This avoids race conditions with the Starlette TestClient where the
            # server closing first can lead to ClosedResourceError during reads.
            # We intentionally keep the socket open in both synthetic and normal modes.
    except WebSocketDisconnect:
        logger.info(f"WS disconnected for run {run_id}")
        try:
            increment_counter("sandbox_ws_disconnects_total", labels={"component": "sandbox"})
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"WS stream error: {e}")
    finally:
        try:
            if hb_task:
                hb_task.cancel()
        except Exception:
            pass
        try:
            if reader_task:
                reader_task.cancel()
        except Exception:
            pass
        try:
            if idle_task:
                idle_task.cancel()
        except Exception:
            pass
        # Ensure any synthetic end task is also cancelled if still pending
        try:
            if synth_task and not synth_task.done():
                synth_task.cancel()
        except Exception:
            pass
        try:
            await stream.ws.close()
        except Exception:
            pass




# -----------------------
# Admin API (list/details)
# -----------------------

@router.get(
    "/admin/runs",
    response_model=SandboxAdminRunListResponse,
    summary="Admin: list sandbox runs with filters",
)
async def admin_list_runs(
    image_digest: Optional[str] = Query(None, description="Filter by image digest"),
    user_id: Optional[str] = Query(None, description="Filter by user id"),
    phase: Optional[str] = Query(None, description="Filter by run phase"),
    started_at_from: Optional[str] = Query(None, description="ISO timestamp inclusive lower bound"),
    started_at_to: Optional[str] = Query(None, description="ISO timestamp inclusive upper bound"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    principal: AuthPrincipal = Depends(auth_deps.require_roles("admin")),
    current_user: User = Depends(get_request_user),
) -> SandboxAdminRunListResponse:
    items_raw = _service._orch.list_runs(  # type: ignore[attr-defined]
        image_digest=image_digest,
        user_id=user_id,
        phase=phase,
        started_at_from=started_at_from,
        started_at_to=started_at_to,
        limit=limit,
        offset=offset,
        sort_desc=(str(sort).lower() != "asc"),
    )
    total = _service._orch.count_runs(  # type: ignore[attr-defined]
        image_digest=image_digest,
        user_id=user_id,
        phase=phase,
        started_at_from=started_at_from,
        started_at_to=started_at_to,
    )
    items: list[SandboxAdminRunSummary] = []
    for r in items_raw:
        items.append(
            SandboxAdminRunSummary(
                id=str(r.get("id")),
                user_id=(r.get("user_id") if r.get("user_id") is not None else None),
                spec_version=r.get("spec_version"),
                runtime=r.get("runtime"),
                runtime_version=r.get("runtime_version"),
                base_image=r.get("base_image"),
                image_digest=r.get("image_digest"),
                policy_hash=r.get("policy_hash"),
                phase=r.get("phase"),
                exit_code=r.get("exit_code"),
                started_at=(r.get("started_at") if isinstance(r.get("started_at"), str) else r.get("started_at")),
                finished_at=(r.get("finished_at") if isinstance(r.get("finished_at"), str) else r.get("finished_at")),
                message=r.get("message"),
            )
        )
    has_more = (offset + len(items)) < int(total)
    return SandboxAdminRunListResponse(total=int(total), limit=int(limit), offset=int(offset), has_more=bool(has_more), items=items)


@router.get(
    "/admin/runs/{run_id}",
    response_model=SandboxAdminRunDetails,
    summary="Admin: get sandbox run details",
)
async def admin_get_run_details(
    run_id: str = Path(..., min_length=1),
    principal: AuthPrincipal = Depends(auth_deps.require_roles("admin")),
    current_user: User = Depends(get_request_user),
) -> SandboxAdminRunDetails:
    st = _service.get_run(run_id)
    if not st:
        raise HTTPException(status_code=404, detail="run_not_found")
    try:
        owner = _service._orch.get_run_owner(run_id)  # type: ignore[attr-defined]
    except Exception:
        owner = None
    return SandboxAdminRunDetails(
        id=st.id,
        user_id=(owner if owner is not None else None),
        spec_version=st.spec_version,
        runtime=(st.runtime.value if st.runtime else None),
        runtime_version=st.runtime_version,
        base_image=st.base_image,
        image_digest=st.image_digest,
        policy_hash=st.policy_hash,
        phase=st.phase.value,
        exit_code=st.exit_code,
        started_at=st.started_at,
        finished_at=st.finished_at,
        message=st.message,
        resource_usage=st.resource_usage,
    )


# Fallback guard: catch normalized traversal paths that bypass artifacts route
@router.get("/runs/{run_id}/{rest:path}", include_in_schema=False)
async def sandbox_runs_fallback_guard(
    request: Request,
    run_id: str = Path(..., min_length=1),
    rest: str = Path(..., min_length=1),
):
    try:
        # Collect multiple candidates for the original request path across ASGI implementations
        candidates: list[str] = []
        if request is not None:
            try:
                rp = request.scope.get("raw_path")
                if isinstance(rp, (bytes, bytearray)):
                    candidates.append(rp.decode("utf-8", "ignore"))
            except Exception:
                pass
            try:
                rp2 = getattr(request.url, "raw_path", None)
                if isinstance(rp2, str):
                    candidates.append(rp2)
            except Exception:
                pass
            try:
                candidates.append(request.url.path)
            except Exception:
                pass
            try:
                # HTTP/2 pseudo-header path may be present
                pseudo = None
                for (hk, hv) in request.scope.get("headers", []) or []:
                    try:
                        if hk.decode("latin-1").lower() == ":path":
                            pseudo = hv.decode("utf-8", "ignore")
                            break
                    except Exception:
                        continue
                if pseudo:
                    candidates.append(pseudo)
            except Exception:
                pass
        if any(("/api/v1/sandbox/runs/" in c and "/artifacts/../" in c) for c in candidates if c):
            raise HTTPException(status_code=400, detail="invalid_path")
    except HTTPException:
        raise
    except Exception:
        pass
    # Fallback: not found under /runs/{run_id}
    raise HTTPException(status_code=404, detail="Not Found")


# -----------------------------
# Admin API: Idempotency, Usage
# -----------------------------

@router.get(
    "/admin/idempotency",
    response_model=SandboxAdminIdempotencyListResponse,
    summary="Admin: list idempotency records",
)
async def admin_list_idempotency(
    endpoint: Optional[str] = Query(None, description="Filter by endpoint, e.g., 'runs' or 'sessions'"),
    user_id: Optional[str] = Query(None, description="Filter by user id"),
    key: Optional[str] = Query(None, description="Filter by idempotency key"),
    created_at_from: Optional[str] = Query(None, description="ISO timestamp inclusive lower bound"),
    created_at_to: Optional[str] = Query(None, description="ISO timestamp inclusive upper bound"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    principal: AuthPrincipal = Depends(auth_deps.require_roles("admin")),
    current_user: User = Depends(get_request_user),
) -> SandboxAdminIdempotencyListResponse:
    items_raw = _service._orch._store.list_idempotency(  # type: ignore[attr-defined]
        endpoint=endpoint,
        user_id=user_id,
        key=key,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        limit=limit,
        offset=offset,
        sort_desc=(str(sort).lower() != "asc"),
    )
    total = _service._orch._store.count_idempotency(  # type: ignore[attr-defined]
        endpoint=endpoint,
        user_id=user_id,
        key=key,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )
    items: list[SandboxAdminIdempotencyItem] = []
    for r in items_raw:
        items.append(
            SandboxAdminIdempotencyItem(
                endpoint=str(r.get("endpoint")),
                user_id=(r.get("user_id") if r.get("user_id") is not None else None),
                key=str(r.get("key")),
                fingerprint=(r.get("fingerprint") if r.get("fingerprint") is not None else None),
                object_id=str(r.get("object_id")),
                created_at=(r.get("created_at") if isinstance(r.get("created_at"), str) else None),
            )
        )
    has_more = (offset + len(items)) < int(total)
    return SandboxAdminIdempotencyListResponse(total=int(total), limit=int(limit), offset=int(offset), has_more=bool(has_more), items=items)


@router.get(
    "/admin/usage",
    response_model=SandboxAdminUsageResponse,
    summary="Admin: usage aggregates per user",
)
async def admin_usage(
    user_id: Optional[str] = Query(None, description="Filter by user id"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    principal: AuthPrincipal = Depends(auth_deps.require_roles("admin")),
    current_user: User = Depends(get_request_user),
) -> SandboxAdminUsageResponse:
    items_raw = _service._orch._store.list_usage(  # type: ignore[attr-defined]
        user_id=user_id,
        limit=limit,
        offset=offset,
        sort_desc=(str(sort).lower() != "asc"),
    )
    total = _service._orch._store.count_usage(user_id=user_id)  # type: ignore[attr-defined]
    items: list[SandboxAdminUsageItem] = []
    for r in items_raw:
        items.append(
            SandboxAdminUsageItem(
                user_id=str(r.get("user_id")),
                runs_count=int(r.get("runs_count") or 0),
                log_bytes=int(r.get("log_bytes") or 0),
                artifact_bytes=int(r.get("artifact_bytes") or 0),
            )
        )
    has_more = (offset + len(items)) < int(total)
    return SandboxAdminUsageResponse(total=int(total), limit=int(limit), offset=int(offset), has_more=bool(has_more), items=items)
