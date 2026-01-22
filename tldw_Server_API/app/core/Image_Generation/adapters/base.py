"""Base contracts for image generation adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass(frozen=True)
class ImageGenRequest:
    backend: str
    prompt: str
    negative_prompt: Optional[str]
    width: Optional[int]
    height: Optional[int]
    steps: Optional[int]
    cfg_scale: Optional[float]
    seed: Optional[int]
    sampler: Optional[str]
    model: Optional[str]
    format: str
    extra_params: Dict[str, Any]
    request_id: Optional[str] = None


@dataclass(frozen=True)
class ImageGenResult:
    content: bytes
    content_type: str
    bytes_len: int


class ImageGenerationAdapter(Protocol):
    """Protocol for image generation backends."""

    name: str
    supported_formats: set[str]

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        """Generate an image from the given request."""
        ...
