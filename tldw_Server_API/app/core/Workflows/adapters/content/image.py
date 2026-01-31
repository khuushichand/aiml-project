"""Image generation and description adapters.

This module includes adapters for image operations:
- image_gen: Generate images
- image_describe: Describe images
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.content._config import (
    ImageGenConfig,
    ImageDescribeConfig,
)


@registry.register(
    "image_gen",
    category="content",
    description="Generate images",
    parallelizable=True,
    tags=["content", "image"],
    config_model=ImageGenConfig,
)
async def run_image_gen_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate images using AI image generation services.

    Config:
      - prompt: str (templated) - Image description prompt
      - provider: str = "openai" - Image generation provider
      - model: str (optional) - Model to use (e.g., "dall-e-3")
      - size: str = "1024x1024" - Image size
      - quality: Literal["standard", "hd"] = "standard"
      - style: Literal["natural", "vivid"] = "natural"
      - n: int = 1 - Number of images to generate
    Output:
      - {"images": [{"url": str, "path": str}], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_image_gen_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "image_describe",
    category="content",
    description="Describe images",
    parallelizable=True,
    tags=["content", "image"],
    config_model=ImageDescribeConfig,
)
async def run_image_describe_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Describe image content using vision models.

    Config:
      - image_uri: str (templated) - file:// path or URL to image
      - provider: str - Vision model provider
      - model: str (optional) - Model to use
      - prompt: str (optional) - Custom description prompt
      - detail: Literal["low", "high", "auto"] = "auto"
    Output:
      - {"description": str, "tags": [str]}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_image_describe_adapter as _legacy
    return await _legacy(config, context)
