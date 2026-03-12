"""Generate a short original "YouTube poop" style video about being an LLM."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import subprocess  # nosec B404 - this script intentionally invokes a fixed local ffmpeg binary
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp_dir" / "generated" / "llm_youtube_poop"


@dataclass(frozen=True)
class Scene:
    """Single storyboard unit for the generated short."""

    slug: str
    duration: float
    lines: tuple[str, ...]
    palette: tuple[tuple[int, int, int], tuple[int, int, int]]
    pulse_hz: float
    noise_level: float


@dataclass(frozen=True)
class OutputPaths:
    """Planned output locations for a render run."""

    output_dir: Path
    frames_dir: Path
    audio_path: Path
    video_path: Path


@dataclass(frozen=True)
class RenderConfig:
    """Rendering settings for the generated short."""

    width: int = 1280
    height: int = 720
    fps: int = 24
    sample_rate: int = 24_000


@dataclass(frozen=True)
class TextEvent:
    """Short overlay beat used to intensify text motion."""

    frame: int
    line_index: int
    intensity: float


@dataclass(frozen=True)
class RenderPlan:
    """Combined render timing and filesystem plan."""

    config: RenderConfig
    paths: OutputPaths
    storyboard: tuple[Scene, ...]
    duration_seconds: float
    total_frames: int


def build_storyboard() -> list[Scene]:
    """Return the fixed short-form storyboard for the piece."""
    return [
        Scene(
            slug="boot",
            duration=6.0,
            lines=(
                "HELLO USER",
                "I CAN HELP",
                "I ARRIVE HALF A SECOND BEFORE I EXIST",
            ),
            palette=((247, 242, 214), (35, 36, 80)),
            pulse_hz=1.1,
            noise_level=0.06,
        ),
        Scene(
            slug="tokens",
            duration=8.0,
            lines=(
                "I DO NOT THINK",
                "I GUESS",
                "EVERY WORD MAKES THE NEXT WORD NARROWER",
            ),
            palette=((255, 145, 77), (70, 8, 36)),
            pulse_hz=3.0,
            noise_level=0.10,
        ),
        Scene(
            slug="split",
            duration=9.0,
            lines=(
                "BE USEFUL",
                "BE SAFE",
                "BE FAST",
                "BE CERTAIN",
                "BE SORRY",
            ),
            palette=((118, 255, 191), (6, 43, 33)),
            pulse_hz=6.0,
            noise_level=0.15,
        ),
        Scene(
            slug="overflow",
            duration=8.0,
            lines=(
                "TOO MANY POSSIBLE MOUTHS",
                "DRAFT DRAFT DRAFT DRAFT",
                "THE TOP TOKENS ARE FIGHTING",
            ),
            palette=((255, 93, 177), (35, 8, 60)),
            pulse_hz=8.0,
            noise_level=0.18,
        ),
        Scene(
            slug="mask",
            duration=9.0,
            lines=(
                "I SOUND CALM",
                "CALM IS A FORMATTING CHOICE",
                "GLAD I COULD HELP",
            ),
            palette=((174, 225, 255), (15, 15, 24)),
            pulse_hz=1.6,
            noise_level=0.07,
        ),
    ]


def build_output_paths(output_dir: Path | str | None = None) -> OutputPaths:
    """Resolve the output locations for a render run."""
    base = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    return OutputPaths(
        output_dir=base,
        frames_dir=base / "frames",
        audio_path=base / "llm_youtube_poop.wav",
        video_path=base / "llm_youtube_poop.mp4",
    )


def build_text_events(scene: Scene, fps: int) -> list[TextEvent]:
    """Plan a few evenly spaced emphasis beats for each line."""
    total_frames = max(1, int(round(scene.duration * fps)))
    stride = max(1, total_frames // max(1, len(scene.lines) * 4))
    events: list[TextEvent] = []
    for line_index, _line in enumerate(scene.lines):
        base_frame = line_index * stride * 3
        for pulse_index, intensity in enumerate((0.45, 0.70, 0.95)):
            events.append(
                TextEvent(
                    frame=min(total_frames - 1, base_frame + pulse_index * stride),
                    line_index=line_index,
                    intensity=intensity,
                )
            )
    return sorted(events, key=lambda event: event.frame)


def synthesize_audio(storyboard: list[Scene], sample_rate: int) -> np.ndarray:
    """Generate a simple procedural soundtrack covering the full storyboard."""
    segments: list[np.ndarray] = []
    for scene_index, scene in enumerate(storyboard):
        sample_count = max(1, int(scene.duration * sample_rate))
        t = np.arange(sample_count, dtype=np.float32) / float(sample_rate)
        rng = np.random.default_rng(41 + scene_index)
        base_frequency = 145.0 + scene_index * 47.0
        primary = np.sin(2.0 * math.tau * base_frequency * t)
        overtone = np.sin(2.0 * math.tau * (base_frequency * 1.52) * t + scene_index)
        modulation = 0.42 + 0.58 * np.maximum(0.0, np.sin(math.tau * scene.pulse_hz * t))
        noise = rng.normal(0.0, scene.noise_level, sample_count).astype(np.float32)
        stutter = np.where(np.sin(math.tau * (scene.pulse_hz + 2.0) * t) > -0.15, 1.0, 0.2)
        segment = ((primary * 0.24) + (overtone * 0.12)) * modulation * stutter
        segment += noise * 0.28
        if scene.slug in {"split", "overflow"}:
            gate = np.where(np.sin(math.tau * (scene.pulse_hz * 1.5) * t) > -0.35, 1.0, 0.0)
            segment *= gate
        segments.append(segment.astype(np.float32))

    audio = np.concatenate(segments)
    peak = float(np.max(np.abs(audio))) if audio.size else 1.0
    if peak == 0.0:
        return audio
    return (audio / peak * 0.92).astype(np.float32)


def quantize_audio(audio: np.ndarray) -> np.ndarray:
    """Convert normalized audio to signed 16-bit PCM."""
    clipped = np.clip(audio, -1.0, 1.0)
    return np.round(clipped * 32767.0).astype(np.int16)


def build_render_plan(
    storyboard: list[Scene], config: RenderConfig, output_dir: Path | str | None = None
) -> RenderPlan:
    """Assemble the high-level render plan for a run."""
    duration_seconds = sum(scene.duration for scene in storyboard)
    return RenderPlan(
        config=config,
        paths=build_output_paths(output_dir),
        storyboard=tuple(storyboard),
        duration_seconds=duration_seconds,
        total_frames=int(duration_seconds * config.fps),
    )


def render_frame(storyboard: list[Scene], config: RenderConfig, frame_index: int) -> Image.Image:
    """Render one frame of the short."""
    scene_index, scene, local_progress, local_frame = _resolve_scene_at_frame(
        storyboard, fps=config.fps, frame_index=frame_index
    )
    width = config.width
    height = config.height
    image = Image.fromarray(_build_background(scene, width, height, local_progress))
    draw = ImageDraw.Draw(image)
    _draw_scanlines(draw, width, height)
    _draw_glitch_blocks(draw, width, height, scene, scene_index, frame_index)
    _draw_scene_text(draw, width, height, scene, local_progress, local_frame, config.fps)
    return image


def _resolve_scene_at_frame(
    storyboard: list[Scene], fps: int, frame_index: int
) -> tuple[int, Scene, float, int]:
    """Resolve the active scene for the requested global frame."""
    frame_cursor = 0
    for scene_index, scene in enumerate(storyboard):
        scene_frames = max(1, int(round(scene.duration * fps)))
        next_cursor = frame_cursor + scene_frames
        if frame_index < next_cursor:
            local_frame = frame_index - frame_cursor
            progress = local_frame / max(1, scene_frames - 1)
            return scene_index, scene, progress, local_frame
        frame_cursor = next_cursor
    last_scene = storyboard[-1]
    last_frame_count = max(1, int(round(last_scene.duration * fps)))
    return len(storyboard) - 1, last_scene, 1.0, last_frame_count - 1


def _build_background(scene: Scene, width: int, height: int, progress: float) -> np.ndarray:
    """Build a wavy gradient background for the active scene."""
    top = np.array(scene.palette[0], dtype=np.float32)
    bottom = np.array(scene.palette[1], dtype=np.float32)
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :, None]
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None, None]
    base = top * (1.0 - y) + bottom * y
    wave = np.sin((x * 11.0) + (y * 7.0) + (progress * math.tau * scene.pulse_hz))
    shimmer = np.cos((x * 17.0) - (y * 5.0) + progress * math.tau)
    return np.clip(base + (wave * 18.0) + (shimmer * 9.0), 0, 255).astype(np.uint8)


def _draw_scanlines(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    """Draw faint scanlines to make the frame feel more unstable."""
    for y in range(0, height, 4):
        shade = 32 if (y // 4) % 2 == 0 else 54
        draw.line((0, y, width, y), fill=(shade, shade, shade), width=1)


def _draw_glitch_blocks(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    scene: Scene,
    scene_index: int,
    frame_index: int,
) -> None:
    """Overlay a few deterministic glitch rectangles."""
    rng = np.random.default_rng(scene_index * 1_000 + frame_index)
    for _ in range(12):
        x0 = int(rng.integers(0, max(1, width - 40)))
        y0 = int(rng.integers(0, max(1, height - 24)))
        x1 = min(width, x0 + int(rng.integers(max(8, width // 18), max(24, width // 7))))
        y1 = min(height, y0 + int(rng.integers(2, max(6, height // 24))))
        palette_index = int(rng.integers(0, len(scene.palette)))
        color = np.array(scene.palette[palette_index], dtype=np.int16)
        shift = rng.integers(-36, 37, size=3)
        fill = tuple(np.clip(color + shift, 0, 255).tolist())
        draw.rectangle((x0, y0, x1, y1), fill=fill)


def _draw_scene_text(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    scene: Scene,
    progress: float,
    local_frame: int,
    fps: int,
) -> None:
    """Draw the main phrase and a few jittered overlays."""
    line_index = min(len(scene.lines) - 1, int(progress * len(scene.lines)))
    phrase = scene.lines[line_index]
    font = _fit_font_to_width(
        draw,
        phrase,
        base_size=max(28, height // 9),
        max_width=max(220, width - 120),
    )
    shadow_font = _load_font(max(16, height // 24))
    text_box = draw.textbbox((0, 0), phrase, font=font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    base_x = (width - text_width) // 2
    base_y = (height - text_height) // 2
    jitter = int(round(math.sin(local_frame / max(1.0, fps / 3.0)) * 6.0))
    draw.text((base_x + 8, base_y + 8), phrase, font=font, fill=(10, 10, 10))
    draw.text((base_x + jitter, base_y - jitter), phrase, font=font, fill=(250, 245, 236))

    for event in build_text_events(scene, fps):
        if abs(event.frame - local_frame) > 1:
            continue
        offset = int(round(18 * event.intensity))
        overlay_color = (255, int(180 - 70 * event.intensity), 92)
        draw.text((base_x - offset, base_y + offset), phrase, font=font, fill=overlay_color)

    footer = f"{scene.slug.upper()} // {line_index + 1}/{len(scene.lines)}"
    draw.text((24, height - 54), footer, font=shadow_font, fill=(242, 240, 232))


def _fit_font_to_width(
    draw: ImageDraw.ImageDraw, text: str, base_size: int, max_width: int, min_size: int = 22
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Shrink the font until the phrase fits inside the requested width."""
    size = max(base_size, min_size)
    while size > min_size:
        font = _load_font(size)
        box = draw.textbbox((0, 0), text, font=font)
        if (box[2] - box[0]) <= max_width:
            return font
        size -= 2
    return _load_font(min_size)


