"""Tests for the original LLM YouTube poop generator helper."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from Helper_Scripts.Creative import generate_llm_youtube_poop as script


@pytest.mark.unit
def test_build_storyboard_returns_short_multi_scene_sequence() -> None:
    """The storyboard should stay within the intended short-form runtime."""
    storyboard = script.build_storyboard()

    assert len(storyboard) >= 4
    assert all(scene.lines for scene in storyboard)
    total_duration = sum(scene.duration for scene in storyboard)
    assert 35.0 <= total_duration <= 45.0


@pytest.mark.unit
def test_build_output_paths_targets_expected_artifacts(tmp_path: Path) -> None:
    """Output planning should use the expected file names and folders."""
    plan = script.build_output_paths(tmp_path)

    assert plan.output_dir == tmp_path
    assert plan.frames_dir == tmp_path / "frames"
    assert plan.audio_path == tmp_path / "llm_youtube_poop.wav"
    assert plan.video_path == tmp_path / "llm_youtube_poop.mp4"


@pytest.mark.unit
def test_synthesize_audio_returns_expected_length_and_pcm_range() -> None:
    """Audio synthesis should cover the full storyboard and stay PCM-safe."""
    storyboard = script.build_storyboard()
    sample_rate = 8_000

    audio = script.synthesize_audio(storyboard, sample_rate=sample_rate)
    pcm = script.quantize_audio(audio)

    assert audio.shape == (int(sum(scene.duration for scene in storyboard) * sample_rate),)
    assert pcm.dtype.name == "int16"
    assert int(pcm.max()) <= 32767
    assert int(pcm.min()) >= -32768


@pytest.mark.unit
def test_build_text_events_creates_multiple_overlay_beats() -> None:
    """Each scene should yield enough text events to feel animated."""
    scene = script.build_storyboard()[1]

    events = script.build_text_events(scene, fps=12)

    assert len(events) >= len(scene.lines) * 3
    assert events == sorted(events, key=lambda event: event.frame)


@pytest.mark.unit
def test_render_frame_writes_requested_dimensions(tmp_path: Path) -> None:
    """A single rendered frame should match the requested output size."""
    storyboard = script.build_storyboard()
    config = script.RenderConfig(width=320, height=180, fps=12, sample_rate=8_000)

    image = script.render_frame(storyboard, config, frame_index=5)
    output_path = tmp_path / "frame.png"
    image.save(output_path)

    assert image.size == (320, 180)
    assert output_path.exists()


@pytest.mark.unit
def test_build_render_plan_tracks_total_frames_and_artifact_names(tmp_path: Path) -> None:
    """Render planning should combine timing and output-path expectations."""
    storyboard = script.build_storyboard()
    config = script.RenderConfig(width=320, height=180, fps=12, sample_rate=8_000)

    render_plan = script.build_render_plan(storyboard, config, tmp_path)

    assert render_plan.total_frames == int(sum(scene.duration for scene in storyboard) * config.fps)
    assert render_plan.paths.frames_dir.name == "frames"
    assert render_plan.paths.audio_path.name == "llm_youtube_poop.wav"
    assert render_plan.paths.video_path.name == "llm_youtube_poop.mp4"


@pytest.mark.unit
def test_fit_font_to_width_keeps_long_phrase_inside_frame() -> None:
    """Long phrases should shrink enough to stay inside the render area."""
    image = Image.new("RGB", (1280, 720))
    draw = ImageDraw.Draw(image)
    phrase = "EVERY WORD MAKES THE NEXT WORD NARROWER"

    font = script._fit_font_to_width(draw, phrase, base_size=80, max_width=1160)
    box = draw.textbbox((0, 0), phrase, font=font)

    assert box[2] - box[0] <= 1160
