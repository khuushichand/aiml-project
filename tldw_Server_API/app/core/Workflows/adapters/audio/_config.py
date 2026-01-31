"""Pydantic config models for audio adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class NormalizationOptionsConfig(BaseAdapterConfig):
    """Options for audio normalization."""

    normalize: bool = Field(False, description="Enable loudness normalization")
    target_lufs: float = Field(-16.0, description="Target loudness in LUFS")
    true_peak_dbfs: float = Field(-1.5, description="True peak in dBFS")
    lra: float = Field(11.0, description="Loudness range target")


class PostProcessConfig(BaseAdapterConfig):
    """Post-processing options for TTS output."""

    normalize: bool = Field(False, description="Enable loudness normalization")
    target_lufs: float = Field(-16.0, description="Target LUFS for normalization")
    true_peak_dbfs: float = Field(-1.5, description="True peak in dBFS")
    lra: float = Field(11.0, description="Loudness range")


class TTSConfig(BaseAdapterConfig):
    """Config for TTS (text-to-speech) adapter."""

    input: Optional[str] = Field(None, description="Text to synthesize (templated); defaults to last.text")
    model: str = Field("kokoro", description="TTS model (kokoro, tts-1, etc.)")
    voice: str = Field("af_heart", description="Voice identifier")
    response_format: Literal["mp3", "wav", "opus", "flac", "aac", "pcm"] = Field(
        "mp3", description="Output audio format"
    )
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech speed multiplier")
    provider: Optional[str] = Field(None, description="Provider hint (optional)")
    lang_code: Optional[str] = Field(None, description="Language code hint")
    normalization_options: Optional[NormalizationOptionsConfig] = Field(
        None, description="Input normalization options"
    )
    voice_reference: Optional[str] = Field(None, description="Voice reference file URI")
    reference_duration_min: Optional[float] = Field(None, description="Minimum reference duration")
    extra_params: Optional[Dict[str, Any]] = Field(None, description="Provider-specific parameters")
    provider_options: Optional[Dict[str, Any]] = Field(None, description="Additional provider options")
    output_filename_template: Optional[str] = Field(None, description="Output filename template (Jinja)")
    post_process: Optional[PostProcessConfig] = Field(None, description="Post-processing options")


class STTConfig(BaseAdapterConfig):
    """Config for STT (speech-to-text) adapter."""

    file_uri: str = Field(..., description="file:// path to audio/video file (required)")
    model: str = Field("large-v3", description="Whisper model name")
    language: Optional[str] = Field(None, description="Source language code")
    hotwords: Optional[List[str]] = Field(None, description="Hotwords for improved recognition")
    diarize: bool = Field(False, description="Enable speaker diarization")
    word_timestamps: bool = Field(False, description="Include word-level timestamps")


class AudioNormalizeConfig(BaseAdapterConfig):
    """Config for audio normalization adapter."""

    file_uri: str = Field(..., description="file:// path to input audio (required)")
    target_lufs: float = Field(-16.0, description="Target loudness in LUFS")
    true_peak_dbfs: float = Field(-1.5, description="True peak in dBFS")
    lra: float = Field(11.0, description="Loudness range target")
    output_format: str = Field("mp3", description="Output audio format")


class AudioConcatConfig(BaseAdapterConfig):
    """Config for audio concatenation adapter."""

    files: List[str] = Field(..., description="List of file:// URIs to concatenate")
    output_format: str = Field("mp3", description="Output audio format")
    crossfade_ms: int = Field(0, ge=0, description="Crossfade duration between clips in ms")


class AudioTrimConfig(BaseAdapterConfig):
    """Config for audio trimming adapter."""

    file_uri: str = Field(..., description="file:// path to input audio (required)")
    start_ms: int = Field(0, ge=0, description="Start position in milliseconds")
    end_ms: Optional[int] = Field(None, ge=0, description="End position in milliseconds")
    duration_ms: Optional[int] = Field(None, ge=0, description="Duration to keep in milliseconds")
    output_format: str = Field("mp3", description="Output audio format")


class AudioConvertConfig(BaseAdapterConfig):
    """Config for audio format conversion adapter."""

    file_uri: str = Field(..., description="file:// path to input audio (required)")
    output_format: Literal["mp3", "wav", "opus", "flac", "aac", "ogg"] = Field(
        "mp3", description="Target audio format"
    )
    bitrate: Optional[str] = Field(None, description="Target bitrate (e.g., '128k')")
    sample_rate: Optional[int] = Field(None, description="Target sample rate in Hz")
    channels: Optional[int] = Field(None, ge=1, le=8, description="Number of audio channels")


class AudioExtractConfig(BaseAdapterConfig):
    """Config for extracting audio from video adapter."""

    file_uri: str = Field(..., description="file:// path to input video (required)")
    output_format: Literal["mp3", "wav", "opus", "flac", "aac", "ogg"] = Field(
        "mp3", description="Output audio format"
    )
    start_ms: Optional[int] = Field(None, ge=0, description="Start position in milliseconds")
    end_ms: Optional[int] = Field(None, ge=0, description="End position in milliseconds")


class AudioMixConfig(BaseAdapterConfig):
    """Config for audio mixing adapter."""

    files: List[str] = Field(..., description="List of file:// URIs to mix")
    volumes: Optional[List[float]] = Field(None, description="Volume levels for each track (0.0-2.0)")
    output_format: str = Field("mp3", description="Output audio format")


class AudioDiarizeConfig(BaseAdapterConfig):
    """Config for speaker diarization adapter."""

    file_uri: str = Field(..., description="file:// path to input audio (required)")
    min_speakers: Optional[int] = Field(None, ge=1, description="Minimum expected speakers")
    max_speakers: Optional[int] = Field(None, ge=1, description="Maximum expected speakers")
    model: Optional[str] = Field(None, description="Diarization model to use")
