"""Subtitle processing adapters.

This module includes adapters for subtitle operations:
- subtitle_generate: Generate subtitles from audio
- subtitle_translate: Translate subtitles
- subtitle_burn: Burn subtitles into video
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.video._config import (
    SubtitleGenerateConfig,
    SubtitleTranslateConfig,
    SubtitleBurnConfig,
)


@registry.register(
    "subtitle_generate",
    category="video",
    description="Generate subtitles from audio",
    parallelizable=False,
    config_model=SubtitleGenerateConfig,
    tags=["video", "subtitles"],
)
async def run_subtitle_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate subtitles from audio/video using speech-to-text.

    Config:
      - input_path: str (templated) - Input audio/video file path
      - output_path: str (optional) - Output subtitle file path
      - format: Literal["srt", "vtt", "ass"] = "srt" - Subtitle format
      - language: str (optional) - Source language code
      - model: str = "large-v3" - Whisper model name
    Output:
      - {"output_path": str, "format": str, "segments": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_subtitle_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "subtitle_translate",
    category="video",
    description="Translate subtitles",
    parallelizable=True,
    config_model=SubtitleTranslateConfig,
    tags=["video", "subtitles"],
)
async def run_subtitle_translate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Translate subtitles to a different language.

    Config:
      - input_path: str (templated) - Input subtitle file path
      - output_path: str (optional) - Output subtitle file path
      - source_lang: str (optional) - Source language code
      - target_lang: str - Target language code (required)
      - provider: str (optional) - Translation provider
      - model: str (optional) - Model for LLM translation
    Output:
      - {"output_path": str, "source_lang": str, "target_lang": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_subtitle_translate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "subtitle_burn",
    category="video",
    description="Burn subtitles into video",
    parallelizable=False,
    config_model=SubtitleBurnConfig,
    tags=["video", "subtitles"],
)
async def run_subtitle_burn_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Burn (hardcode) subtitles into a video file.

    Config:
      - video_path: str (templated) - Input video file path
      - subtitle_path: str (templated) - Input subtitle file path
      - output_path: str (optional) - Output video file path
      - font_size: int = 24 - Subtitle font size
      - font_color: str = "white" - Subtitle font color
      - position: Literal["bottom", "top"] = "bottom" - Subtitle position
    Output:
      - {"output_path": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_subtitle_burn_adapter as _legacy
    return await _legacy(config, context)
