# test_pocket_tts_adapter_integration.py
# Description: Integration tests for PocketTTS ONNX adapter
#
import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.legacy_tts]
RUN_TTS_LEGACY_INTEGRATION = os.getenv("RUN_TTS_LEGACY_INTEGRATION") == "1"

if not RUN_TTS_LEGACY_INTEGRATION:
    pytest.skip(
        "Legacy TTS integration tests are disabled by default. Set RUN_TTS_LEGACY_INTEGRATION=1 to enable.",
        allow_module_level=True,
    )

from tldw_Server_API.app.core.TTS.adapters.pocket_tts_adapter import PocketTTSOnnxAdapter
from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, ProviderStatus, TTSRequest


def _has_runtime_deps() -> bool:
    try:
        import pocket_tts_onnx  # noqa: F401
        import soundfile  # noqa: F401
        import sentencepiece  # noqa: F401
        import onnxruntime  # noqa: F401
        import scipy  # noqa: F401
    except Exception:
        return False
    return True


def _find_assets():
    base_dir = Path("models/pocket_tts_onnx")
    models_dir = base_dir / "onnx"
    tokenizer_path = base_dir / "tokenizer.model"

    if not models_dir.exists() or not tokenizer_path.exists():
        return None

    int8_files = [
        "flow_lm_main_int8.onnx",
        "flow_lm_flow_int8.onnx",
        "mimi_decoder_int8.onnx",
        "mimi_encoder.onnx",
        "text_conditioner.onnx",
    ]
    fp32_files = [
        "flow_lm_main.onnx",
        "flow_lm_flow.onnx",
        "mimi_decoder.onnx",
        "mimi_encoder.onnx",
        "text_conditioner.onnx",
    ]

    if all((models_dir / name).exists() for name in int8_files):
        return models_dir, tokenizer_path, "int8"
    if all((models_dir / name).exists() for name in fp32_files):
        return models_dir, tokenizer_path, "fp32"

    return None


@pytest.mark.asyncio
@pytest.mark.skipif(not _has_runtime_deps(), reason="PocketTTS runtime dependencies not installed")
async def test_pocket_tts_initialize_and_generate():
    assets = _find_assets()
    if not assets:
        pytest.skip("PocketTTS ONNX assets not available under models/pocket_tts_onnx")

    models_dir, tokenizer_path, precision = assets
    voice_path = Path("Helper_Scripts/Audio/Sample_Voices/Sample_Voice_1.wav")
    if not voice_path.exists():
        pytest.skip("Sample voice reference not available")

    adapter = PocketTTSOnnxAdapter(
        {
            "model_path": str(models_dir),
            "tokenizer_path": str(tokenizer_path),
            "precision": precision,
            "device": "cpu",
        }
    )

    success = await adapter.initialize()
    assert success is True
    assert adapter.status == ProviderStatus.AVAILABLE

    request = TTSRequest(
        text="Hello from PocketTTS.",
        voice="clone",
        format=AudioFormat.PCM,
        stream=False,
        voice_reference=voice_path.read_bytes(),
        extra_params={
            "max_frames": 2,
            "validate_reference": False,
            "convert_reference": False,
        },
    )

    response = await adapter.generate(request)
    assert response.audio_data is not None
    assert len(response.audio_data) > 0

    await adapter.close()
