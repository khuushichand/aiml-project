"""Setup endpoints for the first-time configuration flow."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from tldw_Server_API.app.core.Setup import setup_manager

router = APIRouter(prefix="/setup", tags=["setup"], include_in_schema=True)


class ConfigUpdates(BaseModel):
    updates: Dict[str, Dict[str, Any]] = Field(
        ..., description="Mapping of section -> key/value pairs to persist in config.txt"
    )


class SetupCompleteRequest(BaseModel):
    disable_first_time_setup: Optional[bool] = Field(
        False,
        description="If true, flips enable_first_time_setup to false so the screen stays hidden",
    )


class AssistantQuestion(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language question for the setup assistant")


@router.get("/status", openapi_extra={"security": []})
async def get_setup_status() -> Dict[str, Any]:
    """Return setup availability and placeholder diagnostics."""
    return setup_manager.get_status_snapshot()


@router.get("/config", openapi_extra={"security": []})
async def get_setup_config() -> Dict[str, Any]:
    """Return the current configuration grouped by section for the setup UI."""
    status_snapshot = setup_manager.get_status_snapshot()
    if not status_snapshot["enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setup flow not enabled in config.txt")

    if not status_snapshot["needs_setup"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Setup already completed. Toggle enable_first_time_setup to revisit the wizard.",
        )

    return setup_manager.get_config_snapshot()


@router.post("/config", openapi_extra={"security": []})
async def update_setup_config(payload: ConfigUpdates) -> Dict[str, Any]:
    """Persist configuration updates coming from the setup UI."""
    status_snapshot = setup_manager.get_status_snapshot()
    if not status_snapshot["enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setup flow not enabled in config.txt")

    if not status_snapshot["needs_setup"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Setup already completed. Toggle enable_first_time_setup to make changes here.",
        )

    try:
        backup_path = setup_manager.update_config(payload.updates)
        return {
            "success": True,
            "backup_path": str(backup_path) if backup_path else None,
            "requires_restart": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to write configuration via setup endpoint")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/complete", openapi_extra={"security": []})
async def mark_setup_complete(payload: SetupCompleteRequest) -> Dict[str, Any]:
    """Mark the setup workflow as complete and optionally disable future prompts."""
    status_snapshot = setup_manager.get_status_snapshot()
    if not status_snapshot["enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setup flow not enabled in config.txt")

    if not status_snapshot["needs_setup"]:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Setup already marked as complete")

    setup_manager.mark_setup_completed(True)

    if payload.disable_first_time_setup:
        setup_manager.update_config({setup_manager.SETUP_SECTION: {"enable_first_time_setup": False}}, create_backup=False)

    return {
        "success": True,
        "message": "Setup marked as complete. Restart the server to load new configuration.",
        "requires_restart": True,
    }


@router.post("/assistant", openapi_extra={"security": []})
async def ask_setup_assistant(payload: AssistantQuestion) -> Dict[str, Any]:
    """Provide contextual help for setup questions using local configuration knowledge."""
    try:
        return setup_manager.answer_setup_question(payload.question)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
