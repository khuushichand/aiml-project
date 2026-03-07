from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tldw_Server_API.app.core.TTS.adapters.echo_tts_adapter import EchoTTSAdapter


@pytest.mark.unit
def test_load_reference_audio_prefers_torchaudio_for_wav_path():
    adapter = EchoTTSAdapter(config={})
    expected_audio = object()
    inference = SimpleNamespace(
        load_audio=Mock(side_effect=AssertionError("inference.load_audio should not be called for WAV")),
    )
    wav_loader = Mock(return_value=expected_audio)
    adapter._load_wav_with_torchaudio = wav_loader

    result = adapter._load_reference_audio(inference, "ref.WAV", 120)

    assert result is expected_audio
    wav_loader.assert_called_once_with("ref.WAV", max_duration=120)


@pytest.mark.unit
def test_load_reference_audio_falls_back_when_torchaudio_path_errors():
    adapter = EchoTTSAdapter(config={})
    expected_audio = object()
    inference = SimpleNamespace(load_audio=Mock(return_value=expected_audio))
    wav_loader = Mock(side_effect=ImportError("torchaudio unavailable"))
    adapter._load_wav_with_torchaudio = wav_loader

    result = adapter._load_reference_audio(inference, "ref.wav", 90)

    assert result is expected_audio
    wav_loader.assert_called_once_with("ref.wav", max_duration=90)
    inference.load_audio.assert_called_once_with("ref.wav", 90)


@pytest.mark.unit
def test_load_reference_audio_uses_inference_loader_for_non_wav():
    adapter = EchoTTSAdapter(config={})
    expected_audio = object()
    inference = SimpleNamespace(load_audio=Mock(return_value=expected_audio))
    wav_loader = Mock()
    adapter._load_wav_with_torchaudio = wav_loader

    result = adapter._load_reference_audio(inference, "ref.mp3", 45)

    assert result is expected_audio
    wav_loader.assert_not_called()
    inference.load_audio.assert_called_once_with("ref.mp3", 45)
