from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tldw_Server_API.app.core.TTS.adapters.echo_tts_adapter import EchoTTSAdapter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compute_speaker_latent_loads_reference_audio_via_inference(tmp_path):
    adapter = EchoTTSAdapter(config={"max_reference_seconds": 120})
    temp_path = tmp_path / "reference.wav"
    temp_path.write_bytes(b"wav")

    speaker_audio = Mock()
    speaker_audio.to = Mock(return_value="speaker-audio")
    inference = SimpleNamespace(
        load_audio=Mock(return_value=speaker_audio),
        get_speaker_latent_and_mask=Mock(return_value=("latent", "mask")),
    )
    adapter._echo_inference = inference
    adapter._model = SimpleNamespace(device="cpu")
    adapter._fish_ae = SimpleNamespace(dtype="float32")
    adapter._pca_state = object()
    adapter._write_temp_audio = Mock(return_value=str(temp_path))

    latent, mask = await adapter._compute_speaker_latent(b"voice-bytes")

    assert (latent, mask) == ("latent", "mask")
    adapter._write_temp_audio.assert_called_once_with(b"voice-bytes")
    inference.load_audio.assert_called_once_with(str(temp_path), 120)
    speaker_audio.to.assert_called_once_with(device="cpu", dtype="float32")
    inference.get_speaker_latent_and_mask.assert_called_once_with(
        adapter._fish_ae,
        adapter._pca_state,
        "speaker-audio",
    )
    assert not temp_path.exists()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compute_speaker_latent_removes_temp_audio_when_loader_fails(tmp_path):
    adapter = EchoTTSAdapter(config={})
    temp_path = tmp_path / "reference.wav"
    temp_path.write_bytes(b"wav")

    inference = SimpleNamespace(load_audio=Mock(side_effect=RuntimeError("bad audio")))
    adapter._echo_inference = inference
    adapter._write_temp_audio = Mock(return_value=str(temp_path))
    adapter._model = SimpleNamespace(device="cpu")
    adapter._fish_ae = SimpleNamespace(dtype="float32")
    adapter._pca_state = object()

    with pytest.raises(RuntimeError, match="bad audio"):
        await adapter._compute_speaker_latent(b"voice-bytes")

    assert not temp_path.exists()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compute_speaker_latent_raises_when_inference_missing():
    adapter = EchoTTSAdapter(config={})
    adapter._echo_inference = None

    with pytest.raises(Exception, match="inference module not loaded"):
        await adapter._compute_speaker_latent(b"voice-bytes")
