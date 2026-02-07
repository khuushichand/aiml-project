"""
Tests for voice upload integration with generated files storage.
"""
import shutil
from unittest.mock import AsyncMock

import pytest

from tldw_Server_API.app.core.TTS.voice_manager import (
    VoiceInfo,
    VoiceManager,
    VoiceReferenceMetadata,
    VoiceUploadRequest,
)
from tldw_Server_API.app.core.AuthNZ.repos.generated_files_repo import FILE_CATEGORY_VOICE_CLONE
from tldw_Server_API.app.core.AuthNZ.exceptions import QuotaExceededError
from tldw_Server_API.app.core.TTS.voice_manager import VoiceQuotaExceededError
from tldw_Server_API.app.core.TTS import voice_manager as voice_manager_module


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_voice_registers_generated_file(tmp_path, monkeypatch):
    """Voice upload registers a generated file entry."""
    manager = VoiceManager()
    voices_path = tmp_path / "voices"
    voices_path.mkdir(parents=True, exist_ok=True)
    (voices_path / "uploads").mkdir(parents=True, exist_ok=True)
    (voices_path / "processed").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(manager, "get_user_voices_path", lambda user_id: voices_path)

    async def _process_for_provider(src, dst, provider):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        return dst

    monkeypatch.setattr(manager, "_process_for_provider", _process_for_provider)
    monkeypatch.setattr(manager, "_get_audio_duration", AsyncMock(return_value=5.0))
    manager.registry.register_voice = AsyncMock()

    mock_storage = AsyncMock()
    mock_storage.register_generated_file = AsyncMock(return_value={"id": 1})

    async def _get_storage_service():
        return mock_storage

    monkeypatch.setattr(voice_manager_module, "get_storage_service", _get_storage_service)

    req = VoiceUploadRequest(name="Test Voice", description=None, provider="vibevoice", reference_text=None)
    await manager.upload_voice(user_id=1, file_content=b"RIFFDATA", filename="sample.wav", request=req)

    assert mock_storage.register_generated_file.await_count == 1
    call_kwargs = mock_storage.register_generated_file.call_args[1]
    assert call_kwargs["file_category"] == FILE_CATEGORY_VOICE_CLONE
    assert call_kwargs["user_id"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_voice_quota_exceeded_maps_to_voice_quota(monkeypatch, tmp_path):
    """QuotaExceededError from storage maps to VoiceQuotaExceededError."""
    manager = VoiceManager()
    voices_path = tmp_path / "voices"
    voices_path.mkdir(parents=True, exist_ok=True)
    (voices_path / "uploads").mkdir(parents=True, exist_ok=True)
    (voices_path / "processed").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(manager, "get_user_voices_path", lambda user_id: voices_path)
    monkeypatch.setattr(manager, "_get_audio_duration", AsyncMock(return_value=5.0))

    async def _process_for_provider(src, dst, provider):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        return dst

    monkeypatch.setattr(manager, "_process_for_provider", _process_for_provider)
    manager.registry.register_voice = AsyncMock()

    mock_storage = AsyncMock()
    mock_storage.register_generated_file = AsyncMock(
        side_effect=QuotaExceededError(20.0, 10)
    )

    async def _get_storage_service():
        return mock_storage

    monkeypatch.setattr(voice_manager_module, "get_storage_service", _get_storage_service)

    req = VoiceUploadRequest(name="Test Voice", description=None, provider="vibevoice", reference_text=None)
    with pytest.raises(VoiceQuotaExceededError):
        await manager.upload_voice(user_id=1, file_content=b"RIFFDATA", filename="sample.wav", request=req)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_voice_unregisters_generated_file_and_metadata(monkeypatch, tmp_path):
    """Deleting a voice removes metadata and unregisters matching generated_files records."""
    manager = VoiceManager()
    voices_path = tmp_path / "voices"
    voices_path.mkdir(parents=True, exist_ok=True)
    (voices_path / "uploads").mkdir(parents=True, exist_ok=True)
    (voices_path / "processed").mkdir(parents=True, exist_ok=True)
    (voices_path / "metadata").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(manager, "get_user_voices_path", lambda user_id: voices_path)
    monkeypatch.setattr(manager, "_get_audio_duration", AsyncMock(return_value=5.0))

    user_id = 42
    voice_id = "voice-delete"
    processed_path = voices_path / "processed" / f"{voice_id}.wav"
    upload_path = voices_path / "uploads" / f"{voice_id}_sample.wav"
    processed_path.write_bytes(b"RIFFDATA")
    upload_path.write_bytes(b"RIFFDATA")

    voice_info = VoiceInfo(
        voice_id=voice_id,
        name="to-delete",
        description=None,
        file_path=str(processed_path.relative_to(voices_path)),
        format="wav",
        duration=5.0,
        sample_rate=22050,
        size_bytes=processed_path.stat().st_size,
        provider="vibevoice",
        created_at=voice_manager_module.datetime.utcnow(),
        file_hash="hash",
    )
    await manager.registry.register_voice(user_id, voice_info)

    metadata = VoiceReferenceMetadata(voice_id=voice_id, reference_text="hello")
    await manager.save_reference_metadata(user_id, metadata)
    metadata_path = manager.get_user_voice_metadata_path(user_id, voice_id)
    assert metadata_path.exists()

    mock_storage = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.list_files = AsyncMock(
        return_value=(
            [
                {
                    "id": 123,
                    "storage_path": str(processed_path.relative_to(voices_path)),
                    "file_category": FILE_CATEGORY_VOICE_CLONE,
                }
            ],
            1,
        )
    )
    mock_storage.get_generated_files_repo = AsyncMock(return_value=mock_repo)
    mock_storage.unregister_generated_file = AsyncMock(return_value=True)

    async def _get_storage_service():
        return mock_storage

    monkeypatch.setattr(voice_manager_module, "get_storage_service", _get_storage_service)

    deleted = await manager.delete_voice(user_id=user_id, voice_id=voice_id)
    assert deleted is True
    assert not processed_path.exists()
    assert not upload_path.exists()
    assert not metadata_path.exists()
    mock_storage.unregister_generated_file.assert_awaited_once_with(123, hard_delete=True)
