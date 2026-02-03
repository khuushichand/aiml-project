from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from loguru import logger

from tldw_Server_API.app.services.personalization_consolidation import get_consolidation_service


async def trigger_consolidation(user_id: str | None) -> dict[str, Any]:
    """Trigger personalization consolidation for a given user."""
    try:
        svc = get_consolidation_service()
        ok = await svc.trigger_consolidation(user_id=user_id)
        return {"status": "ok" if ok else "error", "user_id": user_id}
    except Exception as exc:
        logger.warning(f"Admin consolidate trigger failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to trigger consolidation") from exc


async def get_status() -> dict[str, Any]:
    """Return in-memory consolidation status (last tick per user)."""
    try:
        svc = get_consolidation_service()
        status_fn = getattr(svc, "get_status", None)
        if not callable(status_fn):
            raise TypeError(
                "Personalization service get_status is not callable: "
                f"{status_fn!r} (type={type(status_fn).__name__})"
            )
        return status_fn()
    except Exception as exc:
        logger.warning(f"Admin status fetch failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch status") from exc
