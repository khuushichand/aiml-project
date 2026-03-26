import hashlib
import os
import time
import wave
from io import BytesIO
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


def _make_wav_bytes(
    payload: bytes = b"\x00\x01" * 8,
    *,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(payload)
    return buffer.getvalue()


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
    from tldw_Server_API.app.core.TTS.adapters import pocket_tts_cpp_runtime as runtime_module
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_direct_voice_reference,
    )

    voice_reference = b"RIFF" + b"\x01" * 32
    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)
    normalized = _make_wav_bytes(b"\x01\x02" * 8)

    async def _fake_convert(input_path: Path, output_path: Path, sample_rate: int, channels: int, bit_depth: int) -> bool:
        assert input_path.read_bytes() == voice_reference
        assert sample_rate == 24000
        assert channels == 1
        assert bit_depth == 16
        output_path.write_bytes(normalized)
        return True

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runtime_module.AudioConverter, "convert_to_wav", _fake_convert)
    try:
        materialized, is_transient = await materialize_direct_voice_reference(
            voice_manager=manager,
            user_id=7,
            voice_reference=voice_reference,
            persist_direct_voice_references=True,
        )
    finally:
        monkeypatch.undo()

    expected_name = f"ref_{hashlib.sha256(normalized).hexdigest()}.wav"
    assert materialized == runtime_root / "providers" / "pocket_tts_cpp" / expected_name
    assert materialized.exists()
    assert materialized.read_bytes() == normalized
    assert is_transient is False


@pytest.mark.asyncio
async def test_pocket_tts_cpp_normalizes_non_wav_direct_reference_before_materialization(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters import pocket_tts_cpp_runtime as runtime_module
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_direct_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)
    mp3_like_bytes = b"ID3" + b"\x04" * 17
    normalized = _make_wav_bytes(b"\x04\x05" * 12)
    converter_calls: list[tuple[Path, Path]] = []

    async def _fake_convert(input_path: Path, output_path: Path, sample_rate: int, channels: int, bit_depth: int) -> bool:
        converter_calls.append((input_path, output_path))
        assert input_path.read_bytes() == mp3_like_bytes
        assert sample_rate == 24000
        assert channels == 1
        assert bit_depth == 16
        output_path.write_bytes(normalized)
        return True

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runtime_module.AudioConverter, "convert_to_wav", _fake_convert)
    try:
        materialized, is_transient = await materialize_direct_voice_reference(
            voice_manager=manager,
            user_id=7,
            voice_reference=mp3_like_bytes,
            persist_direct_voice_references=True,
        )
    finally:
        monkeypatch.undo()

    expected_name = f"ref_{hashlib.sha256(normalized).hexdigest()}.wav"
    assert materialized == runtime_root / "providers" / "pocket_tts_cpp" / expected_name
    assert is_transient is False
    assert len(converter_calls) == 1
    assert materialized.read_bytes() == normalized
    with wave.open(str(materialized), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 24000


@pytest.mark.asyncio
async def test_pocket_tts_cpp_transient_direct_references_use_unique_request_scoped_paths(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters import pocket_tts_cpp_runtime as runtime_module
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_direct_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)
    voice_reference = b"RIFF" + b"\x07" * 32
    normalized = _make_wav_bytes(b"\x07\x08" * 10)

    async def _fake_convert(input_path: Path, output_path: Path, sample_rate: int, channels: int, bit_depth: int) -> bool:
        output_path.write_bytes(normalized)
        return True

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runtime_module.AudioConverter, "convert_to_wav", _fake_convert)
    try:
        first_path, first_transient = await materialize_direct_voice_reference(
            voice_manager=manager,
            user_id=7,
            voice_reference=voice_reference,
            persist_direct_voice_references=False,
        )
        second_path, second_transient = await materialize_direct_voice_reference(
            voice_manager=manager,
            user_id=7,
            voice_reference=voice_reference,
            persist_direct_voice_references=False,
        )
    finally:
        monkeypatch.undo()

    assert first_transient is True
    assert second_transient is True
    assert first_path != second_path
    assert first_path.exists()
    assert second_path.exists()


