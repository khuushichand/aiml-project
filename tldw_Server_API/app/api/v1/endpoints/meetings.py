from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from tldw_Server_API.app.api.v1.API_Deps.Meetings_DB_Deps import get_meetings_db_for_user
from tldw_Server_API.app.api.v1.schemas.meetings_schemas import (
    MeetingArtifactCreate,
    MeetingArtifactResponse,
    MeetingHealthResponse,
    MeetingSessionCreate,
    MeetingSessionResponse,
    MeetingSessionStatus,
    MeetingSessionStatusUpdate,
    MeetingTemplateCreate,
    MeetingTemplateResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase
from tldw_Server_API.app.core.Meetings.artifact_service import MeetingArtifactService
from tldw_Server_API.app.core.Meetings.session_service import MeetingSessionService
from tldw_Server_API.app.core.Meetings.template_service import MeetingTemplateService

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("/health", response_model=MeetingHealthResponse, openapi_extra={"security": []})
async def meetings_health() -> MeetingHealthResponse:
    return MeetingHealthResponse()


def _to_session_response(row: dict[str, Any]) -> MeetingSessionResponse:
    return MeetingSessionResponse(
        id=str(row.get("id") or ""),
        title=str(row.get("title") or ""),
        meeting_type=str(row.get("meeting_type") or ""),
        status=row.get("status") or "scheduled",
        source_type=row.get("source_type") or "upload",
        language=row.get("language"),
        template_id=row.get("template_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _to_template_response(row: dict[str, Any]) -> MeetingTemplateResponse:
    return MeetingTemplateResponse(
        id=str(row.get("id") or ""),
        name=str(row.get("name") or ""),
        scope=row.get("scope") or "personal",
        enabled=bool(row.get("enabled")),
        is_default=bool(row.get("is_default")),
        version=int(row.get("version") or 1),
        schema_json=row.get("schema_json") or {},
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _to_artifact_response(row: dict[str, Any]) -> MeetingArtifactResponse:
    return MeetingArtifactResponse(
        id=str(row.get("id") or ""),
        session_id=str(row.get("session_id") or ""),
        kind=row.get("kind") or "summary",
        format=str(row.get("format") or "json"),
        payload_json=row.get("payload_json") or {},
        version=int(row.get("version") or 1),
        created_at=row.get("created_at"),
    )


@router.post("/sessions", response_model=MeetingSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: MeetingSessionCreate,
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
) -> MeetingSessionResponse:
    service = MeetingSessionService(db=meetings_db)
    row = service.create_session(
        title=payload.title,
        meeting_type=payload.meeting_type,
        source_type=payload.source_type,
        language=payload.language,
        template_id=payload.template_id,
        metadata=payload.metadata,
    )
    return _to_session_response(row)


@router.get("/sessions", response_model=list[MeetingSessionResponse])
async def list_sessions(
    status_filter: MeetingSessionStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
) -> list[MeetingSessionResponse]:
    service = MeetingSessionService(db=meetings_db)
    rows = service.list_sessions(status=status_filter, limit=limit, offset=offset)
    return [_to_session_response(row) for row in rows]


@router.get("/sessions/{session_id}", response_model=MeetingSessionResponse)
async def get_session(
    session_id: str,
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
) -> MeetingSessionResponse:
    service = MeetingSessionService(db=meetings_db)
    try:
        row = service.get_session(session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting session not found") from exc
    return _to_session_response(row)


@router.post("/sessions/{session_id}/status", response_model=MeetingSessionResponse)
async def transition_session_status(
    session_id: str,
    payload: MeetingSessionStatusUpdate,
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
) -> MeetingSessionResponse:
    service = MeetingSessionService(db=meetings_db)
    try:
        row = service.transition(session_id=session_id, to_status=payload.status)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_session_response(row)


@router.post("/templates", response_model=MeetingTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: MeetingTemplateCreate,
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
    current_user: User = Depends(get_request_user),
) -> MeetingTemplateResponse:
    if payload.scope == "builtin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Builtin templates are immutable",
        )
    if payload.scope in {"org", "team"} and not (
        bool(current_user.is_admin) or "team_lead" in set(current_user.roles or [])
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges for requested template scope",
        )
    service = MeetingTemplateService(db=meetings_db)
    try:
        row = service.create_template(
            name=payload.name,
            scope=payload.scope,
            schema_json=payload.schema_json,
            enabled=payload.enabled,
            is_default=payload.is_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_template_response(row)


@router.get("/templates", response_model=list[MeetingTemplateResponse])
async def list_templates(
    scope: str | None = Query(default=None),
    include_disabled: bool = Query(default=False),
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
) -> list[MeetingTemplateResponse]:
    service = MeetingTemplateService(db=meetings_db)
    rows = service.list_templates(scope=scope, include_disabled=include_disabled)
    return [_to_template_response(row) for row in rows]


@router.get("/templates/{template_id}", response_model=MeetingTemplateResponse)
async def get_template(
    template_id: str,
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
) -> MeetingTemplateResponse:
    service = MeetingTemplateService(db=meetings_db)
    try:
        row = service.get_template(template_id=template_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting template not found") from exc
    return _to_template_response(row)


@router.post(
    "/sessions/{session_id}/artifacts",
    response_model=MeetingArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_artifact(
    session_id: str,
    payload: MeetingArtifactCreate,
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
) -> MeetingArtifactResponse:
    service = MeetingArtifactService(db=meetings_db)
    try:
        row = service.create_artifact(
            session_id=session_id,
            kind=payload.kind,
            format=payload.format,
            payload_json=payload.payload_json,
            version=payload.version,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_artifact_response(row)


@router.get("/sessions/{session_id}/artifacts", response_model=list[MeetingArtifactResponse])
async def list_artifacts(
    session_id: str,
    meetings_db: MeetingsDatabase = Depends(get_meetings_db_for_user),
) -> list[MeetingArtifactResponse]:
    service = MeetingArtifactService(db=meetings_db)
    rows = service.list_artifacts(session_id=session_id)
    return [_to_artifact_response(row) for row in rows]
