from pathlib import Path

import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2
from tldw_Server_API.app.core.TTS.voice_manager import VoiceReferenceMetadata


class _ServiceVoiceManager:
    def __init__(self, root: Path):
        self.root = root

    def get_user_voices_path(self, user_id: int) -> Path:
        assert user_id == 1
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    async def load_voice_reference_audio(self, user_id: int, voice_id: str) -> bytes:
        assert user_id == 1
        assert voice_id == "voice-1"
        return b"RIFF" + b"\x00" * 32

    async def load_reference_metadata(self, user_id: int, voice_id: str):
        assert user_id == 1
        assert voice_id == "voice-1"
        return VoiceReferenceMetadata(
            voice_id=voice_id,
            reference_text="stored reference text",
        )


@pytest.mark.asyncio
async def test_pocket_tts_cpp_service_injects_stable_path_for_custom_voice(tmp_path, monkeypatch):
    service = TTSServiceV2()
    manager = _ServiceVoiceManager(tmp_path / "voices")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.voice_manager.get_voice_manager",
        lambda: manager,
        raising=True,
    )

    request = TTSRequest(
        text="hello",
        voice="custom:voice-1",
        format=AudioFormat.WAV,
        extra_params={},
    )

    await service._apply_custom_voice_reference(request, user_id=1, provider_hint="pocket_tts_cpp")

    expected = tmp_path / "voices" / "providers" / "pocket_tts_cpp" / "custom_voice-1.wav"
    assert request.voice_reference == b"RIFF" + b"\x00" * 32
    assert request.extra_params["pocket_tts_cpp_voice_path"] == str(expected)
    assert request.extra_params["pocket_tts_cpp_reference_text"] == "stored reference text"
    assert expected.exists()


@pytest.mark.asyncio
async def test_pocket_tts_cpp_service_injects_stable_path_for_direct_voice_reference(tmp_path):
    service = TTSServiceV2()
    request = TTSRequest(
        text="hello",
        voice="alloy",
        format=AudioFormat.WAV,
        voice_reference=b"RIFF" + b"\x01" * 24,
        extra_params={"reference_text": "direct reference text"},
    )

    class _DirectReferenceVoiceManager:
        def get_user_voices_path(self, user_id: int) -> Path:
            assert user_id == 1
            root = tmp_path / "voices"
            root.mkdir(parents=True, exist_ok=True)
            return root

        async def load_reference_metadata(self, user_id: int, voice_id: str):
            return None

    from tldw_Server_API.app.core.TTS import voice_manager as voice_manager_module

    original_get_voice_manager = voice_manager_module.get_voice_manager
    voice_manager_module.get_voice_manager = lambda: _DirectReferenceVoiceManager()
    try:
        await service._apply_custom_voice_reference(request, user_id=1, provider_hint="pocket_tts_cpp")
    finally:
        voice_manager_module.get_voice_manager = original_get_voice_manager

    voice_path = Path(request.extra_params["pocket_tts_cpp_voice_path"])
    assert voice_path.parent == tmp_path / "voices" / "providers" / "pocket_tts_cpp"
    assert voice_path.name.startswith("ref_")
    assert voice_path.suffix == ".wav"
    assert request.extra_params["pocket_tts_cpp_reference_text"] == "direct reference text"
    assert voice_path.exists()
