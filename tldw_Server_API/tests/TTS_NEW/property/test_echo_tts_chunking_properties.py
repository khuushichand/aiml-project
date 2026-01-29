import pytest
from hypothesis import given, strategies as st, assume

from tldw_Server_API.app.core.TTS.adapters.echo_tts_adapter import EchoTTSAdapter


@pytest.mark.property
@given(text=st.text(min_size=1, max_size=500))
def test_echo_chunker_respects_byte_limit_property(text):
    assume(text.strip())
    adapter = EchoTTSAdapter(config={})
    max_bytes = 64
    max_chars = 64
    chunks = adapter._split_text_chunks(text, max_chars=max_chars, max_bytes=max_bytes)

    assert chunks
    assert all(len(chunk.encode("utf-8")) <= max_bytes for chunk in chunks)