@pytest.mark.asyncio
async def test_pocket_tts_cpp_materialized_direct_reference_enforces_max_bytes_immediately(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters import pocket_tts_cpp_runtime as runtime_module
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_direct_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)
    runtime_dir = runtime_root / "providers" / "pocket_tts_cpp"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    old_file = runtime_dir / "ref_old.wav"
    old_file.write_bytes(b"old-old")
    normalized = _make_wav_bytes(b"\x03\x03")

    async def _fake_convert(input_path: Path, output_path: Path, sample_rate: int, channels: int, bit_depth: int) -> bool:
        output_path.write_bytes(normalized)
        return True

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runtime_module.AudioConverter, "convert_to_wav", _fake_convert)
    try:
        materialized, is_transient = await materialize_direct_voice_reference(
            voice_manager=manager,
            user_id=7,
            voice_reference=b"RIFF" + b"\x03" * 8,
            persist_direct_voice_references=True,
            cache_max_bytes=12,
        )
    finally:
        monkeypatch.undo()

    assert is_transient is False
    assert materialized.exists()
    assert not old_file.exists()
    remaining_files = list(runtime_dir.glob("*.wav"))
    assert remaining_files == [materialized]
    assert sum(path.stat().st_size for path in remaining_files) == materialized.stat().st_size


@pytest.mark.asyncio
async def test_pocket_tts_cpp_post_write_pruning_never_returns_deleted_active_path(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters import pocket_tts_cpp_runtime as runtime_module
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_direct_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)
    runtime_dir = runtime_root / "providers" / "pocket_tts_cpp"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    stale_file = runtime_dir / "ref_stale.wav"
    stale_file.write_bytes(b"old-old-old-old")
    normalized = _make_wav_bytes(b"\x09\x09" * 2)

    async def _fake_convert(input_path: Path, output_path: Path, sample_rate: int, channels: int, bit_depth: int) -> bool:
        output_path.write_bytes(normalized)
        return True

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runtime_module.AudioConverter, "convert_to_wav", _fake_convert)
    try:
        materialized, is_transient = await materialize_direct_voice_reference(
            voice_manager=manager,
            user_id=7,
            voice_reference=b"RIFF" + b"\x09" * 20,
            persist_direct_voice_references=True,
            cache_max_bytes=8,
        )
    finally:
        monkeypatch.undo()

    assert is_transient is False
    assert materialized.exists()
    assert not stale_file.exists()
    assert materialized in runtime_dir.glob("*.wav")


@pytest.mark.asyncio
async def test_pocket_tts_cpp_custom_voice_materialization_enforces_max_bytes_immediately(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        materialize_custom_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root, voice_bytes=b"RIFF" + b"\x05" * 12)
    runtime_dir = runtime_root / "providers" / "pocket_tts_cpp"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    old_file = runtime_dir / "ref_old.wav"
    old_file.write_bytes(b"old-old")

    materialized = await materialize_custom_voice_reference(
        voice_manager=manager,
        user_id=7,
        voice_id="voice-123",
        cache_max_bytes=20,
    )

    assert materialized.exists()
    assert not old_file.exists()
    assert materialized in runtime_dir.glob("*.wav")
    assert sum(path.stat().st_size for path in runtime_dir.glob("*.wav")) <= 20 or list(runtime_dir.glob("*.wav")) == [materialized]


@pytest.mark.asyncio
async def test_pocket_tts_cpp_deletes_transient_direct_reference_when_persistence_disabled(tmp_path):
    from tldw_Server_API.app.core.TTS.adapters import pocket_tts_cpp_runtime as runtime_module
    from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_runtime import (
        cleanup_transient_voice_reference,
        materialize_direct_voice_reference,
    )

    runtime_root = tmp_path / "voices"
    manager = _RuntimeVoiceManager(runtime_root)
    normalized = _make_wav_bytes(b"\x02\x02" * 8)

    async def _fake_convert(input_path: Path, output_path: Path, sample_rate: int, channels: int, bit_depth: int) -> bool:
        output_path.write_bytes(normalized)
        return True

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runtime_module.AudioConverter, "convert_to_wav", _fake_convert)
    materialized, is_transient = await materialize_direct_voice_reference(
        voice_manager=manager,
        user_id=7,
        voice_reference=b"RIFF" + b"\x02" * 16,
        persist_direct_voice_references=False,
    )
    monkeypatch.undo()

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
