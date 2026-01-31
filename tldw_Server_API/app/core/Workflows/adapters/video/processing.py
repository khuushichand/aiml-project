"""Video processing adapters.

This module includes adapters for video processing operations:
- video_trim: Trim video files
- video_concat: Concatenate video files
- video_convert: Convert video format
- video_thumbnail: Generate video thumbnail
- video_extract_frames: Extract frames from video
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.video._config import (
    VideoTrimConfig,
    VideoConcatConfig,
    VideoConvertConfig,
    VideoThumbnailConfig,
    VideoExtractFramesConfig,
)


@registry.register(
    "video_trim",
    category="video",
    description="Trim video files",
    parallelizable=True,
    config_model=VideoTrimConfig,
    tags=["video"],
)
async def run_video_trim_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Trim a video file to a specific time range.

    Config:
      - input_path: str (templated) - Input video file path
      - output_path: str (optional) - Output file path
      - start_time: float = 0 - Start time in seconds
      - end_time: float (optional) - End time in seconds
      - duration: float (optional) - Duration in seconds
    Output:
      - {"output_path": str, "duration": float}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_video_trim_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "video_concat",
    category="video",
    description="Concatenate video files",
    parallelizable=False,
    config_model=VideoConcatConfig,
    tags=["video"],
)
async def run_video_concat_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Concatenate multiple video files into one.

    Config:
      - input_paths: list[str] (templated) - List of input video file paths
      - output_path: str (optional) - Output file path
      - format: str (optional) - Output format
    Output:
      - {"output_path": str, "duration": float}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_video_concat_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "video_convert",
    category="video",
    description="Convert video format",
    parallelizable=False,
    config_model=VideoConvertConfig,
    tags=["video"],
)
async def run_video_convert_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert video file to a different format.

    Config:
      - input_path: str (templated) - Input video file path
      - output_path: str (optional) - Output file path
      - format: str = "mp4" - Target format
      - codec: str (optional) - Video codec
      - resolution: str (optional) - Target resolution (e.g., "1920x1080")
      - bitrate: str (optional) - Video bitrate
    Output:
      - {"output_path": str, "format": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_video_convert_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "video_thumbnail",
    category="video",
    description="Generate video thumbnail",
    parallelizable=True,
    config_model=VideoThumbnailConfig,
    tags=["video"],
)
async def run_video_thumbnail_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a thumbnail image from a video.

    Config:
      - input_path: str (templated) - Input video file path
      - output_path: str (optional) - Output image path
      - timestamp: float = 0 - Time position in seconds
      - width: int (optional) - Thumbnail width
      - height: int (optional) - Thumbnail height
      - format: str = "jpg" - Image format
    Output:
      - {"output_path": str, "width": int, "height": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_video_thumbnail_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "video_extract_frames",
    category="video",
    description="Extract frames from video",
    parallelizable=True,
    config_model=VideoExtractFramesConfig,
    tags=["video"],
)
async def run_video_extract_frames_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract frames from a video at specified intervals.

    Config:
      - input_path: str (templated) - Input video file path
      - output_dir: str (optional) - Output directory for frames
      - fps: float = 1 - Frames per second to extract
      - start_time: float = 0 - Start time in seconds
      - end_time: float (optional) - End time in seconds
      - format: str = "jpg" - Image format
    Output:
      - {"frames": [str], "count": int, "output_dir": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_video_extract_frames_adapter as _legacy
    return await _legacy(config, context)
