"""Multi-voice TTS adapter.

Per-section speech synthesis with different voices, concatenation, and
EBU R128 normalization for podcast/briefing-style audio output.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Workflows.adapters._common import (
    AsyncFileWriter,
    resolve_artifacts_dir,
)
from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.audio._config import MultiVoiceTTSConfig

_MULTI_TTS_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    ConnectionError,
    KeyError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
)


async def _generate_silence(duration_seconds: float, output_path: Path, fmt: str = "mp3") -> bool:
    """Generate a silent audio segment using ffmpeg."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return False

    cmd = [
        ffmpeg_path, "-y", "-nostdin",
        "-f", "lavfi",
        "-i", "anullsrc=r=24000:cl=mono",
        "-t", str(duration_seconds),
        str(output_path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            with contextlib.suppress(Exception):
                await proc.communicate()
            return False
        return proc.returncode == 0
    except _MULTI_TTS_NONCRITICAL_EXCEPTIONS:
        return False


async def _synthesize_section(
    text: str,
    model: str,
    voice: str,
    fmt: str,
    speed: float,
    output_path: Path,
) -> int:
    """Synthesize a single text section, returning size in bytes."""
    from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
    from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2

    req = OpenAISpeechRequest(
        model=model,
        input=text,
        voice=voice,
        response_format=fmt,
        speed=speed,
        stream=True,
    )

    size_bytes = 0
    service = await get_tts_service_v2()
    async with AsyncFileWriter(output_path) as writer:
        async for chunk in service.generate_speech(req):
            if isinstance(chunk, (bytes, bytearray)):
                await writer.write(chunk)
                size_bytes += len(chunk)
            else:
                data = bytes(chunk)
                await writer.write(data)
                size_bytes += len(data)
    return size_bytes


async def _concat_files(file_paths: list[Path], output_path: Path, fmt: str = "mp3") -> bool:
    """Concatenate audio files using ffmpeg concat demuxer."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return False

    # Determine codec/format args
    codec_map = {"mp3": ["-c:a", "libmp3lame", "-q:a", "2"], "wav": ["-c:a", "pcm_s16le"],
                 "opus": ["-c:a", "libopus"], "flac": ["-c:a", "flac"], "aac": ["-c:a", "aac", "-b:a", "128k"]}
    codec_args = codec_map.get(fmt, ["-c:a", "libmp3lame", "-q:a", "2"])

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_file = f.name
        for p in file_paths:
            f.write(f"file '{p}'\n")

    cmd = [
        ffmpeg_path, "-y", "-nostdin",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        *codec_args,
        str(output_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=600)
        except asyncio.TimeoutError:
            proc.kill()
            with contextlib.suppress(Exception):
                await proc.communicate()
            return False
        return proc.returncode == 0
    except _MULTI_TTS_NONCRITICAL_EXCEPTIONS:
        return False
    finally:
        with contextlib.suppress(OSError):
            Path(concat_file).unlink()


async def _normalize_audio(
    input_path: Path, output_path: Path, target_lufs: float = -16.0
) -> bool:
    """Run EBU R128 loudness normalization via ffmpeg."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return False

    cmd = [
        ffmpeg_path, "-y", "-nostdin",
        "-i", str(input_path),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        str(output_path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            with contextlib.suppress(Exception):
                await proc.communicate()
            return False
        return proc.returncode == 0
    except _MULTI_TTS_NONCRITICAL_EXCEPTIONS:
        return False


@registry.register(
    "multi_voice_tts",
    category="audio",
    description="Multi-voice TTS: per-section synthesis + concatenation + normalization",
    parallelizable=True,
    config_model=MultiVoiceTTSConfig,
    tags=["audio", "speech", "multi-voice"],
)
async def run_multi_voice_tts_adapter(
    config: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """Multi-voice TTS: synthesize per-section, concatenate, normalize.

    Config:
      - sections: list[{voice, text}] - Sections from compose step
      - voice_assignments: dict - Voice marker -> Kokoro voice ID
      - default_model: str = "kokoro"
      - default_voice: str = "af_heart"
      - response_format: str = "mp3"
      - speed: float = 1.0
      - pause_duration_seconds: float = 1.0
      - normalize: bool = True
      - target_lufs: float = -16.0
    Output:
      - audio_uri, format, sections_generated, size_bytes, normalized
    """
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    sections = config.get("sections") or []
    if not sections:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            sections = prev.get("sections") or []

    if not sections:
        return {"error": "missing_sections"}

    voice_assignments = config.get("voice_assignments") or {}
    if not voice_assignments:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            voice_assignments = prev.get("voice_assignments") or {}

    default_model = str(config.get("default_model") or "kokoro")
    default_voice = str(config.get("default_voice") or "af_heart")
    fmt = str(config.get("response_format") or "mp3").lower()
    ext = fmt if fmt in {"mp3", "wav", "opus", "flac", "aac"} else "mp3"
    try:
        speed = float(config.get("speed", 1.0))
    except (TypeError, ValueError):
        speed = 1.0
    pause_duration = float(config.get("pause_duration_seconds", 1.0))
    do_normalize = bool(config.get("normalize", True))
    target_lufs = float(config.get("target_lufs", -16.0))
    fallback_provider = config.get("fallback_provider")
    fallback_voice = str(config.get("fallback_voice") or "nova")

    import time as _time

    step_run_id = str(context.get("step_run_id") or f"mvtts_{int(_time.time() * 1000)}")
    out_dir = resolve_artifacts_dir(step_run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate per-section audio files
    segment_files: list[Path] = []
    sections_generated = 0

    for idx, section in enumerate(sections):
        # Check cancellation between sections
        try:
            if callable(context.get("is_cancelled")) and context["is_cancelled"]():
                return {"__status__": "cancelled"}
        except _MULTI_TTS_NONCRITICAL_EXCEPTIONS:
            pass

        text = section.get("text", "").strip()
        if not text:
            continue

        voice_marker = section.get("voice", "HOST")
        kokoro_voice = voice_assignments.get(voice_marker, default_voice)
        section_path = out_dir / f"section_{idx:03d}.{ext}"

        # Strip [pause] markers from text; we'll insert silence between sections
        clean_text = text.replace("[pause]", "").strip()
        if not clean_text:
            continue

        try:
            await _synthesize_section(clean_text, default_model, kokoro_voice, fmt, speed, section_path)
            segment_files.append(section_path)
            sections_generated += 1
        except _MULTI_TTS_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Section {idx} TTS failed with {default_model}/{kokoro_voice}: {e}")
            # Fallback attempt
            if fallback_provider:
                try:
                    await _synthesize_section(
                        clean_text, "tts-1", fallback_voice, fmt, speed, section_path
                    )
                    segment_files.append(section_path)
                    sections_generated += 1
                except _MULTI_TTS_NONCRITICAL_EXCEPTIONS as e2:
                    logger.warning(f"Section {idx} fallback TTS also failed: {e2}")

        # Add silence gap between sections (not after last)
        if pause_duration > 0 and idx < len(sections) - 1:
            silence_path = out_dir / f"silence_{idx:03d}.{ext}"
            if await _generate_silence(pause_duration, silence_path, fmt):
                segment_files.append(silence_path)

    if not segment_files:
        return {"error": "no_sections_generated"}

    # Concatenate
    concat_path = out_dir / f"briefing_raw.{ext}"
    if len(segment_files) == 1:
        # Single file, just rename
        segment_files[0].rename(concat_path)
    else:
        concat_ok = await _concat_files(segment_files, concat_path, fmt)
        if not concat_ok:
            # Fallback: use the first file
            if segment_files[0].exists():
                segment_files[0].rename(concat_path)
            else:
                return {"error": "concat_failed"}

    # Normalize
    final_path = concat_path
    normalized = False
    if do_normalize:
        norm_path = out_dir / f"briefing.{ext}"
        if await _normalize_audio(concat_path, norm_path, target_lufs):
            final_path = norm_path
            normalized = True
        else:
            final_path = concat_path

    size_bytes = final_path.stat().st_size if final_path.exists() else 0

    # Register artifact
    audio_artifact_id = None
    try:
        if callable(context.get("add_artifact")):
            import mimetypes

            mime, _ = mimetypes.guess_type(str(final_path))
            audio_artifact_id = f"mvtts_{uuid.uuid4()}"
            context["add_artifact"](
                type="tts_audio",
                uri=f"file://{final_path}",
                size_bytes=size_bytes,
                mime_type=mime or "application/octet-stream",
                metadata={
                    "model": default_model,
                    "sections_generated": sections_generated,
                    "format": ext,
                    "multi_voice": True,
                },
                artifact_id=audio_artifact_id,
            )
    except _MULTI_TTS_NONCRITICAL_EXCEPTIONS:
        audio_artifact_id = None

    outputs: dict[str, Any] = {
        "audio_uri": f"file://{final_path}",
        "audio_path": str(final_path),
        "format": ext,
        "sections_generated": sections_generated,
        "size_bytes": size_bytes,
        "normalized": normalized,
    }

    if audio_artifact_id:
        outputs["artifact_id"] = audio_artifact_id
        outputs["download_url"] = f"/api/v1/workflows/artifacts/{audio_artifact_id}/download"

    return outputs
