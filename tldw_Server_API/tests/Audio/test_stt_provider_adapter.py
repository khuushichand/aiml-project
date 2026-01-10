import types

import pytest


def _import_module():


     # Local import so tests don't break when heavy STT deps are absent.
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter as spa

    return spa


@pytest.mark.unit
def test_default_provider_name_uses_stt_settings(monkeypatch):
     spa = _import_module()

    # Simulate STT-Settings with both keys present; default_transcriber should win.
    def fake_get_stt_config():
             return {
            "default_stt_provider": "parakeet",
            "default_transcriber": "faster_whisper",
        }

    monkeypatch.setattr(spa, "get_stt_config", fake_get_stt_config)

    registry = spa.SttProviderRegistry()
    assert registry.get_default_provider_name() == "faster-whisper"


@pytest.mark.unit
def test_default_provider_name_falls_back_to_stt_provider(monkeypatch):
     spa = _import_module()

    def fake_get_stt_config():

             return {
            "default_stt_provider": "parakeet",
            # No default_transcriber key
        }

    monkeypatch.setattr(spa, "get_stt_config", fake_get_stt_config)

    registry = spa.SttProviderRegistry()
    assert registry.get_default_provider_name() == "parakeet"


@pytest.mark.unit
def test_get_adapter_unknown_provider_falls_back_to_faster_whisper(monkeypatch):
     spa = _import_module()

    def fake_get_stt_config():

             return {
            "default_stt_provider": "parakeet",
        }

    monkeypatch.setattr(spa, "get_stt_config", fake_get_stt_config)

    registry = spa.SttProviderRegistry()
    adapter = registry.get_adapter("unknown-provider")
    assert adapter.name.value == "faster-whisper"


@pytest.mark.unit
def test_resolve_provider_for_model_uses_parser(monkeypatch):
     spa = _import_module()

    # Provide a simple, deterministic parser implementation so we don't depend
    # on the exact behavior of Audio_Transcription_Lib here.
    def fake_parse_transcription_model(model_name: str):
        if model_name.startswith("parakeet"):
            return ("parakeet", "parakeet", "onnx")
        if model_name.startswith("qwen2audio"):
            return ("qwen2audio", model_name, None)
        return ("whisper", model_name, None)

    monkeypatch.setattr(spa, "parse_transcription_model", fake_parse_transcription_model)

    registry = spa.SttProviderRegistry()

    provider, model, variant = registry.resolve_provider_for_model("parakeet-onnx")
    assert provider == "parakeet"
    assert model == "parakeet"
    assert variant == "onnx"

    provider, model, variant = registry.resolve_provider_for_model("qwen2audio-test")
    assert provider == "qwen2audio"
    assert model == "qwen2audio-test"
    assert variant is None

    # Whisper-family models should normalize to faster-whisper.
    provider, model, variant = registry.resolve_provider_for_model("whisper-1")
    assert provider == "faster-whisper"
    assert model == "whisper-1"
    assert variant is None


@pytest.mark.unit
def test_capabilities_exposed_for_known_providers():
     spa = _import_module()

    registry = spa.SttProviderRegistry()

    fw_caps = registry.get_capabilities("faster-whisper")
    assert fw_caps.supports_batch is True
    assert fw_caps.supports_streaming is True

    parakeet_caps = registry.get_capabilities("parakeet")
    assert parakeet_caps.supports_batch is True
    assert parakeet_caps.supports_streaming is True

    canary_caps = registry.get_capabilities("canary")
    assert canary_caps.supports_batch is True
    assert canary_caps.supports_streaming is False

    qwen_caps = registry.get_capabilities("qwen2audio")
    assert qwen_caps.supports_batch is True
    assert qwen_caps.supports_streaming is False


@pytest.mark.unit
def test_transcribe_batch_whisper_normalizes_artifact(monkeypatch, tmp_path):
     spa = _import_module()

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"\x00" * 2048)

    def fake_speech_to_text(
        path,
        whisper_model,
        selected_source_lang,
        vad_filter,
        diarize,
        word_timestamps,
        return_language,
        initial_prompt=None,
        task="transcribe",
        base_dir=None,
    ):

             assert str(path) == str(audio_file)
        assert whisper_model == "tiny"
        assert selected_source_lang is None
        assert task == "transcribe"

        segments = [
            {"Text": "hello", "start_seconds": 0.0, "end_seconds": 0.5},
            {"Text": "world", "start_seconds": 0.5, "end_seconds": 1.0},
        ]
        return segments, "en"

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib

    monkeypatch.setattr(atlib, "speech_to_text", fake_speech_to_text)
    monkeypatch.setattr(atlib, "strip_whisper_metadata_header", lambda segs: segs)

    adapter = spa.FasterWhisperAdapter()
    artifact = adapter.transcribe_batch(
        str(audio_file),
        model="tiny",
        language=None,
        task="transcribe",
        word_timestamps=False,
    )

    assert artifact["text"] == "hello world"
    assert artifact["language"] == "en"
    assert isinstance(artifact["segments"], list)
    # Default diarization and usage contract
    assert artifact["diarization"]["enabled"] is False
    assert artifact["diarization"]["speakers"] is None
    assert artifact["usage"]["duration_ms"] is None