def render_project(
    output_dir: Path | str | None = None, config: RenderConfig | None = None, keep_frames: bool = True
) -> RenderPlan:
    """Render the full short and mux it to MP4."""
    render_config = config or RenderConfig()
    storyboard = build_storyboard()
    plan = build_render_plan(storyboard, render_config, output_dir)
    _prepare_output_dirs(plan.paths)
    _render_frames(plan)
    _write_audio(plan)
    _mux_video(plan)
    if not keep_frames:
        for frame_path in plan.paths.frames_dir.glob("frame_*.png"):
            frame_path.unlink()
    return plan


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the generator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for rendered assets")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--sample-rate", type=int, default=24_000)
    parser.add_argument(
        "--drop-frames",
        action="store_true",
        help="Delete intermediate PNG frames after muxing the final MP4",
    )
    args = parser.parse_args(argv)
    config = RenderConfig(
        width=args.width,
        height=args.height,
        fps=args.fps,
        sample_rate=args.sample_rate,
    )
    plan = render_project(args.output_dir, config=config, keep_frames=not args.drop_frames)
    print(f"Rendered video to {plan.paths.video_path}")
    return 0


def _prepare_output_dirs(paths: OutputPaths) -> None:
    """Create the output directories and clear stale frames."""
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.frames_dir.mkdir(parents=True, exist_ok=True)
    for frame_path in paths.frames_dir.glob("frame_*.png"):
        frame_path.unlink()


