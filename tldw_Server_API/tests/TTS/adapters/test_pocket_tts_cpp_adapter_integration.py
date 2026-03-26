# test_pocket_tts_cpp_adapter_integration.py
# Description: Opt-in integration test skeleton for PocketTTS.cpp CLI adapter
#
import os
from pathlib import Path

import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_adapter import PocketTTSCppAdapter


pytestmark = pytest.mark.integration
RUN_TTS_CPP_INTEGRATION = os.getenv("RUN_TTS_CPP_INTEGRATION") == "1"

if not RUN_TTS_CPP_INTEGRATION:
    pytest.skip(
        "PocketTTS.cpp integration tests are disabled by default. Set RUN_TTS_CPP_INTEGRATION=1 to enable.",
        allow_module_level=True,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolve_assets() -> tuple[Path, Path, Path] | None:
    root = _repo_root()
    binary_path = root / "bin" / "pocket-tts"
    model_path = root / "models" / "pocket_tts_cpp" / "onnx"
    tokenizer_path = root / "models" / "pocket_tts_cpp" / "tokenizer.model"

    if not binary_path.exists() or not model_path.exists() or not tokenizer_path.exists():
        return None

    return binary_path, model_path, tokenizer_path


@pytest.mark.asyncio
async def test_pocket_tts_cpp_initialize_and_synthesize_short_request():
    assets = _resolve_assets()
    if assets is None:
        pytest.skip("PocketTTS.cpp binary or models are not available")

    binary_path, model_path, tokenizer_path = assets
    sample_voice = _repo_root() / "Helper_Scripts" / "Audio" / "Sample_Voices" / "Sample_Voice_1.wav"
    if not sample_voice.exists():
        pytest.skip("PocketTTS.cpp sample voice file is not available")

    adapter = PocketTTSCppAdapter(
        {
            "binary_path": str(binary_path),
            "model_path": str(model_path),
            "tokenizer_path": str(tokenizer_path),
            "timeout": 60,
            "prefer_stdout": True,
        }
    )

    assert await adapter.initialize() is True

    request = TTSRequest(
        text="Hi.",
        voice="custom:sample",
        format=AudioFormat.PCM,
        stream=False,
        voice_reference=sample_voice.read_bytes(),
        extra_params={"pocket_tts_cpp_voice_path": str(sample_voice)},
    )

    response = await adapter.generate(request)

    assert response.audio_data is not None
    assert len(response.audio_data) > 0
    assert response.metadata.get("transport") in {"stdout", "file"}
