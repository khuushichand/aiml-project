"""
Unit tests for VoiceManager upload/delete lifecycle and duration handling.

These tests exercise VoiceManager without relying on external ffmpeg/ffprobe
executables by patching the internal duration/processing helpers.
"""

import os
import asyncio
from pathlib import Path
from typing import List

import pytest

from tldw_Server_API.app.core.TTS.voice_manager import (
    VoiceManager,
    VoiceUploadRequest,
    VoiceDurationError,
    PROVIDER_REQUIREMENTS,
)


@pytest.mark.asyncio
async def test_upload_and_delete_voice_happy_path(tmp_path, monkeypatch):
    """
    Upload a valid voice sample and then delete it, ensuring files and
    registry entries are cleaned up correctly for a provider profile.
    """
    manager = VoiceManager()

    # Ensure VoiceManager writes into a temporary user DB base dir
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

    voices_root = tmp_path / "voices"

    def _fake_user_db_base_dir(*, allow_legacy_alias: bool = False):
        return tmp_path

    def _fake_user_voices_dir(user_id):
        voices_root.mkdir(parents=True, exist_ok=True)
        (voices_root / "uploads").mkdir(parents=True, exist_ok=True)
        (voices_root / "processed").mkdir(parents=True, exist_ok=True)
        (voices_root / "temp").mkdir(parents=True, exist_ok=True)
        return voices_root

    monkeypatch.setattr(DatabasePaths, "get_user_db_base_dir", _fake_user_db_base_dir, raising=True)
    monkeypatch.setattr(DatabasePaths, "get_user_voices_dir", _fake_user_voices_dir, raising=True)

    # Patch duration and processing helpers to be deterministic and fast
    async def fake_duration(path: Path) -> float:  # type: ignore[override]
        # Choose a duration within the recommended range for vibevoice
        reqs = PROVIDER_REQUIREMENTS.get("vibevoice", {})
        return float(reqs.get("duration", {}).get("min", 3.0)) + 0.5

    async def fake_process_for_provider(input_path: Path, output_path: Path, provider: str) -> Path:  # type: ignore[override]
        output_path = output_path.with_suffix(".wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return output_path

    monkeypatch.setattr(manager, "_get_audio_duration", fake_duration, raising=False)
    monkeypatch.setattr(manager, "_process_for_provider", fake_process_for_provider, raising=False)

    # Build a small WAV-like payload; provider is vibevoice
    file_bytes = b"RIFF" + b"\x00" * 1000
    request = VoiceUploadRequest(name="test-voice", description="unit test", provider="vibevoice")

    # Upload
    resp = await manager.upload_voice(
        user_id=1,
        file_content=file_bytes,
        filename="sample.wav",
        request=request,
    )

    assert resp.voice_id
    assert resp.provider_compatible is True
    assert resp.warnings == []
    assert Path(resp.file_path).exists()

    # Delete and ensure files are removed
    deleted = await manager.delete_voice(user_id=1, voice_id=resp.voice_id)
    assert deleted

    voices_root = manager.get_user_voices_path(1)
    processed_dir = voices_root / "processed"
    uploads_dir = voices_root / "uploads"
    # No processed file with this voice_id should remain
    remaining: List[Path] = list(processed_dir.glob(f"{resp.voice_id}*")) if processed_dir.exists() else []
    assert not remaining
    leftovers: List[Path] = list(uploads_dir.glob(f"{resp.voice_id}_*")) if uploads_dir.exists() else []
    assert not leftovers


@pytest.mark.asyncio
async def test_upload_voice_short_duration_warning_and_strict_mode(tmp_path, monkeypatch):
    """
    When duration is outside provider requirements, uploads should:
    - succeed with warnings by default
    - raise VoiceDurationError when TTS_VOICE_STRICT_DURATION is true.
    """
    manager = VoiceManager()

    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

    voices_root = tmp_path / "voices"

    def _fake_user_db_base_dir(*, allow_legacy_alias: bool = False):
        return tmp_path

    def _fake_user_voices_dir(user_id):
        voices_root.mkdir(parents=True, exist_ok=True)
        (voices_root / "uploads").mkdir(parents=True, exist_ok=True)
        (voices_root / "processed").mkdir(parents=True, exist_ok=True)
        (voices_root / "temp").mkdir(parents=True, exist_ok=True)
        return voices_root

    monkeypatch.setattr(DatabasePaths, "get_user_db_base_dir", _fake_user_db_base_dir, raising=True)
    monkeypatch.setattr(DatabasePaths, "get_user_voices_dir", _fake_user_voices_dir, raising=True)

    # Force a duration that is too short for higgs
    async def fake_short_duration(path: Path) -> float:  # type: ignore[override]
        return 0.5

    async def fake_process_for_provider(input_path: Path, output_path: Path, provider: str) -> Path:  # type: ignore[override]
        output_path = output_path.with_suffix(".wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return output_path

    monkeypatch.setattr(manager, "_get_audio_duration", fake_short_duration, raising=False)
    monkeypatch.setattr(manager, "_process_for_provider", fake_process_for_provider, raising=False)

    file_bytes = b"RIFF" + b"\x00" * 1000
    request = VoiceUploadRequest(name="short-voice", description=None, provider="higgs")

    # Non-strict mode (default: env not set) -> accepted with warning
    monkeypatch.delenv("TTS_VOICE_STRICT_DURATION", raising=False)
    resp = await manager.upload_voice(
        user_id=42,
        file_content=file_bytes,
        filename="short.wav",
        request=request,
    )
    assert resp.provider_compatible is False
    assert any("less than recommended" in w for w in resp.warnings)

    # Strict mode -> raises VoiceDurationError
    # Clean up quota tracking for a fresh upload
    manager.user_upload_counts.clear()
    monkeypatch.setenv("TTS_VOICE_STRICT_DURATION", "true")

    with pytest.raises(VoiceDurationError):
        await manager.upload_voice(
            user_id=42,
            file_content=file_bytes,
            filename="short_again.wav",
            request=request,
        )
