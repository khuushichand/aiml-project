import pytest

from tldw_Server_API.app.core.Chunking.chunker import Chunker


def test_sentence_spans_with_repeats():
    text = "Hello. Hello. Hello."
    ch = Chunker()
    tree_chunks = ch.chunk_text_hierarchical_flat(
        text=text,
        method="sentences",
        max_size=1,
        overlap=0,
        language="en",
        template=None,
    )
    # Expect three chunks corresponding to three "Hello." sentences
    assert len(tree_chunks) == 3
    # Verify offsets are strictly increasing and match substring positions
    last_end = -1
    for i, ck in enumerate(tree_chunks):
        md = ck.get("metadata", {})
        s = md.get("start_offset")
        e = md.get("end_offset")
        assert isinstance(s, int) and isinstance(e, int)
        assert e > s
        assert s > last_end
        # slice should equal the text
        assert ck["text"] == text[s:e].strip()
        last_end = e


@pytest.mark.parametrize("lang,text,sentences", [
    ("zh", "你好。世界。你好。", ["你好。", "世界。", "你好。"]),
    ("ja", "はい。いいえ。はい。", ["はい。", "いいえ。", "はい。"]),
])
def test_cjk_sentence_spans_no_spaces(lang, text, sentences):
    ch = Chunker()
    chunks = ch.chunk_text_hierarchical_flat(
        text=text,
        method="sentences",
        max_size=1,
        overlap=0,
        language=lang,
        template=None,
    )
    # All sentences should be preserved verbatim and without injected spaces
    got = [ck["text"] for ck in chunks]
    assert got == sentences
    # Offsets should cover the entire string without overlap or gaps
    coverage = [ (ck["metadata"]["start_offset"], ck["metadata"]["end_offset"]) for ck in chunks ]
    # Ensure they are contiguous and in order
    prev = 0
    for (s,e) in coverage:
        assert s == prev
        assert e > s
        prev = e
    assert prev == len(text)

