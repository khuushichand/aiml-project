import platform

import pytest

from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter


@pytest.mark.asyncio
async def test_mlx_runtime_reports_preset_custom_voice_only(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    adapter = Qwen3TTSAdapter({"runtime": "mlx", "device": "mps"})

    await adapter.ensure_initialized()
    caps = await adapter.get_capabilities()

    assert caps.metadata["runtime"] == "mlx"
    assert caps.metadata["supported_modes"] == ["custom_voice_preset"]
    assert caps.metadata["supports_uploaded_custom_voices"] is False
    assert caps.supports_voice_cloning is False
