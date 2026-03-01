# Integration test for Echo-TTS initialization on CUDA.
#
# This test only runs when CUDA is available and the Echo-TTS module checkout
# is present (default ../echo-tts or ECHO_TTS_MODULE_PATH override).

import os
import sys
import warnings
from pathlib import Path

import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, ProviderStatus, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.echo_tts_adapter import EchoTTSAdapter


torch = pytest.importorskip("torch")

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _resolve_echo_module_path() -> Path:
    env_path = os.getenv("ECHO_TTS_MODULE_PATH")
    if env_path:
        return Path(env_path).expanduser()
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "echo-tts"


def _resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _echo_modules_present(module_path: Path) -> bool:
    return (module_path / "inference.py").exists() and (module_path / "inference_blockwise.py").exists()


def _resolve_voice_reference_path() -> Path:
    repo_root = _resolve_repo_root()
    return repo_root / "tldw_Server_API/tests/Media_Ingestion_Modification/test_media/sample.wav"


def _require_hf_cache(repo_id: str, *, required_files: list[str] | None = None) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        warnings.warn("huggingface_hub not installed; skipping Echo-TTS CUDA generation test.")
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
        warnings.warn(f"Echo-TTS model not cached locally for {repo_id}: {exc}")
        pytest.skip("Echo-TTS model not cached locally")

    if required_files:
        missing = [name for name in required_files if not (snapshot_path / name).exists()]
        if missing:
            warnings.warn(f"Echo-TTS cache missing files for {repo_id}: {missing}")
            pytest.skip("Echo-TTS cache missing required files")

    return snapshot_path


@pytest.mark.asyncio
async def test_echo_tts_initialize_cuda():
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")

    module_path = _resolve_echo_module_path()
    if not _echo_modules_present(module_path):
        pytest.skip(
            "Echo-TTS module not found; set ECHO_TTS_MODULE_PATH to your echo-tts checkout",
        )

    module_path_str = str(module_path)
    if module_path_str not in sys.path:
        sys.path.insert(0, module_path_str)

    adapter = EchoTTSAdapter(
        config={
            "echo_tts_module_path": module_path_str,
            "echo_tts_device": "cuda",
        }
    )
    success = await adapter.initialize()

    assert success is True
    assert adapter.device == "cuda"
    assert adapter._status == ProviderStatus.AVAILABLE
    assert adapter._echo_inference is not None
    assert adapter._echo_blockwise is not None

    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.requires_model
async def test_echo_tts_generate_cuda_cached_models(monkeypatch):
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")

    module_path = _resolve_echo_module_path()
    if not _echo_modules_present(module_path):
        pytest.skip(
            "Echo-TTS module not found; set ECHO_TTS_MODULE_PATH to your echo-tts checkout",
        )

    voice_path = _resolve_voice_reference_path()
    if not voice_path.exists():
        pytest.skip("Sample voice reference not found")

    module_path_str = str(module_path)
    if module_path_str not in sys.path:
        sys.path.insert(0, module_path_str)

    adapter = EchoTTSAdapter(
        config={
            "echo_tts_module_path": module_path_str,
            "echo_tts_device": "cuda",
        }
    )

    _require_hf_cache(adapter.model_repo, required_files=[adapter.pca_state_file])
    _require_hf_cache(adapter.fish_ae_repo)

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    request = TTSRequest(
        text="Hello from Echo-TTS CUDA integration.",
        format=AudioFormat.WAV,
        stream=False,
        voice_reference=voice_path.read_bytes(),
        extra_params={
            "validate_reference": False,
            "convert_reference": False,
            "sequence_length": 160,
            "num_steps": 10,
        },
    )

    response = await adapter.generate(request)
    assert response.audio_data is not None
    assert len(response.audio_data) > 0
    assert response.format == AudioFormat.WAV
    assert response.provider == adapter.PROVIDER_KEY

    await adapter.close()
