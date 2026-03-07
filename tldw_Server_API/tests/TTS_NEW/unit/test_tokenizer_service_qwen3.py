import io
import sys
import types

import numpy as np
import pytest
import soundfile as sf

from tldw_Server_API.app.core.Audio import tokenizer_service


def _install_fake_tokenizer_module(monkeypatch):
    module = types.ModuleType("qwen_tts")

    class FakeTokenizer:
        total_upsample = 2

        def __init__(self, model=None, **_kwargs):
            self.model = model

        def __call__(self, codes):
            return codes

        def chunked_decode(self, codes, chunk_size=300, left_context_size=25):
            context_size = left_context_size
            return codes[..., context_size * self.total_upsample:]

    module.Qwen3TTSTokenizer = FakeTokenizer
    monkeypatch.setitem(sys.modules, "qwen_tts", module)
    return FakeTokenizer


def test_serialize_audio_output_wav_wraps_raw_pcm_bytes():
    pcm = np.array([0, 1000, -1000, 0], dtype=np.int16).tobytes()
    wav_bytes = tokenizer_service._serialize_audio_output(pcm, 24000, "wav")
    assert wav_bytes[:4] == b"RIFF"
    decoded, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="int16")
    assert sample_rate == 24000
    assert decoded.size > 0


def test_serialize_audio_output_wav_passthrough():
    buf = io.BytesIO()
    sf.write(buf, np.zeros(240, dtype=np.float32), 24000, format="WAV", subtype="PCM_16")
    wav_bytes = buf.getvalue()
    output = tokenizer_service._serialize_audio_output(wav_bytes, 24000, "wav")
    assert output == wav_bytes


def test_load_qwen3_tokenizer_patches_chunked_decode(monkeypatch):
    tokenizer_cls = _install_fake_tokenizer_module(monkeypatch)
    original_fn = tokenizer_cls.chunked_decode

    tokenizer = tokenizer_service._load_qwen3_tokenizer(
        "Qwen/Qwen3-TTS-Tokenizer-12Hz/",
        allow_download=False,
        patch_chunked_decode=True,
    )
    assert tokenizer.model == "Qwen/Qwen3-TTS-Tokenizer-12Hz"
    assert tokenizer.__class__.chunked_decode is not original_fn


def test_load_qwen3_tokenizer_patch_toggle_off(monkeypatch):
    tokenizer_cls = _install_fake_tokenizer_module(monkeypatch)
    original_fn = tokenizer_cls.chunked_decode

    tokenizer = tokenizer_service._load_qwen3_tokenizer(
        "Qwen/Qwen3-TTS-Tokenizer-12Hz/",
        allow_download=False,
        patch_chunked_decode=False,
    )
    assert tokenizer.model == "Qwen/Qwen3-TTS-Tokenizer-12Hz"
    assert tokenizer.__class__.chunked_decode is original_fn


def test_load_qwen3_tokenizer_maps_model_path_error(monkeypatch):
    module = types.ModuleType("qwen_tts")

    class BadTokenizer:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs
            raise RuntimeError("HFValidationError: Repo id must be in the form 'repo_name'")

    module.Qwen3TTSTokenizer = BadTokenizer
    monkeypatch.setitem(sys.modules, "qwen_tts", module)

    with pytest.raises(Exception) as exc_info:
        tokenizer_service._load_qwen3_tokenizer("Qwen/Bad-Tokenizer/", allow_download=False)
    assert getattr(exc_info.value, "status_code", None) == 400


def test_load_qwen3_tokenizer_maps_rope_compat_error(monkeypatch):
    module = types.ModuleType("qwen_tts")

    class BadTokenizer:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs
            raise RuntimeError("KeyError: 'default' while setting rope")

    module.Qwen3TTSTokenizer = BadTokenizer
    monkeypatch.setitem(sys.modules, "qwen_tts", module)

    with pytest.raises(Exception) as exc_info:
        tokenizer_service._load_qwen3_tokenizer("Qwen/Tokenizer", allow_download=False)
    assert getattr(exc_info.value, "status_code", None) == 500
