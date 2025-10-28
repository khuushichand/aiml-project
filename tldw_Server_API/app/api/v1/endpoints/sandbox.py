from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Header, File, UploadFile, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
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
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Sandbox.models import RunSpec, SessionSpec, RuntimeType as CoreRuntimeType
from tldw_Server_API.app.core.Sandbox.service import SandboxService
from tldw_Server_API.app.core.Sandbox.streams import get_hub
from tldw_Server_API.app.core.Metrics import increment_counter, observe_histogram
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.core.Audit.unified_audit_service import AuditEventType, AuditEventCategory, AuditSeverity, AuditContext


router = APIRouter(prefix="/sandbox", tags=["sandbox"])

_service = SandboxService()


@router.get("/runtimes", response_model=SandboxRuntimesResponse, summary="Discover available runtimes")
async def get_runtimes(current_user: User = Depends(get_request_user)) -> SandboxRuntimesResponse:
    info = _service.feature_discovery()
    return SandboxRuntimesResponse(runtimes=info)  # type: ignore[arg-type]


@router.post("/sessions", response_model=SandboxSession, summary="Create a short-lived sandbox session")
async def create_session(
    payload: SandboxSessionCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    request: Request = None,
    audit_service=Depends(get_audit_service_for_user),
) -> SandboxSession:
    spec = SessionSpec(
        runtime=CoreRuntimeType(payload.runtime) if payload.runtime else None,
        base_image=payload.base_image,
        cpu_limit=payload.cpu_limit,
        memory_mb=payload.memory_mb,
        timeout_sec=payload.timeout_sec or 300,
        network_policy=payload.network_policy or "deny_all",
        env=payload.env or {},
        labels=payload.labels or {},
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
        from tldw_Server_API.app.core.Sandbox.orchestrator import IdempotencyConflict
        if isinstance(e, IdempotencyConflict):
            raise HTTPException(status_code=409, detail={
                "error": {
                    "code": "idempotency_conflict",
                    "message": str(e),
                    "details": {"original_id": e.original_id}
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

    return SandboxSession(id=session.id, runtime=session.runtime.value, base_image=session.base_image, expires_at=session.expires_at)


@router.delete("/sessions/{session_id}", summary="Destroy a sandbox session early")
async def delete_session(
    session_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> dict:
    ok = _service.destroy_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session_not_found")
    return {"ok": True}


@router.post("/sessions/{session_id}/files", response_model=SandboxFileUploadResponse, summary="Upload files to a session workspace")
async def upload_files(
    session_id: str = Path(..., min_length=1),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_request_user),
    request: Request = None,
    audit_service=Depends(get_audit_service_for_user),
) -> SandboxFileUploadResponse:
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

    def _safe_join(base: str, name: str) -> str:
        name = name.replace("\\", "/").lstrip("/")
        while ".." in name.split("/"):
            name = name.replace("..", "_")
        return os.path.join(base, name)

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
                    if m.isdev() or m.issym() or m.islnk():
                        continue
                    target = _safe_join(ws_root, m.name)
                    if not target.startswith(ws_root):
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
                    name = m.filename
                    target = _safe_join(ws_root, name)
                    if not target.startswith(ws_root):
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
            target = _safe_join(ws_root, up.filename or f"file_{count}")
            if not target.startswith(ws_root):
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
    payload: SandboxRunCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    request: Request = None,
    audit_service=Depends(get_audit_service_for_user),
) -> SandboxRunStatus:
    files_inline = _service.parse_inline_files([f.dict() for f in (payload.files or [])])
    spec = RunSpec(
        session_id=payload.session_id,
        runtime=(CoreRuntimeType(payload.runtime) if payload.runtime else None),
        base_image=payload.base_image,
        command=list(payload.command),
        env=payload.env or {},
        timeout_sec=payload.timeout_sec or 300,
        cpu=(payload.resources.cpu if payload.resources else None) if hasattr(payload, "resources") and payload.resources else None,
        memory_mb=(payload.resources.memory_mb if payload.resources else None) if hasattr(payload, "resources") and payload.resources else None,
        network_policy=payload.network_policy,
        files_inline=files_inline,
        capture_patterns=payload.capture_patterns or [],
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
        from tldw_Server_API.app.core.Sandbox.orchestrator import IdempotencyConflict
        if isinstance(e, IdempotencyConflict):
            raise HTTPException(status_code=409, detail={
                "error": {
                    "code": "idempotency_conflict",
                    "message": str(e),
                    "details": {"original_id": e.original_id}
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
            # Metrics: completion + duration
            try:
                increment_counter(
                    "sandbox_runs_completed_total",
                    labels={"runtime": str(status.runtime.value if status.runtime else (payload.runtime or "unknown")), "outcome": outcome},
                )
            except Exception:
                logger.debug("metrics: sandbox_runs_completed_total failed")
            try:
                observe_histogram(
                    "sandbox_run_duration_seconds",
                    value=float(duration),
                    labels={"runtime": str(status.runtime.value if status.runtime else (payload.runtime or "unknown")), "outcome": outcome},
                )
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

    return SandboxRunStatus(
        id=status.id,
        spec_version=payload.spec_version,
        runtime=status.runtime.value if status.runtime else None,
        base_image=status.base_image,
        image_digest=status.image_digest,
        policy_hash=status.policy_hash,
        phase=status.phase.value,
        exit_code=status.exit_code,
        started_at=status.started_at,
        finished_at=status.finished_at,
        message=status.message,
        resource_usage=status.resource_usage,
    )


@router.get("/runs/{run_id}", response_model=SandboxRunStatus, summary="Get run status")
async def get_run_status(
    run_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> SandboxRunStatus:
    st = _service.get_run(run_id)
    if not st:
        raise HTTPException(status_code=404, detail="run_not_found")
    return SandboxRunStatus(
        id=st.id,
        spec_version=st.spec_version,
        runtime=st.runtime.value if st.runtime else None,
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


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactListResponse, summary="List captured artifacts")
async def list_artifacts(
    run_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> ArtifactListResponse:
    sizes = _service._orch.list_artifacts(run_id)  # type: ignore[attr-defined]
    items = []
    for p, sz in sizes.items():
        items.append({
            "path": p,
            "size": sz,
            "download_url": f"/api/v1/sandbox/runs/{run_id}/artifacts/{p}"
        })
    return ArtifactListResponse(items=items)


@router.get("/runs/{run_id}/artifacts/{path:path}", summary="Download an artifact")
async def download_artifact(
    run_id: str = Path(..., min_length=1),
    path: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
):
    data = _service._orch.get_artifact(run_id, path)  # type: ignore[attr-defined]
    if data is None:
        raise HTTPException(status_code=404, detail="artifact_not_found")
    async def _iter():
        yield data
    return StreamingResponse(_iter(), media_type="application/octet-stream")


@router.post("/runs/{run_id}/cancel", response_model=CancelResponse, summary="Cancel a running sandbox job")
async def cancel_run(
    run_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> CancelResponse:
    # Scaffold does not track runs; return as already-cancelled false
    return CancelResponse(id=run_id, cancelled=False, message="Sandbox scaffold has no active runs")


@router.websocket("/runs/{run_id}/stream")
async def stream_run_logs(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    hub = get_hub()
    hub.set_loop(asyncio.get_running_loop())
    q = hub.subscribe(run_id)
    hub.drain_buffer(run_id, q)

    async def _heartbeats() -> None:
        try:
            while True:
                await asyncio.sleep(10)
                await websocket.send_json({"type": "heartbeat"})
        except Exception:
            return

    hb_task = asyncio.create_task(_heartbeats())
    try:
        while True:
            try:
                frame = await asyncio.wait_for(q.get(), timeout=30)
            except asyncio.TimeoutError:
                continue
            await websocket.send_json(frame)
            if isinstance(frame, dict) and frame.get("type") == "event" and frame.get("event") == "end":
                break
    except WebSocketDisconnect:
        logger.info(f"WS disconnected for run {run_id}")
    except Exception as e:
        logger.debug(f"WS stream error: {e}")
    finally:
        try:
            hb_task.cancel()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
