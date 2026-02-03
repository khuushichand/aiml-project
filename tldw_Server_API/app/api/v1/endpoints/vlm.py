from __future__ import annotations

from typing import Any

from fastapi import APIRouter

try:
    from tldw_Server_API.app.core.Ingestion_Media_Processing.VLM.registry import (
        list_backends as _list_backends,
    )
except Exception:  # pragma: no cover - optional module
    def _list_backends() -> dict[str, Any]:  # type: ignore
        return {}


router = APIRouter(prefix="/vlm", tags=["vlm"])


@router.get("/backends")
def list_vlm_backends() -> dict[str, Any]:
    """List available VLM backends with lightweight health information."""
    out = _list_backends()
    return out
