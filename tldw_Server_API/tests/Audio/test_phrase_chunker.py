from tldw_Server_API.app.core.Streaming.phrase_chunker import PhraseChunker


def test_phrase_chunker_emits_on_sentence_boundary() -> None:
    chunker = PhraseChunker(min_chars=15, max_chars=80)
    out = chunker.push("Hello world. How")
    assert out == ["Hello world."]
    assert chunker.flush() == "How"


def test_phrase_chunker_forces_emit_on_max_chars() -> None:
    chunker = PhraseChunker(min_chars=5, max_chars=10)
    out = chunker.push("abcdefghijklmno")
    assert out
