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
                from tldw_Server_API.app.core.http_client import create_client as _create_client
                with _create_client(timeout=1.5) as _c:
                    r = _c.get(url.rsplit("/v1", 1)[0] + "/v1/models")
                    out["points"]["sglang_reachable"] = r.status_code in (200, 401)
            except Exception:
                out["points"]["sglang_reachable"] = False
    except Exception:
        pass

    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.dots_ocr import (
            DotsOCRBackend,
        )
        dots_desc = DotsOCRBackend().describe()
        out.setdefault("dots", {}).update({"prompt": dots_desc.get("prompt")})
        vllm = dots_desc.get("vllm_url")
        if vllm:
            try:
                from tldw_Server_API.app.core.http_client import create_client as _create_client
                with _create_client(timeout=1.5) as _c:
                    r = _c.get(vllm.rsplit("/v1", 1)[0] + "/v1/models")
                    out["dots"]["vllm_reachable"] = r.status_code in (200, 401)
            except Exception:
                out["dots"]["vllm_reachable"] = False
    except Exception:
        pass

    return out


@router.post("/points/preload")
def preload_points_transformers() -> Dict[str, Any]:
    """Preload POINTS transformers model to surface errors early."""
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.points_reader import (
            _load_transformers,
        )
        _load_transformers()
        return {"status": "ok", "mode": "transformers"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
