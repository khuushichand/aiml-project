from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from tldw_Server_API.app.core.Ingestion_Media_Processing.transcription_models import (  # type: ignore
    get_transcription_models_payload,
)

router = APIRouter(tags=["Media Processing"])


@router.get(
    "/transcription-models",
    status_code=status.HTTP_200_OK,
    summary="Get Available Transcription Models",
    response_model=dict[str, Any],
)
async def get_transcription_models() -> dict[str, Any]:
    """
    Modular transcription models endpoint backed by core helper.
    """
    return get_transcription_models_payload()


__all__ = ["router"]
