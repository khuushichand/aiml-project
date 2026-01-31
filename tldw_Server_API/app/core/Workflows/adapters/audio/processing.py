"""Audio processing adapters.

This module includes adapters for audio processing operations:
- audio_normalize: Normalize audio levels
- audio_concat: Concatenate audio files
- audio_trim: Trim audio files
- audio_convert: Convert audio format
- audio_extract: Extract audio from video
- audio_mix: Mix multiple audio tracks
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.audio._config import (
    AudioNormalizeConfig,
    AudioConcatConfig,
    AudioTrimConfig,
    AudioConvertConfig,
    AudioExtractConfig,
    AudioMixConfig,
)


@registry.register(
    "audio_normalize",
    category="audio",
    description="Normalize audio levels",
    parallelizable=True,
    config_model=AudioNormalizeConfig,
    tags=["audio"],
)
async def run_audio_normalize_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize audio volume levels using ffmpeg.

    Config:
      - input_path: str (templated) - Input audio file path
      - output_path: str (optional) - Output file path (auto-generated if not provided)
      - target_loudness: float = -23 - Target loudness in LUFS
    Output:
      - {"output_path": str, "normalized": bool}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_audio_normalize_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "audio_concat",
    category="audio",
    description="Concatenate audio files",
    parallelizable=True,
    config_model=AudioConcatConfig,
    tags=["audio"],
)
async def run_audio_concat_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Concatenate multiple audio files into one.

    Config:
      - input_paths: list[str] (templated) - List of input audio file paths
      - output_path: str (optional) - Output file path
      - format: str = "mp3" - Output format
    Output:
      - {"output_path": str, "duration": float}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_audio_concat_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "audio_trim",
    category="audio",
    description="Trim audio files",
    parallelizable=True,
    config_model=AudioTrimConfig,
    tags=["audio"],
)
async def run_audio_trim_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Trim an audio file to a specific time range.

    Config:
      - input_path: str (templated) - Input audio file path
      - output_path: str (optional) - Output file path
      - start_time: float = 0 - Start time in seconds
      - end_time: float (optional) - End time in seconds
      - duration: float (optional) - Duration in seconds (alternative to end_time)
    Output:
      - {"output_path": str, "duration": float}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_audio_trim_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "audio_convert",
    category="audio",
    description="Convert audio format",
    parallelizable=True,
    config_model=AudioConvertConfig,
    tags=["audio"],
)
async def run_audio_convert_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert audio file to a different format.

    Config:
      - input_path: str (templated) - Input audio file path
      - output_path: str (optional) - Output file path
      - format: str = "mp3" - Target format (mp3, wav, flac, ogg, etc.)
      - bitrate: str (optional) - Audio bitrate (e.g., "192k")
      - sample_rate: int (optional) - Sample rate in Hz
    Output:
      - {"output_path": str, "format": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_audio_convert_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "audio_extract",
    category="audio",
    description="Extract audio from video",
    parallelizable=True,
    config_model=AudioExtractConfig,
    tags=["audio"],
)
async def run_audio_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract audio track from a video file.

    Config:
      - input_path: str (templated) - Input video file path
      - output_path: str (optional) - Output audio file path
      - format: str = "mp3" - Output audio format
      - channels: int (optional) - Number of audio channels
    Output:
      - {"output_path": str, "format": str, "duration": float}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_audio_extract_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "audio_mix",
    category="audio",
    description="Mix multiple audio tracks",
    parallelizable=False,
    config_model=AudioMixConfig,
    tags=["audio"],
)
async def run_audio_mix_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Mix multiple audio tracks together.

    Config:
      - input_paths: list[str] (templated) - List of input audio file paths
      - output_path: str (optional) - Output file path
      - volumes: list[float] (optional) - Volume levels for each track (0.0-1.0)
      - format: str = "mp3" - Output format
    Output:
      - {"output_path": str, "tracks_mixed": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_audio_mix_adapter as _legacy
    return await _legacy(config, context)
