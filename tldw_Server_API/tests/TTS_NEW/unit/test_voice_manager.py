"""
Unit tests for VoiceManager upload/delete lifecycle and duration handling.

These tests exercise VoiceManager without relying on external ffmpeg/ffprobe
executables by patching the internal duration/processing helpers.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List

import pytest

from tldw_Server_API.app.core.TTS.voice_manager import (
    VoiceManager,
    VoiceUploadRequest,
    VoiceDurationError,
    VoiceInfo,
    PROVIDER_REQUIREMENTS,
    VoiceReferenceMetadata,
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


@pytest.mark.asyncio
async def test_delete_voice_rejects_path_traversal(tmp_path, monkeypatch):
    """Delete should refuse to remove files outside the voices directory."""
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

    outside_file = tmp_path / "outside.wav"
    outside_file.write_bytes(b"not a voice sample")

    voice_info = VoiceInfo(
        voice_id="malicious-id",
        name="malicious",
        description=None,
        file_path="../outside.wav",
        format="wav",
        duration=1.0,
        sample_rate=None,
        size_bytes=outside_file.stat().st_size,
        provider="vibevoice",
        created_at=datetime.utcnow(),
        file_hash="",
    )

    await manager.registry.register_voice(user_id=7, voice_info=voice_info)

    deleted = await manager.delete_voice(user_id=7, voice_id="malicious-id")
    assert deleted is False
    assert outside_file.exists()


@pytest.mark.asyncio
async def test_reference_metadata_round_trip(tmp_path, monkeypatch):
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

    metadata = VoiceReferenceMetadata(
        voice_id="voice-123",
        reference_text="Reference text",
        provider_artifacts={"neutts": {"ref_codes": [1, 2, 3]}},
    )
    await manager.save_reference_metadata(user_id=1, metadata=metadata)

    loaded = await manager.load_reference_metadata(user_id=1, voice_id="voice-123")
    assert loaded is not None
    assert loaded.voice_id == metadata.voice_id
    assert loaded.reference_text == metadata.reference_text
    assert loaded.provider_artifacts["neutts"]["ref_codes"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_encode_voice_reference_stores_artifacts(tmp_path, monkeypatch):
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

    voice_id = "voice-encode"
    processed_path = voices_root / "processed" / f"{voice_id}.wav"
    processed_path.write_bytes(b"RIFF" + b"\x00" * 1000)

    voice_info = VoiceInfo(
        voice_id=voice_id,
        name="encode-voice",
        description=None,
        file_path=str(processed_path.relative_to(voices_root)),
        format="wav",
        duration=3.5,
        sample_rate=16000,
        size_bytes=processed_path.stat().st_size,
        provider="neutts",
        created_at=datetime.utcnow(),
        file_hash="",
    )

    await manager.registry.register_voice(user_id=1, voice_info=voice_info)

    async def _fake_encode(audio_path: Path) -> List[int]:
        assert audio_path == processed_path
        return [10, 20, 30]

    monkeypatch.setattr(manager, "_encode_neutts_reference", _fake_encode, raising=False)

    result = await manager.encode_voice_reference(
        user_id=1,
        voice_id=voice_id,
        provider="neutts",
        reference_text="Hello there",
    )
    assert result.cached is False
    assert result.ref_codes_len == 3
    assert result.reference_text == "Hello there"

    cached = await manager.encode_voice_reference(
        user_id=1,
        voice_id=voice_id,
        provider="neutts",
    )
    assert cached.cached is True
    assert cached.ref_codes_len == 3
