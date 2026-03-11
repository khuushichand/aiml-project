import platform

from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter


def test_runtime_auto_prefers_mlx_on_macos_arm64(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    adapter = Qwen3TTSAdapter({"runtime": "auto"})

    assert adapter._resolve_runtime_name() == "mlx"


def test_runtime_explicit_remote_wins_over_platform(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    adapter = Qwen3TTSAdapter(
        {
            "runtime": "remote",
            "base_url": "http://127.0.0.1:8000/v1/audio/speech",
        }
    )

    assert adapter._resolve_runtime_name() == "remote"
