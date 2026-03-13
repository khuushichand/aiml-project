"""Minimal presentation video rendering helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.Slides.slides_db import SlidesDatabase

_SUPPORTED_RENDER_FORMATS = {"mp4", "webm"}


class PresentationRenderError(RuntimeError):
    """Raised when a presentation render cannot be completed."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass
class PresentationRenderResult:
    """Details about a rendered presentation video file."""

    output_format: str
    storage_path: str
    output_path: Path
    byte_size: int


@dataclass
class PresentationRenderSnapshot:
    """Versioned presentation data used for a render."""

    presentation_id: str
    presentation_version: int
    title: str
    theme: str
    slides: list[dict[str, Any]]
    studio_data: dict[str, Any] | None


def load_presentation_render_snapshot(
    db: SlidesDatabase,
    *,
    presentation_id: str,
    presentation_version: int,
) -> PresentationRenderSnapshot:
    """Load a specific version snapshot for rendering."""

    try:
        version_row = db.get_presentation_version(
            presentation_id=presentation_id,
            version=presentation_version,
        )
    except KeyError as exc:
        raise PresentationRenderError("presentation_render_version_not_found") from exc

    try:
        payload = json.loads(version_row.payload_json)
    except json.JSONDecodeError as exc:
        raise PresentationRenderError("presentation_render_snapshot_invalid") from exc
    if not isinstance(payload, dict):
        raise PresentationRenderError("presentation_render_snapshot_invalid")

    slides = payload.get("slides")
    if isinstance(slides, str):
        try:
            slides = json.loads(slides)
        except json.JSONDecodeError as exc:
            raise PresentationRenderError("presentation_render_snapshot_invalid") from exc
    if not isinstance(slides, list):
        raise PresentationRenderError("presentation_render_snapshot_invalid")
    title = str(payload.get("title") or "Presentation").strip() or "Presentation"
    theme = str(payload.get("theme") or "black").strip() or "black"
    studio_data = payload.get("studio_data")
    if isinstance(studio_data, str) and studio_data.strip():
        try:
            parsed_studio = json.loads(studio_data)
        except json.JSONDecodeError:
            parsed_studio = None
        studio_data = parsed_studio if isinstance(parsed_studio, dict) else None
    elif studio_data is not None and not isinstance(studio_data, dict):
        studio_data = None

    normalized_slides: list[dict[str, Any]] = []
    for slide in slides:
        if isinstance(slide, dict):
            normalized_slides.append(dict(slide))

    return PresentationRenderSnapshot(
        presentation_id=presentation_id,
        presentation_version=presentation_version,
        title=title,
        theme=theme,
        slides=normalized_slides,
        studio_data=studio_data,
    )


def _sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-._")
    return cleaned[:80] or "presentation"


def _build_storage_name(*, presentation_id: str, presentation_version: int, output_format: str) -> str:
    stem = _sanitize_name(presentation_id)
    return f"{stem}-v{presentation_version}.{output_format}"


def _resolve_ffmpeg_path() -> str:
    env_path = (os.getenv("FFMPEG_PATH") or "").strip()
    if env_path:
        return env_path
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    raise PresentationRenderError("presentation_render_ffmpeg_unavailable")


def _run_ffmpeg_command(command: list[str], *, output_path: Path) -> None:
    try:
        # The renderer passes a fixed argv list to a locally resolved ffmpeg binary.
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )  # nosec B603
    except FileNotFoundError as exc:
        raise PresentationRenderError("presentation_render_ffmpeg_unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise PresentationRenderError("presentation_render_timeout", retryable=True) from exc
    except subprocess.CalledProcessError as exc:
        raise PresentationRenderError("presentation_render_failed", retryable=True) from exc
    if not output_path.exists():
        raise PresentationRenderError("presentation_render_output_missing", retryable=True)


def render_presentation_video(
    *,
    presentation_id: str,
    presentation_version: int,
    title: str,
    slides: list[dict[str, Any]],
    output_format: str,
    output_dir: Path | str,
) -> PresentationRenderResult:
    """Render a minimal slideshow video for a specific presentation version."""

    normalized_format = str(output_format or "").strip().lower()
    if normalized_format not in _SUPPORTED_RENDER_FORMATS:
        raise PresentationRenderError("presentation_render_format_invalid")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    storage_name = _build_storage_name(
        presentation_id=presentation_id,
        presentation_version=presentation_version,
        output_format=normalized_format,
    )
    output_path = output_root / storage_name

    ffmpeg_path = _resolve_ffmpeg_path()
    duration_seconds = max(1, len(slides) or 1)
    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=1280x720:d={duration_seconds}",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo",
        "-shortest",
        "-metadata",
        f"title={title}",
    ]
    if normalized_format == "mp4":
        command.extend(
            [
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
            ]
        )
    else:
        command.extend(
            [
                "-c:v",
                "libvpx-vp9",
                "-b:v",
                "0",
                "-crf",
                "35",
                "-c:a",
                "libopus",
            ]
        )
    command.append(str(output_path))

    _run_ffmpeg_command(command, output_path=output_path)

    return PresentationRenderResult(
        output_format=normalized_format,
        storage_path=storage_name,
        output_path=output_path,
        byte_size=output_path.stat().st_size,
    )
