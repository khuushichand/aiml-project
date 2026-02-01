"""Video processing adapters.

This module includes adapters for video operations:
- video_trim: Trim video files
- video_concat: Concatenate video files
- video_convert: Convert video format
- video_thumbnail: Generate video thumbnail
- video_extract_frames: Extract frames from video
- subtitle_generate: Generate subtitles
- subtitle_translate: Translate subtitles
- subtitle_burn: Burn subtitles into video
"""

from tldw_Server_API.app.core.Workflows.adapters.video.processing import (
    run_video_trim_adapter,
    run_video_concat_adapter,
    run_video_convert_adapter,
    run_video_thumbnail_adapter,
    run_video_extract_frames_adapter,
)

from tldw_Server_API.app.core.Workflows.adapters.video.subtitles import (
    run_subtitle_generate_adapter,
    run_subtitle_translate_adapter,
    run_subtitle_burn_adapter,
)

__all__ = [
    "run_video_trim_adapter",
    "run_video_concat_adapter",
    "run_video_convert_adapter",
    "run_video_thumbnail_adapter",
    "run_video_extract_frames_adapter",
    "run_subtitle_generate_adapter",
    "run_subtitle_translate_adapter",
    "run_subtitle_burn_adapter",
]