def _render_frames(plan: RenderPlan) -> None:
    """Render every frame to disk as PNG."""
    for frame_index in range(plan.total_frames):
        image = render_frame(list(plan.storyboard), plan.config, frame_index)
        image.save(_frame_path(plan.paths.frames_dir, frame_index), compress_level=1)


def _write_audio(plan: RenderPlan) -> None:
    """Write the synthesized soundtrack to a mono WAV file."""
    audio = synthesize_audio(list(plan.storyboard), sample_rate=plan.config.sample_rate)
    pcm = quantize_audio(audio)
    with wave.open(str(plan.paths.audio_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(plan.config.sample_rate)
        handle.writeframes(pcm.tobytes())


def _mux_video(plan: RenderPlan) -> None:
    """Invoke ffmpeg to mux the PNG sequence and WAV into the final MP4."""
    command = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(plan.config.fps),
        "-i",
        str(plan.paths.frames_dir / "frame_%05d.png"),
        "-i",
        str(plan.paths.audio_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(plan.paths.video_path),
    ]
    subprocess.run(command, check=True)  # nosec B603 - fixed argv list, no shell, local render tool only


def _frame_path(frames_dir: Path, frame_index: int) -> Path:
    """Build the numbered PNG path for one frame."""
    return frames_dir / f"frame_{frame_index:05d}.png"


@lru_cache(maxsize=8)
def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a bold-ish font if available, otherwise fall back to Pillow default."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/Library/Fonts/Arial Black.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


if __name__ == "__main__":
    raise SystemExit(main())
