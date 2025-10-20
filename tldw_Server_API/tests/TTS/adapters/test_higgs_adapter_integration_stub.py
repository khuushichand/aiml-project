# test_higgs_adapter_integration_stub.py
# Description: Lightweight integration test for Higgs adapter using a stub serve engine.

import sys
import types
import numpy as np
import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.integration


def _install_stub_serve_engine():
    """Install a stubbed boson_multimodal.serve.serve_engine module into sys.modules."""
    # Root package
    bm = types.ModuleType("boson_multimodal")
    bm.__path__ = []  # mark as package

    # boson_multimodal.serve
    bm_serve = types.ModuleType("boson_multimodal.serve")
    bm_serve.__path__ = []

    # boson_multimodal.serve.serve_engine
    bm_engine = types.ModuleType("boson_multimodal.serve.serve_engine")

    class HiggsAudioResponse:
        def __init__(self, audio, sampling_rate=24000, generated_text=""):
            self.audio = audio
            self.sampling_rate = sampling_rate
            self.generated_text = generated_text

    class StubEngine:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.last_chat_ml_sample = None
            # default attributes referenced by adapter after init
            self.audio_num_codebooks = 12
            self.audio_tokenizer = None
            self.audio_tokenizer_tps = 25
            self.samples_per_token = 960
            self.hamming_window_len = 2 * self.audio_num_codebooks * self.samples_per_token

        def generate(self, **kwargs):
            # capture the chat_ml_sample for assertions
            self.last_chat_ml_sample = kwargs.get("chat_ml_sample")
            audio = np.zeros(8000, dtype=np.float32)
            return HiggsAudioResponse(audio=audio, sampling_rate=24000, generated_text="stub")

    bm_engine.HiggsAudioServeEngine = StubEngine
    bm_engine.HiggsAudioResponse = HiggsAudioResponse

    sys.modules["boson_multimodal"] = bm
    sys.modules["boson_multimodal.serve"] = bm_serve
    sys.modules["boson_multimodal.serve.serve_engine"] = bm_engine


@pytest.mark.asyncio
async def test_voice_reference_integration_message_injection():
    from tldw_Server_API.app.core.TTS.adapters.higgs_adapter import HiggsAdapter
    from tldw_Server_API.app.core.TTS.adapters.base import TTSRequest, AudioFormat

    # Install stub serve engine into sys.modules so imports succeed
    _install_stub_serve_engine()

    # Avoid memory monitor gating
    mock_manager = AsyncMock()
    mock_manager.memory_monitor.is_memory_critical.return_value = False

    with patch(
        "tldw_Server_API.app.core.TTS.adapters.higgs_adapter.get_resource_manager",
        return_value=mock_manager,
    ):
        adapter = HiggsAdapter({"higgs_device": "cpu"})

        # Initialize, which should construct the stub engine
        initialized = await adapter.initialize()
        assert initialized

        # Patch voice reference processing to avoid heavy dependencies
        with patch.object(adapter, "_prepare_voice_reference", return_value="/tmp/ref.wav"):
            # Patch StreamingAudioWriter and AudioNormalizer to be no-ops
            with patch(
                "tldw_Server_API.app.core.TTS.streaming_audio_writer.AudioNormalizer.normalize",
                side_effect=lambda x, target_dtype=None: x,
            ), patch(
                "tldw_Server_API.app.core.TTS.streaming_audio_writer.StreamingAudioWriter.write_chunk",
                side_effect=lambda *a, **k: b"chunk",
            ):
                minimal_wav = b"RIFF" + b"\x00" * 4 + b"WAVEfmt " + b"\x00" * 32
                request = TTSRequest(
                    text="Hello world",
                    voice="narrator",
                    voice_reference=minimal_wav,
                    format=AudioFormat.WAV,
                    stream=True,
                )

                # Trigger generation (streaming to exercise the code path)
                resp = await adapter.generate(request)
                assert resp.audio_stream is not None
                # drain generator (one or two chunks)
                chunks = []
                async for c in resp.audio_stream:
                    chunks.append(c)
                    if len(chunks) > 2:
                        break
                assert len(chunks) >= 1

                # Inspect the captured ChatML payload from the stub engine
                stub_engine = adapter.serve_engine
                chat_ml = getattr(stub_engine, "last_chat_ml_sample", None)
                assert chat_ml is not None
                messages = chat_ml.get("messages") if isinstance(chat_ml, dict) else None
                assert messages is not None and len(messages) >= 2

                # Find assistant message and ensure it contains audio content
                def _role(m):
                    return getattr(m, "role", m.get("role") if isinstance(m, dict) else None)

                def _content(m):
                    return getattr(m, "content", m.get("content") if isinstance(m, dict) else None)

                assistant = next((m for m in messages if _role(m) == "assistant"), None)
                assert assistant is not None
                content = _content(assistant)
                ctype = getattr(content, "type", content.get("type") if isinstance(content, dict) else None)
                url = getattr(content, "audio_url", content.get("audio_url") if isinstance(content, dict) else None)
                assert ctype == "audio"
                assert url == "/tmp/ref.wav"

        # Cleanup adapter
        await adapter.close()


@pytest.mark.asyncio
async def test_multispeaker_and_language_hints_in_chatml_stub():
    from tldw_Server_API.app.core.TTS.adapters.higgs_adapter import HiggsAdapter
    from tldw_Server_API.app.core.TTS.adapters.base import TTSRequest, AudioFormat

    _install_stub_serve_engine()

    mock_manager = AsyncMock()
    mock_manager.memory_monitor.is_memory_critical.return_value = False

    with patch(
        "tldw_Server_API.app.core.TTS.adapters.higgs_adapter.get_resource_manager",
        return_value=mock_manager,
    ):
        adapter = HiggsAdapter({"higgs_device": "cpu"})
        assert await adapter.initialize()

        with patch(
            "tldw_Server_API.app.core.TTS.streaming_audio_writer.AudioNormalizer.normalize",
            side_effect=lambda x, target_dtype=None: x,
        ), patch(
            "tldw_Server_API.app.core.TTS.streaming_audio_writer.StreamingAudioWriter.write_chunk",
            side_effect=lambda *a, **k: b"chunk",
        ):
            request = TTSRequest(
                text="Hola mundo",
                voice="narrator",
                language="es",
                emotion="happy",
                emotion_intensity=1.0,  # moderately
                style="dramatic",
                speakers={"S1": "narrator", "S2": "conversational"},
                format=AudioFormat.WAV,
                stream=True,
            )

            resp = await adapter.generate(request)
            assert resp.audio_stream is not None
            # Advance stream a bit
            async for _ in resp.audio_stream:
                break

            stub_engine = adapter.serve_engine
            chat_ml = getattr(stub_engine, "last_chat_ml_sample", None)
            assert chat_ml is not None
            messages = chat_ml.get("messages") if isinstance(chat_ml, dict) else None
            assert messages

            # Last message should be user content with hints
            last = messages[-1]
            content = getattr(last, "content", last.get("content") if isinstance(last, dict) else None)
            assert isinstance(content, str)
            assert "multiple speakers" in content
            assert "Please generate speech in es" in content
            assert "moderately happy" in content
            assert "In a dramatic style" in content

        await adapter.close()
