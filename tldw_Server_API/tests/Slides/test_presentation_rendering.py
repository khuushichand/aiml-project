from pathlib import Path
import subprocess

import pytest
from PIL import Image, ImageChops

from tldw_Server_API.app.core.Slides.presentation_rendering import (
    PresentationRenderError,
    _resolve_ffmpeg_timeout_seconds,
    _render_slide_frame,
    _run_ffmpeg_command,
    render_presentation_video,
)


def test_render_slide_frame_draws_slide_text_content(tmp_path):
    output_path = tmp_path / "slide.png"

    _render_slide_frame(
        {
            "order": 0,
            "layout": "content",
            "title": "Deck title",
            "content": "Line one\nLine two",
            "speaker_notes": "Narration",
            "metadata": {},
        },
        output_path=output_path,
        collections_db=None,
        user_id=None,
    )

    rendered = Image.open(output_path).convert("RGB")
    background = Image.new("RGB", rendered.size, "#0f172a")

    assert ImageChops.difference(rendered, background).getbbox() is not None


def test_render_presentation_video_builds_slide_segments_from_visuals_and_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.presentation_rendering._resolve_ffmpeg_path",
        lambda: "/usr/bin/ffmpeg",
    )
    captured_commands: list[list[str]] = []
    segment_outputs: list[Path] = []
    slide_frame_calls: list[dict[str, object]] = []
    audio_path = tmp_path / "slide-0.wav"
    audio_path.write_bytes(b"audio-bytes")

    def _fake_render_slide_frame(slide, *, output_path, collections_db, user_id):
        slide_frame_calls.append(
            {
                "title": slide.get("title"),
                "content": slide.get("content"),
                "user_id": user_id,
                "has_collections": collections_db is not None,
            }
        )
        output_path.write_bytes(b"png-bytes")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.presentation_rendering._render_slide_frame",
        _fake_render_slide_frame,
    )

    def _fake_materialize_slide_audio(slide, *, temp_dir, slide_index, collections_db, user_id):
        assert collections_db is not None
        assert user_id == 7
        return audio_path if slide_index == 0 else None

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.presentation_rendering._materialize_slide_audio",
        _fake_materialize_slide_audio,
    )

    def _fake_run_ffmpeg(command: list[str], *, output_path: Path, timeout_seconds: int | None = None) -> None:
        captured_commands.append(command)
        segment_outputs.append(output_path)
        assert command[0] == "/usr/bin/ffmpeg"
        assert timeout_seconds is not None
        output_path.write_bytes(b"video-bytes")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.presentation_rendering._run_ffmpeg_command",
        _fake_run_ffmpeg,
    )

    result = render_presentation_video(
        presentation_id="pres_123",
        presentation_version=1,
        title="Deck",
        slides=[
            {
                "order": 0,
                "layout": "title",
                "title": "Deck",
                "content": "Opening slide",
                "speaker_notes": "Intro",
                "metadata": {},
            },
            {
                "order": 1,
                "layout": "content",
                "title": "Agenda",
                "content": "Point A\nPoint B",
                "speaker_notes": "Longer narration for the second slide",
                "metadata": {},
            }
        ],
        output_format="mp4",
        output_dir=tmp_path,
        collections_db=object(),
        user_id=7,
    )

    assert [call["title"] for call in slide_frame_calls] == ["Deck", "Agenda"]
    assert [call["content"] for call in slide_frame_calls] == ["Opening slide", "Point A\nPoint B"]
    assert len(captured_commands) == 3
    assert str(audio_path) in captured_commands[0]
    assert "anullsrc=r=48000:cl=stereo" in captured_commands[1]
    assert "-f" in captured_commands[2]
    assert "concat" in captured_commands[2]
    assert result.output_format == "mp4"
    assert result.storage_path.endswith(".mp4")
    assert result.output_path.exists()
    assert result.byte_size == len(b"video-bytes")


def test_render_presentation_video_rejects_unsupported_format(tmp_path):
    with pytest.raises(PresentationRenderError) as exc:
        render_presentation_video(
            presentation_id="pres_123",
            presentation_version=1,
            title="Deck",
            slides=[],
            output_format="mov",
            output_dir=tmp_path,
        )

    assert exc.value.code == "presentation_render_format_invalid"


def test_run_ffmpeg_command_logs_stderr_on_failure(tmp_path, monkeypatch):
    output_path = tmp_path / "missing.mp4"
    logged: dict[str, object] = {}

    def _fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr=b"ffmpeg exploded")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.presentation_rendering.subprocess.run",
        _fake_run,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.presentation_rendering.logger.warning",
        lambda message, *args: logged.update({"message": message, "args": args}),
    )

    with pytest.raises(PresentationRenderError) as exc:
        _run_ffmpeg_command(["/usr/bin/ffmpeg"], output_path=output_path, timeout_seconds=321)

    assert exc.value.code == "presentation_render_failed"
    assert "ffmpeg command failed with exit code {}" in str(logged["message"])
    assert "ffmpeg exploded" in str(logged["args"][1])


def test_resolve_ffmpeg_timeout_scales_with_expected_duration(monkeypatch):
    monkeypatch.delenv("PRESENTATION_RENDER_FFMPEG_TIMEOUT_SECONDS", raising=False)

    assert _resolve_ffmpeg_timeout_seconds(expected_duration_seconds=10) == 120
    assert _resolve_ffmpeg_timeout_seconds(expected_duration_seconds=600) > 120

    monkeypatch.setenv("PRESENTATION_RENDER_FFMPEG_TIMEOUT_SECONDS", "45")
    assert _resolve_ffmpeg_timeout_seconds(expected_duration_seconds=600) == 45
