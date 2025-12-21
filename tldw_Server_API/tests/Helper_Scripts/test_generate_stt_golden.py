"""Tests for the STT golden helper script utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from Helper_Scripts.Audio import generate_stt_golden as script


class DummyAdapter:
    """Stub adapter that returns a fixed transcript for tests."""

    def transcribe_batch(self, audio_path: str, **kwargs) -> dict:
        return {
            "text": "Hello world",
            "segments": [{"Text": "Hello world"}],
        }


def test_resolve_audio_path_relative(tmp_path: Path) -> None:
    """_resolve_audio_path should accept base-dir relative audio paths."""
    base_dir = tmp_path / "golden"
    audio_path = base_dir / "audio" / "clip.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"data")

    resolved, rel_audio = script._resolve_audio_path(audio_path.relative_to(base_dir), base_dir)

    assert resolved == audio_path.resolve()
    assert rel_audio == "audio/clip.wav"


def test_resolve_audio_path_outside_base(tmp_path: Path) -> None:
    """_resolve_audio_path should reject files outside the base dir."""
    base_dir = tmp_path / "golden"
    base_dir.mkdir()
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"data")

    with pytest.raises(ValueError):
        script._resolve_audio_path(audio_path, base_dir)


def test_generate_golden_payload_includes_optional_fields(tmp_path: Path) -> None:
    """_generate_golden_payload should include optional thresholds when provided."""
    adapter = DummyAdapter()
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"data")

    payload = script._generate_golden_payload(
        adapter,
        audio_path,
        "audio/clip.wav",
        model="demo-model",
        language="en",
        max_token_error_rate=0.1,
        min_segments=2,
    )

    assert payload["audio"] == "audio/clip.wav"
    assert payload["model"] == "demo-model"
    assert payload["expected_text"] == "Hello world"
    assert payload["language"] == "en"
    assert payload["max_token_error_rate"] == 0.1
    assert payload["min_segments"] == 2


def test_write_golden_json(tmp_path: Path) -> None:
    """_write_golden_json should persist the payload as JSON."""
    payload = {
        "audio": "audio/clip.wav",
        "model": "demo-model",
        "expected_text": "Hello world",
    }
    output_path = tmp_path / "whisper_clip1.golden.json"

    script._write_golden_json(output_path, payload)

    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded == payload
