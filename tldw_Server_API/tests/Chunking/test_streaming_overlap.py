import os
from typing import List

import pytest

from tldw_Server_API.app.core.Chunking import Chunker


def _reconstruct_tokens_from_stream(chunks: List[str], max_overlap: int) -> List[str]:
    """Greedily reconstruct a token stream from streaming chunks.

    On each chunk, remove the longest prefix that matches the current suffix
    (up to max_overlap tokens) to deduplicate boundary overlap.
    """
    out: List[str] = []
    for ch in chunks:
        toks = ch.split()
        # find longest d <= max_overlap s.t. out[-d:] == toks[:d]
        d = 0
        L = min(max_overlap, len(toks), len(out))
        for k in range(L, 0, -1):
            if out[-k:] == toks[:k]:
                d = k
                break
        out.extend(toks[d:])
    return out


def test_chunk_file_stream_words_overlap(tmp_path):
    # Prepare a deterministic whitespace-normalized corpus
    words = [f"w{i:04d}" for i in range(1, 1200)]
    text = " ".join(words)
    p = tmp_path / "words.txt"
    p.write_text(text, encoding="utf-8")

    ck = Chunker()

    # overlap > 0
    chunks = list(
        ck.chunk_file_stream(
            p, method="words", max_size=25, overlap=5, language="en", buffer_size=1024
        )
    )
    recon = _reconstruct_tokens_from_stream(chunks, max_overlap=5)
    assert recon == words, "Reconstructed token stream should match original (overlap>0)"

    # overlap == 0
    chunks0 = list(
        ck.chunk_file_stream(
            p, method="words", max_size=25, overlap=0, language="en", buffer_size=1024
        )
    )
    recon0 = _reconstruct_tokens_from_stream(chunks0, max_overlap=0)
    assert recon0 == words, "Reconstructed token stream should match original (overlap=0)"


def test_chunk_file_stream_sentences_overlap(tmp_path):
    # Build simple sentences
    sents = [f"This is sentence {i}." for i in range(1, 400)]
    text = " ".join(sents)
    p = tmp_path / "sents.txt"
    p.write_text(text, encoding="utf-8")

    ck = Chunker()

    # overlap one sentence
    chunks = list(
        ck.chunk_file_stream(
            p, method="sentences", max_size=8, overlap=1, language="en", buffer_size=2048
        )
    )
    recon = _reconstruct_tokens_from_stream(chunks, max_overlap=50)  # sentence ~ few tokens
    # Compare after whitespace normalization via token lists
    original_tokens = text.split()
    assert recon == original_tokens, "Sentence stream should preserve content with dedup"


def test_structure_aware_code_fence_no_trailing_newline():
    ck = Chunker()
    src = (
        "# Title\n\n"
        "```python\n"
        "print('hello')"
        "```\n"
        "Paragraph after.\n"
    )
    # Intentionally no newline before the closing fence in middle of the string
    chunks = ck.chunk_text(src, method="structure_aware", max_size=3, overlap=0, language="en")
    # Ensure code fence is recognized and serialized back with fences present
    assert any("```python" in c and "```" in c for c in chunks), "Code fence should be preserved as a single block"
    assert any("print('hello')" in c for c in chunks), "Code content should be present"


def test_language_autodetect_thai():
    ck = Chunker()
    thai_text = "ภาษาไทยทดสอบ ทดสอบข้อความ เพื่อการตัดประโยคฯ"
    out = ck.process_text(
        thai_text,
        options={
            "method": "sentences",
            "max_size": 2,
            "overlap": 0,
            "language": "auto",
        },
    )
    assert out and isinstance(out, list)
    md = out[0].get("metadata", {})
    assert md.get("language") == "th", f"Expected Thai autodetect, got {md.get('language')}"
