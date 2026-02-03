from __future__ import annotations

from fastapi import APIRouter

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminCleanupSettingsResponse,
    AdminCleanupSettingsUpdate,
    NotesTitleSettingsResponse,
    NotesTitleSettingsUpdate,
)
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
