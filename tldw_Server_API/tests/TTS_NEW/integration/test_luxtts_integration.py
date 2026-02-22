# Integration test for LuxTTS initialization and generation.
#
# This test only runs when RUN_LUXTTS_INTEGRATION=1 and a LuxTTS checkout
# is available (default ../LuxTTS or LUX_TTS_MODULE_PATH override). It also
# requires the LuxTTS model to be cached locally (no network).

import os
import sys
import warnings
from pathlib import Path

import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.luxtts_adapter import LuxTTSAdapter

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

RUN_LUXTTS_INTEGRATION = os.getenv("RUN_LUXTTS_INTEGRATION") == "1"


def _resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolve_lux_module_path() -> Path:
    env_path = os.getenv("LUX_TTS_MODULE_PATH")
    if env_path:
        return Path(env_path).expanduser()
    repo_root = _resolve_repo_root()
    return repo_root / "LuxTTS"


def _resolve_voice_reference_path() -> Path:
    repo_root = _resolve_repo_root()
    return repo_root / "tldw_Server_API/tests/Media_Ingestion_Modification/test_media/sample.wav"


def _require_hf_cache(repo_id: str) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        warnings.warn("huggingface_hub not installed; skipping LuxTTS integration test.")
        pytest.skip("huggingface_hub not installed")

    try:
        snapshot_path = Path(
            snapshot_download(  # nosec B615
                repo_id=repo_id,
                local_files_only=True,
            )
        )
    except TypeError as exc:
        warnings.warn(f"huggingface_hub snapshot_download does not support local_files_only: {exc}")
        pytest.skip("huggingface_hub too old for local-only cache check")
    except Exception as exc:
        warnings.warn(f"LuxTTS model not cached locally for {repo_id}: {exc}")
        pytest.skip("LuxTTS model not cached locally")

    return snapshot_path


@pytest.mark.requires_model
async def test_luxtts_generate_cached_model(monkeypatch):
    if not RUN_LUXTTS_INTEGRATION:
        pytest.skip("RUN_LUXTTS_INTEGRATION not set")

    module_path = _resolve_lux_module_path()
    if not module_path.exists():
        pytest.skip("LuxTTS module not found; set LUX_TTS_MODULE_PATH to your LuxTTS checkout")

    module_path_str = str(module_path)
    if module_path_str not in sys.path:
        sys.path.insert(0, module_path_str)

    voice_path = _resolve_voice_reference_path()
    if not voice_path.exists():
        pytest.skip("Sample voice reference not found")

    model_id = os.getenv("LUX_TTS_MODEL_ID", "YatharthS/LuxTTS")
    model_path_override = os.getenv("LUX_TTS_MODEL_PATH")
    if model_path_override:
        model_path = Path(model_path_override).expanduser()
        if not model_path.exists():
            pytest.skip("LUX_TTS_MODEL_PATH does not exist")
        model_path_str = str(model_path)
    else:
        _require_hf_cache(model_id)
        model_path_str = model_id

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    adapter = LuxTTSAdapter(
        config={
            "lux_tts_module_path": module_path_str,
            "model": model_path_str,
            "device": "cpu",
        }
    )

    request = TTSRequest(
        text="Hello from LuxTTS integration.",
        format=AudioFormat.WAV,
        stream=False,
        voice_reference=voice_path.read_bytes(),
    )

    response = await adapter.generate(request)
    assert response.audio_data is not None
    assert len(response.audio_data) > 0
    assert response.provider == adapter.PROVIDER_KEY

    await adapter.close()
