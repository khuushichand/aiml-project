"""
Tests for voice upload integration with generated files storage.
"""
import shutil
from unittest.mock import AsyncMock

import pytest

from tldw_Server_API.app.core.TTS.voice_manager import VoiceManager, VoiceUploadRequest
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
