"""Pydantic config models for video adapters."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class VideoTrimConfig(BaseAdapterConfig):
    """Config for video trimming adapter."""

    file_uri: str = Field(..., description="file:// path to input video (required)")
    start_ms: int = Field(0, ge=0, description="Start position in milliseconds")
    end_ms: Optional[int] = Field(None, ge=0, description="End position in milliseconds")
    duration_ms: Optional[int] = Field(None, ge=0, description="Duration to keep in milliseconds")
    output_format: str = Field("mp4", description="Output video format")


class VideoConcatConfig(BaseAdapterConfig):
    """Config for video concatenation adapter."""

    files: List[str] = Field(..., description="List of file:// URIs to concatenate")
    output_format: str = Field("mp4", description="Output video format")
    transition: Optional[str] = Field(None, description="Transition effect between clips")
    transition_duration_ms: int = Field(0, ge=0, description="Transition duration in ms")


class VideoConvertConfig(BaseAdapterConfig):
    """Config for video format conversion adapter."""

    file_uri: str = Field(..., description="file:// path to input video (required)")
    output_format: Literal["mp4", "webm", "mkv", "avi", "mov"] = Field(
        "mp4", description="Target video format"
    )
    video_codec: Optional[str] = Field(None, description="Video codec (e.g., h264, vp9)")
    audio_codec: Optional[str] = Field(None, description="Audio codec (e.g., aac, opus)")
    resolution: Optional[str] = Field(None, description="Target resolution (e.g., '1920x1080')")
    bitrate: Optional[str] = Field(None, description="Target video bitrate (e.g., '5M')")
    fps: Optional[int] = Field(None, ge=1, le=120, description="Target frame rate")


class VideoThumbnailConfig(BaseAdapterConfig):
    """Config for video thumbnail generation adapter."""

    file_uri: str = Field(..., description="file:// path to input video (required)")
    timestamp_ms: Optional[int] = Field(None, ge=0, description="Timestamp to capture in milliseconds")
    timestamp_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Timestamp as percentage of video duration"
    )
    width: Optional[int] = Field(None, ge=1, description="Output width in pixels")
    height: Optional[int] = Field(None, ge=1, description="Output height in pixels")
    format: Literal["jpg", "png", "webp"] = Field("jpg", description="Output image format")


class VideoExtractFramesConfig(BaseAdapterConfig):
    """Config for extracting frames from video adapter."""

    file_uri: str = Field(..., description="file:// path to input video (required)")
    fps: Optional[float] = Field(None, ge=0.01, description="Frames per second to extract")
    count: Optional[int] = Field(None, ge=1, description="Total number of frames to extract")
    start_ms: Optional[int] = Field(None, ge=0, description="Start position in milliseconds")
    end_ms: Optional[int] = Field(None, ge=0, description="End position in milliseconds")
    format: Literal["jpg", "png", "webp"] = Field("jpg", description="Output image format")


class SubtitleGenerateConfig(BaseAdapterConfig):
    """Config for subtitle generation adapter."""

    file_uri: str = Field(..., description="file:// path to audio/video file (required)")
    model: str = Field("large-v3", description="Whisper model for transcription")
    language: Optional[str] = Field(None, description="Source language code")
    format: Literal["srt", "vtt", "ass"] = Field("srt", description="Subtitle output format")
    word_timestamps: bool = Field(False, description="Include word-level timestamps")
    max_line_length: Optional[int] = Field(None, ge=20, description="Maximum characters per line")


class SubtitleTranslateConfig(BaseAdapterConfig):
    """Config for subtitle translation adapter."""

    file_uri: str = Field(..., description="file:// path to subtitle file (required)")
    target_language: str = Field(..., description="Target language code (required)")
    source_language: Optional[str] = Field(None, description="Source language code (auto-detect if not specified)")
    provider: Optional[str] = Field(None, description="Translation provider (openai, anthropic, etc.)")
    model: Optional[str] = Field(None, description="Model to use for translation")
    preserve_timing: bool = Field(True, description="Preserve original timing information")


class SubtitleBurnConfig(BaseAdapterConfig):
    """Config for burning subtitles into video adapter."""

    video_uri: str = Field(..., description="file:// path to input video (required)")
    subtitle_uri: str = Field(..., description="file:// path to subtitle file (required)")
    output_format: str = Field("mp4", description="Output video format")
    font_size: Optional[int] = Field(None, ge=8, le=72, description="Font size for subtitles")
    font_name: Optional[str] = Field(None, description="Font name for subtitles")
    position: Literal["bottom", "top", "center"] = Field("bottom", description="Subtitle position")
    margin_v: Optional[int] = Field(None, ge=0, description="Vertical margin in pixels")
