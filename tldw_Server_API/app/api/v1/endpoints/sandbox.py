from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path
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
from fastapi import WebSocket, WebSocketDisconnect


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
    session = _service.create_session(spec)
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
    current_user: User = Depends(get_request_user),
) -> SandboxFileUploadResponse:
    # File ingestion is not implemented in scaffold; return a placeholder
    logger.info(f"Upload files called for session {session_id} (scaffold: no-op)")
    return SandboxFileUploadResponse(session_id=session_id, bytes_received=0, file_count=0)


@router.post("/runs", response_model=SandboxRunStatus, summary="Start a sandbox run (one-shot or for a session)")
async def start_run(
    payload: SandboxRunCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
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
    status = _service.start_run_scaffold(spec)
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
    # Scaffold does not track runs; return not found
    raise HTTPException(status_code=404, detail="run_not_found")


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactListResponse, summary="List captured artifacts")
async def list_artifacts(
    run_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> ArtifactListResponse:
    # Scaffold has no artifacts
    return ArtifactListResponse(items=[])


@router.post("/runs/{run_id}/cancel", response_model=CancelResponse, summary="Cancel a running sandbox job")
async def cancel_run(
    run_id: str = Path(..., min_length=1),
    current_user: User = Depends(get_request_user),
) -> CancelResponse:
    # Scaffold does not track runs; return as already-cancelled false
    return CancelResponse(id=run_id, cancelled=False, message="Sandbox scaffold has no active runs")


@router.websocket("/runs/{run_id}/stream")
async def stream_run_logs(websocket: WebSocket, run_id: str) -> None:
    """WebSocket endpoint stub for run log streaming.

    Accepts the connection, emits a heartbeat and a terminal end event, then closes.
    Real implementation will attach to runner log streams.
    """
    await websocket.accept()
    try:
        await websocket.send_json({"type": "heartbeat"})
        await websocket.send_json({"type": "event", "event": "end", "data": {"exit_code": 0}})
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from sandbox run stream: {run_id}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
