import sys
import types

import pytest


def _has_tiktoken():
    try:
        import tiktoken  # noqa: F401
        return True
    except Exception:
        return False


def test_tokens_offsets_tiktoken_monotonic_and_slice_match():
    if not _has_tiktoken():
        pytest.skip("tiktoken not available")

    from tldw_Server_API.app.core.Chunking.strategies.tokens import (
        TokenChunkingStrategy,
    )

    text = (
        "Hello,  world!\nHello world!  Goodbye.\n"
        "Repeated phrase. Repeated phrase. Repeated phrase."
    )
    strat = TokenChunkingStrategy(tokenizer_name="gpt-3.5-turbo")
    results = strat.chunk_with_metadata(text, max_size=12, overlap=4)

    assert results, "No chunks returned"

    prev_start = -1
    prev_end = -1
    for r in results:
        s = r.metadata.start_char
        e = r.metadata.end_char
        # Bounds are valid and monotonic
        assert 0 <= s <= e <= len(text)
        assert s >= prev_start
        assert e >= prev_end
        # Slice matches decoded text
        assert text[s:e] == r.text
        # Token counts sane
        assert 0 < r.metadata.token_count <= 12
        prev_start, prev_end = s, e


def test_tokens_offsets_tiktoken_repeated_substrings_heavy_overlap():
    if not _has_tiktoken():
        pytest.skip("tiktoken not available")

    from tldw_Server_API.app.core.Chunking.strategies.tokens import (
        TokenChunkingStrategy,
    )

    # Repeated patterns can confuse naive substring matching; ensure offsets handle it
    text = (
        "foo bar foo bar foo bar foo bar\n"
        "foo bar foo bar foo bar foo bar\n"
        "foo bar foo bar foo bar"
    )
    strat = TokenChunkingStrategy(tokenizer_name="gpt-3.5-turbo")
    results = strat.chunk_with_metadata(text, max_size=8, overlap=7)

    assert results and len(results) > 2
    for r in results:
        s = r.metadata.start_char
        e = r.metadata.end_char
        assert 0 <= s <= e <= len(text)
        # Exact slice match proves correct mapping even with repeats and heavy overlap
        assert text[s:e] == r.text


def test_tokens_offsets_tiktoken_unicode_emojis_multibyte():
    if not _has_tiktoken():
        pytest.skip("tiktoken not available")

    from tldw_Server_API.app.core.Chunking.strategies.tokens import (
        TokenChunkingStrategy,
    )

    text = (
        "Start 😊😊 café café naïve 🚀 - dashes - and 🤝🏽 emoji with skin-tone.\n"
        "New line, tabs\t\t, and zero-width joiners: 👨‍👩‍👧‍👦 family."
    )
    import unicodedata as _ud

    def _strip_cf(s: str) -> str:
        return "".join(ch for ch in s if _ud.category(ch) != "Cf")

    strat = TokenChunkingStrategy(tokenizer_name="gpt-4")
    results = strat.chunk_with_metadata(text, max_size=20, overlap=10)

    import unicodedata as _ud
    assert results
    for r in results:
        s = r.metadata.start_char
        e = r.metadata.end_char
        assert 0 <= s <= e <= len(text)
        # Boundary should not split grapheme: no combining mark or joiner right after e
        if e < len(text):
            cat = _ud.category(text[e])
            assert cat not in ("Mn", "Me", "Cf"), f"Boundary splits cluster at pos {e}: U+{ord(text[e]):04X} ({cat})"


def test_tokens_offsets_transformers_path_via_mock():
    """Exercise the transformers offset_mapping logic via a mocked tokenizer."""
    from tldw_Server_API.app.core.Chunking.strategies.tokens import (
        TokenChunkingStrategy,
    )

    text = "abcdef ghij klmno"

    class FakeHFTokenizer:
        def __call__(self, txt, add_special_tokens=False, return_offsets_mapping=False, **_: object):
            assert txt == text
            # char-level tokenization; optionally add specials (-1 at both ends)
            input_ids = list(range(len(txt)))
            offsets = [(i, i + 1) for i in range(len(txt))]
            if add_special_tokens:
                input_ids = [-1] + input_ids + [-2]
                offsets = [(0, 0)] + offsets + [(0, 0)]
            return {"input_ids": input_ids, "offset_mapping": offsets}

        def decode(self, token_ids):
            # map -1/-2 to empty, others index into original text
            out = []
            for tid in token_ids:
                if tid in (-1, -2):
                    continue
                out.append(text[tid])
            return "".join(out)

    # Wrap to look like our TransformersTokenizer wrapper (has .tokenizer attr)
    wrapper = types.SimpleNamespace(tokenizer=FakeHFTokenizer())

    strat = TokenChunkingStrategy(tokenizer_name="mock-hf")
    # Force our mocked wrapper
    strat._tokenizer = wrapper  # type: ignore[attr-defined]

    results = strat.chunk_with_metadata(
        text, max_size=5, overlap=2, add_special_tokens=True
    )

    assert results
    # Validate per-chunk spans map back to original text
    for r in results:
        s = r.metadata.start_char
        e = r.metadata.end_char
        assert 0 <= s <= e <= len(text)
        assert text[s:e] == r.text
        assert r.metadata.options.get("add_special_tokens") is True


def test_tokens_offsets_fallback_path():
    from tldw_Server_API.app.core.Chunking.strategies.tokens import (
        TokenChunkingStrategy,
        FallbackTokenizer,
    )

    text = "Leading  spaces,\nmultiple\nlines,\tand\t punctuations!"

    # Force fallback tokenizer so we don't depend on external libs
    strat = TokenChunkingStrategy(tokenizer_name="gpt-3.5-turbo")
    fb = FallbackTokenizer("gpt-3.5-turbo")
    strat._tokenizer = fb  # type: ignore[attr-defined]

    results = strat.chunk_with_metadata(text, max_size=12, overlap=4)

    assert results
    prev_start = -1
    prev_end = -1
    ratio = fb.tokens_per_word.get(fb.model_name, fb.tokens_per_word["default"])
    for r in results:
        s = r.metadata.start_char
        e = r.metadata.end_char
        assert 0 <= s <= e <= len(text)
        assert s >= prev_start
        assert e >= prev_end
        # Words within slice match words in chunk text
        assert text[s:e].split() == r.text.split()
        # Token count approximates word_count * ratio
        expected = int(round(r.metadata.word_count * ratio))
        assert r.metadata.token_count == expected
        assert r.metadata.options.get("approximate") is True
        prev_start, prev_end = s, e
