from __future__ import annotations

import os
import platform

import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter

pytestmark = [pytest.mark.asyncio, pytest.mark.integration, pytest.mark.local_llm_service]


def _require_qwen3_mlx_model() -> str:
    if os.getenv("TLDW_RUN_QWEN3_MLX_INTEGRATION") != "1":
        pytest.skip("TLDW_RUN_QWEN3_MLX_INTEGRATION not set")
    if platform.system() != "Darwin" or platform.machine().lower() != "arm64":
        pytest.skip("Qwen3 MLX integration tests run only on Apple Silicon macOS")
    try:
        import mlx_audio.tts.utils  # noqa: F401
    except Exception:
        pytest.skip("mlx-audio is not installed; skipping Qwen3 MLX integration tests")
    return os.getenv("QWEN3_MLX_MODEL") or "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16"


@pytest.mark.requires_model
async def test_qwen3_mlx_streaming_smoke():
    model_id = _require_qwen3_mlx_model()
    adapter = Qwen3TTSAdapter(
        {
            "runtime": "mlx",
            "model": "auto",
            "mlx_model": model_id,
            "device": "mps",
        }
    )
    try:
        await adapter.ensure_initialized()

        request = TTSRequest(
            text="Hello from the Qwen3 MLX integration test.",
            voice="Vivian",
            format=AudioFormat.PCM,
            stream=True,
        )
        request.model = "auto"

        response = await adapter.generate(request)
        chunks = [chunk async for chunk in response.audio_stream if chunk]

        assert chunks
        assert sum(len(chunk) for chunk in chunks) > 0
        assert response.metadata["runtime"] == "mlx"
        assert response.metadata["streaming_fallback"] == "buffered"
    finally:
        await adapter.close()
