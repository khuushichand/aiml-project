import hashlib
import os
import time
from pathlib import Path

import pytest

from tldw_Server_API.app.core.TTS.voice_manager import VoiceManager, VOICE_RATE_LIMITS


class _RuntimeVoiceManager:
    def __init__(self, root: Path, voice_bytes: bytes = b"RIFF" + b"\x00" * 64):
        self.root = root
        self.voice_bytes = voice_bytes

    def get_user_voices_path(self, user_id: int) -> Path:
        assert user_id == 7
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    async def load_voice_reference_audio(self, user_id: int, voice_id: str) -> bytes:
        assert user_id == 7
        assert voice_id == "voice-123"
        return self.voice_bytes


@pytest.mark.asyncio
async def test_pocket_tts_cpp_materializes_stored_voice_to_stable_custom_path(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_custom_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)

    materialized = await materialize_custom_voice_reference(
        voice_manager=manager,
        user_id=7,
        voice_id="voice-123",
    )

    assert materialized == runtime_root / "providers" / "pocket_tts_cpp" / "custom_voice-123.wav"
    assert materialized.exists()
    assert materialized.read_bytes() == manager.voice_bytes


@pytest.mark.asyncio
async def test_pocket_tts_cpp_materializes_direct_reference_to_deterministic_ref_path(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_direct_voice_reference,
    )

    voice_reference = b"RIFF" + b"\x01" * 32
    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)

    materialized, is_transient = await materialize_direct_voice_reference(
        voice_manager=manager,
        user_id=7,
        voice_reference=voice_reference,
        persist_direct_voice_references=True,
    )

    expected_name = f"ref_{hashlib.sha256(voice_reference).hexdigest()}.wav"
    assert materialized == runtime_root / "providers" / "pocket_tts_cpp" / expected_name
    assert materialized.exists()
    assert materialized.read_bytes() == voice_reference
    assert is_transient is False


@pytest.mark.asyncio
async def test_pocket_tts_cpp_materialized_direct_reference_enforces_max_bytes_immediately(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_direct_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)
    runtime_dir = runtime_root / "providers" / "pocket_tts_cpp"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    old_file = runtime_dir / "ref_old.wav"
    old_file.write_bytes(b"old-old")

    materialized, is_transient = await materialize_direct_voice_reference(
        voice_manager=manager,
        user_id=7,
        voice_reference=b"RIFF" + b"\x03" * 8,
        persist_direct_voice_references=True,
        cache_max_bytes=12,
    )

    assert is_transient is False
    assert materialized.exists()
    assert not old_file.exists()
    remaining_files = list(runtime_dir.glob("*.wav"))
    assert remaining_files == [materialized]
    assert sum(path.stat().st_size for path in remaining_files) <= 12


@pytest.mark.asyncio
async def test_pocket_tts_cpp_deletes_transient_direct_reference_when_persistence_disabled(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        cleanup_transient_voice_reference,
        materialize_direct_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)
    materialized, is_transient = await materialize_direct_voice_reference(
        voice_manager=manager,
        user_id=7,
        voice_reference=b"RIFF" + b"\x02" * 16,
        persist_direct_voice_references=False,
    )

    assert is_transient is True
    assert materialized.exists()

    cleanup_transient_voice_reference(materialized, is_transient)

    assert not materialized.exists()


def test_pocket_tts_cpp_prunes_provider_cache_for_ttl_and_oversize_files(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        prune_materialized_voice_cache,
    )

    runtime_dir = tmp_path / "voices" / "providers" / "pocket_tts_cpp"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    expired = runtime_dir / "expired.wav"
    oldest = runtime_dir / "oldest.wav"
    newest = runtime_dir / "newest.wav"
    expired.write_bytes(b"x" * 4)
    oldest.write_bytes(b"y" * 7)
    newest.write_bytes(b"z" * 7)

    now = time.time()
    os.utime(expired, (now - 7200, now - 7200))
    os.utime(oldest, (now - 60, now - 60))
    os.utime(newest, (now - 5, now - 5))

    removed = prune_materialized_voice_cache(
        runtime_dir,
        cache_ttl_hours=1,
        cache_max_bytes=10,
    )

    removed_names = {path.name for path in removed}
    assert removed_names == {"expired.wav", "oldest.wav"}
    assert not expired.exists()
    assert not oldest.exists()
    assert newest.exists()


@pytest.mark.asyncio
async def test_pocket_tts_cpp_provider_cache_is_excluded_from_uploaded_voice_quota(tmp_path, monkeypatch):
    manager = VoiceManager()
    voices_root = tmp_path / "voices"
    processed_dir = voices_root / "processed"
    provider_dir = voices_root / "providers" / "pocket_tts_cpp"
    processed_dir.mkdir(parents=True, exist_ok=True)
    provider_dir.mkdir(parents=True, exist_ok=True)

    processed_file = processed_dir / "user_voice.wav"
    provider_file = provider_dir / "ref_cache.wav"
    processed_file.write_bytes(b"a" * 512)
    provider_file.write_bytes(b"b" * 4096)

    monkeypatch.setattr(manager, "get_user_voices_path", lambda user_id: voices_root, raising=False)
    monkeypatch.setitem(VOICE_RATE_LIMITS, "total_storage_mb", 0.001)
    monkeypatch.setitem(VOICE_RATE_LIMITS, "max_voices_per_user", 10)

    async def _fake_duration(_path: Path) -> float:
        return 1.0

    monkeypatch.setattr(manager, "_get_audio_duration", _fake_duration, raising=False)

    allowed, message = await manager.check_rate_limits(99)

    assert allowed is True
    assert message == ""
