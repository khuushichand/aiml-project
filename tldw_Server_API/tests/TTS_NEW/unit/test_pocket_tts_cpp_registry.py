import pytest

from tldw_Server_API.app.core.TTS.adapter_registry import TTSAdapterFactory, TTSProvider
from tldw_Server_API.app.core.TTS.tts_config import ProviderConfig, TTSConfig, TTSConfigManager


@pytest.mark.unit
def test_pocket_tts_cpp_model_aliases_resolve_to_new_provider():
    factory = TTSAdapterFactory({})

    assert factory.get_provider_for_model("pocket_tts_cpp") == TTSProvider.POCKET_TTS_CPP
    assert factory.get_provider_for_model("pocket-tts-cpp") == TTSProvider.POCKET_TTS_CPP


@pytest.mark.unit
def test_pocket_tts_cpp_config_round_trip_preserves_explicit_fields():
    manager = TTSConfigManager.__new__(TTSConfigManager)
    manager._config = TTSConfig(
        providers={
            "pocket_tts_cpp": ProviderConfig(
                binary_path="models/pocket_tts_cpp/pocket_tts_cpp",
                tokenizer_path="models/pocket_tts_cpp/tokenizer.model",
                enable_voice_cache=True,
                cache_ttl_hours=12,
                cache_max_bytes_per_user=2048,
                persist_direct_voice_references=True,
            )
        }
    )
    manager._sources = {}

    config_dict = manager.to_dict()
    provider_dict = config_dict["providers"]["pocket_tts_cpp"]

    assert provider_dict["binary_path"] == "models/pocket_tts_cpp/pocket_tts_cpp"
    assert provider_dict["tokenizer_path"] == "models/pocket_tts_cpp/tokenizer.model"
    assert provider_dict["enable_voice_cache"] is True
    assert provider_dict["cache_ttl_hours"] == 12
    assert provider_dict["cache_max_bytes_per_user"] == 2048
    assert provider_dict["persist_direct_voice_references"] is True
