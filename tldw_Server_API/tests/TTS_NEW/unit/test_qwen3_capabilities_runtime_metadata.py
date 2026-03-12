from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSCapabilities
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2
from tldw_Server_API.app.core.TTS.circuit_breaker import build_qwen_runtime_breaker_key


def test_qwen3_capability_payload_includes_runtime_metadata():
    caps = TTSCapabilities(
        provider_name="Qwen3-TTS",
        supported_languages={"en"},
        supported_voices=[],
        supported_formats={AudioFormat.PCM},
        max_text_length=5000,
        supports_streaming=True,
        metadata={"runtime": "mlx", "supported_modes": ["custom_voice_preset"]},
    )

    serialized = TTSServiceV2()._serialize_capabilities(caps)

    assert serialized["metadata"]["runtime"] == "mlx"


def test_runtime_breaker_key_is_namespaced():
    key = build_qwen_runtime_breaker_key("qwen3_tts", "mlx")
    assert key == "qwen3_tts:mlx"
