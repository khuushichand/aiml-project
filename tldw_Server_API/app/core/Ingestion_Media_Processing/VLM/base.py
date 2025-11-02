from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class VLMDetection:
    """
    A single detection output by a VLM backend.

    Attributes:
        label: Semantic label (e.g., "table", "figure", "chart").
        score: Confidence score (0-1).
        bbox: Bounding box in pixel coordinates [x0, y0, x1, y1].
        metadata: Backend-specific metadata (e.g., page number, extra scores).
    """
    label: str
    score: float
    bbox: List[float]
    metadata: Dict[str, Any]


@dataclass
class VLMResult:
    """Structured result containing detections and any optional text summaries."""
    detections: List[VLMDetection]
    # Optional textual outputs (e.g., captions) - empty for detectors-only backends
    texts: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None


class VLMBackend(ABC):
    """
    Base interface for VLM backends used by ingestion.

    Backends should be lightweight to construct; heavy models should load lazily on first use.
    """

    name: str = "base"

    @classmethod
    def available(cls) -> bool:
        """Return True if the backend can run in the current environment."""
        return True

    def describe(self) -> Dict[str, Any]:
        """Lightweight descriptor for endpoint health checks and listing."""
        return {"name": getattr(self, "name", self.__class__.__name__)}

    @abstractmethod
    def process_image(
        self,
        image_bytes: bytes,
        *,
        mime_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VLMResult:
        """
        Process image bytes and return detections/captions.

        Args:
            image_bytes: Encoded image bytes (e.g., PNG/JPEG)
            mime_type: Optional MIME type
            context: Optional context (e.g., page number)
        """
        raise NotImplementedError
