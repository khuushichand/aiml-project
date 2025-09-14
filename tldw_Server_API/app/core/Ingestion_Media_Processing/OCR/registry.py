from __future__ import annotations

from typing import Dict, Optional, Type

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.base import OCRBackend
from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.tesseract_cli import (
    TesseractCLIBackend,
)

_BACKENDS: Dict[str, Type[OCRBackend]] = {
    TesseractCLIBackend.name: TesseractCLIBackend,
}


def get_backend(name: Optional[str] = None) -> Optional[OCRBackend]:
    """
    Resolve an OCR backend instance by name or choose the first available.

    name = None     -> auto-detect first available backend
    name = "auto"   -> same as None
    name = "tesseract" -> Tesseract CLI backend, if available
    """
    candidates = []
    if name and name != "auto":
        cls = _BACKENDS.get(name)
        if cls and cls.available():
            return cls()
        return None

    # auto: prefer tesseract if available (can extend with priority)
    for cls in _BACKENDS.values():
        if cls.available():
            candidates.append(cls)
    if not candidates:
        return None
    return candidates[0]()

