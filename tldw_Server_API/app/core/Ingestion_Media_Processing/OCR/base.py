from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class OCRBackend(ABC):
    """
    Abstract OCR backend interface.

    Implementations should support OCR on raw image bytes.
    PDF page handling is performed by the ingestion code (which renders pages to images).
    """

    name: str = "abstract"

    @classmethod
    @abstractmethod
    def available(cls) -> bool:
        """Return True if this backend is usable on this system (e.g. binary/library available)."""
        raise NotImplementedError

    @abstractmethod
    def ocr_image(self, image_bytes: bytes, lang: Optional[str] = None) -> str:
        """Run OCR on an image (bytes) and return extracted text (UTF-8)."""
        raise NotImplementedError
