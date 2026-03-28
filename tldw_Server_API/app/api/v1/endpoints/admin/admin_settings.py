from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, ConfigDict, Field

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminCleanupSettingsResponse,
    AdminCleanupSettingsUpdate,
    NotesTitleSettingsResponse,
    NotesTitleSettingsUpdate,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_settings_service

router = APIRouter()


@router.get("/cleanup-settings", response_model=AdminCleanupSettingsResponse)
async def get_cleanup_settings() -> AdminCleanupSettingsResponse:
    return await admin_settings_service.get_cleanup_settings()


@router.post("/cleanup-settings", response_model=AdminCleanupSettingsResponse)
async def set_cleanup_settings(payload: AdminCleanupSettingsUpdate) -> AdminCleanupSettingsResponse:
    return await admin_settings_service.set_cleanup_settings(payload)


@router.get("/notes/title-settings", response_model=NotesTitleSettingsResponse)
async def get_notes_title_settings() -> NotesTitleSettingsResponse:
    return await admin_settings_service.get_notes_title_settings()


@router.post("/notes/title-settings", response_model=NotesTitleSettingsResponse)
async def set_notes_title_settings(payload: NotesTitleSettingsUpdate) -> NotesTitleSettingsResponse:
    return await admin_settings_service.set_notes_title_settings(payload)


class RiskWeightsResponse(BaseModel):
    weights: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)


class RiskWeightsUpdateRequest(BaseModel):
    weights: dict[str, Any]


@router.get("/security/risk-weights", response_model=RiskWeightsResponse)
async def get_security_risk_weights(
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> RiskWeightsResponse:
    """Get the security risk score weights configuration."""
    result = await admin_settings_service.get_risk_weights()
    return RiskWeightsResponse(weights=result)


@router.post("/security/risk-weights", response_model=RiskWeightsResponse)
async def set_security_risk_weights(
    payload: RiskWeightsUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> RiskWeightsResponse:
    """Update the security risk score weights configuration."""
    result = await admin_settings_service.set_risk_weights(payload.weights)
    return RiskWeightsResponse(weights=result)
