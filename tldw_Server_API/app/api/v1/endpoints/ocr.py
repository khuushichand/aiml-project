from __future__ import annotations

from fastapi import APIRouter
from typing import Dict, Any

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.registry import (
    list_backends as _list_backends,
)


router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.get("/backends")
def list_ocr_backends() -> Dict[str, Any]:
    """List available OCR backends with lightweight health information."""
    out = _list_backends()

    # Enrich with backend-specific details without heavy loading
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.points_reader import (
            PointsReaderBackend,
        )
        out.setdefault("points", {})
        out["points"]["mode"] = PointsReaderBackend().describe().get("mode")
        # If SGLang configured, attempt a quick availability check
        url = PointsReaderBackend().describe().get("url")
        if url:
            try:
                import requests

                r = requests.get(url.rsplit("/v1", 1)[0] + "/v1/models", timeout=1.5)
                out["points"]["sglang_reachable"] = r.status_code in (200, 401)
            except Exception:
                out["points"]["sglang_reachable"] = False
    except Exception:
        pass

    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.dots_ocr import (
            DotsOCRBackend,
        )
        out.setdefault("dots", {}).update({"prompt": DotsOCRBackend().describe().get("prompt")})
    except Exception:
        pass

    return out

