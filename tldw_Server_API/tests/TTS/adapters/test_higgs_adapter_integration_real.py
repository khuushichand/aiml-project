# test_higgs_adapter_integration_real.py
# Description: Full integration test for Higgs adapter that runs if local weights are available.

import os
import pytest

pytestmark = [pytest.mark.integration]


def _local_model_paths():
    """Resolve local model/tokenizer paths from environment variables.

    Set env vars:
      HIGGS_MODEL_LOCAL_DIR: path to the Higgs model directory (contains config.json)
      HIGGS_AUDIO_TOKENIZER_LOCAL_DIR: path to the audio tokenizer directory (contains config.json)
    """
    model_dir = os.getenv("HIGGS_MODEL_LOCAL_DIR")
    tok_dir = os.getenv("HIGGS_AUDIO_TOKENIZER_LOCAL_DIR")
    if not model_dir or not tok_dir:
        return None, None
    # Quick sanity checks
    if not (os.path.isdir(model_dir) and os.path.isfile(os.path.join(model_dir, "config.json"))):
        return None, None
    if not (os.path.isdir(tok_dir) and os.path.isfile(os.path.join(tok_dir, "config.json"))):
        return None, None
    return model_dir, tok_dir


def _boson_available():
    try:
        import boson_multimodal  # noqa: F401
        return True
    except Exception:
        return False


available = _boson_available()
model_dir, tok_dir = _local_model_paths()


@pytest.mark.skipif(
    not (available and model_dir and tok_dir),
    reason=(
        "Real integration requires boson_multimodal and local weights. "
        "Set HIGGS_MODEL_LOCAL_DIR and HIGGS_AUDIO_TOKENIZER_LOCAL_DIR."
    ),
)
@pytest.mark.asyncio
async def test_real_higgs_integration_local_weights():
    from tldw_Server_API.app.core.TTS.adapters.higgs_adapter import HiggsAdapter
    from tldw_Server_API.app.core.TTS.adapters.base import TTSRequest, AudioFormat

    adapter = HiggsAdapter(
        {
            "higgs_model_path": model_dir,
            "higgs_tokenizer_path": tok_dir,
            "higgs_device": "cpu",
        }
    )

    # Initialize (should not attempt network download)
    ok = await adapter.initialize()
    assert ok

    # Simple non-streaming generate
    req = TTSRequest(text="This is a real integration test.", voice="narrator", format=AudioFormat.WAV, stream=False)
    resp = await adapter.generate(req)
    assert resp.audio_data is not None
    assert len(resp.audio_data) > 0

    # Streaming generate
    req2 = TTSRequest(text="Streaming test with local weights.", voice="conversational", format=AudioFormat.WAV, stream=True)
    resp2 = await adapter.generate(req2)
    assert resp2.audio_stream is not None
    chunks = []
    async for c in resp2.audio_stream:
        chunks.append(c)
        if len(chunks) > 2:
            break
    assert len(chunks) >= 1

    await adapter.close()
