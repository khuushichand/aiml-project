from pathlib import Path

import pytest

from tldw_Server_API.app.core.Slides.presentation_rendering import (
    PresentationRenderError,
    render_presentation_video,
)


def test_render_presentation_video_writes_mp4_output(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.presentation_rendering._resolve_ffmpeg_path",
        lambda: "/usr/bin/ffmpeg",
    )

    def _fake_run_ffmpeg(command: list[str], *, output_path: Path) -> None:
        assert command[0] == "/usr/bin/ffmpeg"
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
                "content": "",
                "speaker_notes": "Intro",
                "metadata": {},
            }
        ],
        output_format="mp4",
        output_dir=tmp_path,
    )

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
