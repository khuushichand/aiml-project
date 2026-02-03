from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminCleanupSettingsUpdate,
    NotesTitleSettingsUpdate,
)
from tldw_Server_API.app.services import admin_settings_service

router = APIRouter()


@router.get("/cleanup-settings")
async def get_cleanup_settings() -> dict[str, Any]:
    return await admin_settings_service.get_cleanup_settings()


@router.post("/cleanup-settings")
async def set_cleanup_settings(payload: AdminCleanupSettingsUpdate) -> dict[str, Any]:
    return await admin_settings_service.set_cleanup_settings(payload)


@router.get("/notes/title-settings")
async def get_notes_title_settings() -> dict[str, Any]:
    return await admin_settings_service.get_notes_title_settings()


@router.post("/notes/title-settings")
async def set_notes_title_settings(payload: NotesTitleSettingsUpdate) -> dict[str, Any]:
    return await admin_settings_service.set_notes_title_settings(payload)
