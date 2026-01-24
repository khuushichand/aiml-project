import pytest

from tldw_Server_API.app.core.TTS.adapters.echo_tts_adapter import EchoTTSAdapter


@pytest.mark.unit
def test_echo_tts_chunker_respects_utf8_bytes():
    adapter = EchoTTSAdapter(config={})
    text = "\u00e1" * 500  # 2 bytes each in UTF-8 => 1000 bytes
    chunks = adapter._split_text_chunks(text, max_chars=300, max_bytes=200)

    assert len(chunks) > 1
    assert all(chunks)
    assert all(len(chunk.encode("utf-8")) <= 200 for chunk in chunks)
    assert "".join(chunks) == text
