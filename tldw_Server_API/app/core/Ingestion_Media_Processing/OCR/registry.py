from __future__ import annotations

from typing import Dict, Optional, Type, List

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.base import OCRBackend
from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.tesseract_cli import (
    TesseractCLIBackend,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.dots_ocr import (
    DotsOCRBackend,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.points_reader import (
    PointsReaderBackend,
)
try:
    # Optional config override
    from tldw_Server_API.app.core.config import loaded_config_data as _loaded_cfg
except Exception:
    _loaded_cfg = None

_BACKENDS: Dict[str, Type[OCRBackend]] = {
    # Auto-detection priority is the dictionary order below
    # Keep Tesseract first for a lightweight default, but users can force 'dots'
    TesseractCLIBackend.name: TesseractCLIBackend,
    DotsOCRBackend.name: DotsOCRBackend,
    PointsReaderBackend.name: PointsReaderBackend,
}


def _resolve_priority_from_config() -> Optional[List[str]]:
    try:
        if not _loaded_cfg:
            return None
        ocr_cfg = _loaded_cfg.get("OCR") or {}
        pr = ocr_cfg.get("backend_priority")
        if not pr:
            return None
        if isinstance(pr, str):
            # comma-separated list
            return [s.strip() for s in pr.split(",") if s.strip()]
        if isinstance(pr, list):
            return [str(s).strip() for s in pr if str(s).strip()]
        return None
    except Exception:
        return None


def get_backend(name: Optional[str] = None) -> Optional[OCRBackend]:
    """
    Resolve an OCR backend instance by name or choose the first available.

    name = None         -> auto-detect first available backend
    name = "auto"       -> same as None
    name = "tesseract"  -> Tesseract CLI backend, if available
    name = "dots"       -> dots.ocr CLI backend, if available
    name = "points"     -> POINTS-Reader backend, if available
    """
    candidates = []
    if name and name not in ("auto", "auto_high_quality"):
        cls = _BACKENDS.get(name)
        if cls and cls.available():
            return cls()
        return None

    # Auto resolution
    preferred_order: Optional[List[str]] = None
    if name == "auto_high_quality":
        preferred_order = ["points", "dots", "tesseract"]
    else:
        # Try config override for normal auto
        preferred_order = _resolve_priority_from_config()

    if preferred_order:
        for key in preferred_order:
            cls = _BACKENDS.get(key)
            if cls and cls.available():
                return cls()
        # fallback to discovery order below

    # Default: first available in registration order
    for cls in _BACKENDS.values():
        if cls.available():
            candidates.append(cls)
    if not candidates:
        return None
    return candidates[0]()


def list_backends() -> Dict[str, Dict[str, bool]]:
    """Return a simple availability map for known backends."""
    out: Dict[str, Dict[str, bool]] = {}
    for k, cls in _BACKENDS.items():
        ok = False
        try:
            ok = bool(cls.available())
        except Exception:
            ok = False
        out[k] = {"available": ok}
    return out