@pytest.mark.unit
def test_transcribe_batch_parakeet_normalizes_artifact(monkeypatch, tmp_path):
     spa = _import_module()

    audio_file = tmp_path / "sample_parakeet.wav"
    audio_file.write_bytes(b"\x00" * 1024)

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib

    def fake_speech_to_text(
        path,
        whisper_model,
        selected_source_lang,
        vad_filter,
        diarize,
        return_language,
        base_dir=None,
    ):

             assert str(path) == str(audio_file)
        # Parakeet adapter encodes model name into whisper_model
        assert whisper_model == "parakeet-standard"
        segments = [
            {"Text": "parakeet", "start_seconds": 0.0, "end_seconds": 0.5},
            {"Text": "ok", "start_seconds": 0.5, "end_seconds": 1.0},
        ]
        return segments, "en"

    monkeypatch.setattr(atlib, "speech_to_text", fake_speech_to_text, raising=True)

    adapter = spa.ParakeetAdapter()
    artifact = adapter.transcribe_batch(
        str(audio_file),
        model="parakeet-standard",
        language="en",
    )

    assert artifact["text"] == "parakeet ok"
    assert artifact["language"] == "en"
    assert isinstance(artifact["segments"], list)
    assert artifact["metadata"]["provider"] == "parakeet"
    assert artifact["metadata"]["model"] == "parakeet-standard"
    assert artifact["diarization"]["enabled"] is False


@pytest.mark.unit
def test_transcribe_batch_canary_normalizes_artifact(monkeypatch, tmp_path):
     spa = _import_module()

    # Create a minimal valid WAV file for soundfile to read
    import numpy as np
    import soundfile as sf

    audio_file = tmp_path / "sample_canary.wav"
    data = np.zeros(1600, dtype="float32")
    sf.write(str(audio_file), data, 16000)

    # Provide a lightweight fake Nemo module so we don't depend on real Nemo.
    import sys
    fake_nemo_mod = types.ModuleType(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo"
    )

    def fake_transcribe_with_canary(audio_np, sample_rate, language, task="transcribe", target_language=None):

             assert sample_rate == 16000
        return "canary transcript"

    fake_nemo_mod.transcribe_with_canary = fake_transcribe_with_canary
    sys.modules[
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo"
    ] = fake_nemo_mod

    adapter = spa.CanaryAdapter()
    artifact = adapter.transcribe_batch(
        str(audio_file),
        model="nemo-canary-1b",
        language="en",
    )

    assert artifact["text"] == "canary transcript"
    assert isinstance(artifact["segments"], list)
    assert artifact["segments"][0]["Text"] == "canary transcript"
    assert artifact["metadata"]["provider"] == "canary"
    assert artifact["diarization"]["enabled"] is False


@pytest.mark.unit
def test_transcribe_batch_external_normalizes_artifact(monkeypatch, tmp_path):
     spa = _import_module()

    audio_file = tmp_path / "sample_external.wav"
    audio_file.write_bytes(b"\x00" * 1024)

    # Stub external provider module to avoid real HTTP calls
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_External_Provider as ext_mod

    def fake_transcribe_with_external_provider(
        path,
        provider_name="default",
        language=None,
        sample_rate=None,
        base_dir=None,
    ):

             assert str(path) == str(audio_file)
        assert base_dir is None
        return "external transcript"

    monkeypatch.setattr(
        ext_mod,
        "transcribe_with_external_provider",
        fake_transcribe_with_external_provider,
        raising=True,
    )

    adapter = spa.ExternalAdapter()
    artifact = adapter.transcribe_batch(
        str(audio_file),
        model="external:myprovider",
        language="en",
    )

    assert artifact["text"] == "external transcript"
    assert isinstance(artifact["segments"], list)
    assert artifact["segments"][0]["Text"] == "external transcript"
    assert artifact["metadata"]["provider"] == "external"
    assert artifact["metadata"]["external_provider_name"] == "myprovider"
    assert artifact["diarization"]["enabled"] is False


@pytest.mark.unit
def test_transcribe_batch_external_passes_base_dir(monkeypatch, tmp_path):
     spa = _import_module()

    audio_file = tmp_path / "external_base_dir.wav"
    audio_file.write_bytes(b"\x00" * 2048)
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    captured = {}

    def fake_transcribe_with_external_provider(
        path,
        provider_name="default",
        language=None,
        sample_rate=None,
        base_dir=None,
    ):

             captured["path"] = str(path)
        captured["base_dir"] = base_dir
        return "external ok"

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_External_Provider as ext_mod

    monkeypatch.setattr(
        ext_mod,
        "transcribe_with_external_provider",
        fake_transcribe_with_external_provider,
        raising=True,
    )

    adapter = spa.ExternalAdapter()
    artifact = adapter.transcribe_batch(
        str(audio_file),
        model="external:stub",
        language=None,
        base_dir=base_dir,
    )

    assert artifact["text"] == "external ok"
    assert captured["path"] == str(audio_file)
    assert captured["base_dir"] == base_dir
