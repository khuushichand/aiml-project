import sys
import types

from tldw_Server_API.app.core.Chunking import Chunker
from tldw_Server_API.app.core.Chunking.base import ChunkerConfig, ChunkingMethod
from tldw_Server_API.app.core.Chunking.strategies.words import WordChunkingStrategy


def test_words_min_chunk_size_no_space_merge(monkeypatch):
    strategy = WordChunkingStrategy(language="zh")
    tokens = ["a", "b", "c", "d"]
    monkeypatch.setattr(strategy, "_tokenize_text", lambda text: tokens)
    text = "".join(tokens)
    chunks = strategy.chunk(text, max_size=3, overlap=0, min_chunk_size=2)
    assert chunks == [text]


def test_words_chunk_generator_matches_chunk_with_min_size(monkeypatch):
    strategy = WordChunkingStrategy(language="en")
    tokens = ["one", "two", "three", "four", "five"]
    monkeypatch.setattr(strategy, "_tokenize_text", lambda text: tokens)
    text = " ".join(tokens)
    chunks = strategy.chunk(text, max_size=3, overlap=0, min_chunk_size=3)
    gen_chunks = list(strategy.chunk_generator(text, max_size=3, overlap=0, min_chunk_size=3))
    assert gen_chunks == chunks


def test_sentence_strategy_language_reconfigure_via_chunker(monkeypatch):
    fake_pkg = types.ModuleType("pythainlp")
    fake_tokenize = types.ModuleType("pythainlp.tokenize")

    def sent_tokenize(text):
        return [text]

    fake_tokenize.sent_tokenize = sent_tokenize
    fake_pkg.tokenize = fake_tokenize
    monkeypatch.setitem(sys.modules, "pythainlp", fake_pkg)
    monkeypatch.setitem(sys.modules, "pythainlp.tokenize", fake_tokenize)

    ck = Chunker(config=ChunkerConfig(default_method=ChunkingMethod.SENTENCES, language="en"))
    ck.chunk_text("One. Two.", method="sentences", max_size=1, overlap=0, language="en")
    strategy = ck.get_strategy("sentences")
    assert not strategy.pythainlp_available

    ck.chunk_text("thai test.", method="sentences", max_size=1, overlap=0, language="th")
    assert strategy.pythainlp_available
    assert strategy._th_sent_tokenize is sent_tokenize


def test_hierarchical_sentences_respects_combine_short():
    ck = Chunker()
    text = "A. B. C. D."
    base = ck.chunk_text(
        text,
        method="sentences",
        max_size=2,
        overlap=0,
        combine_short=True,
        min_sentence_length=5,
    )
    hier = ck.chunk_text_hierarchical_flat(
        text,
        method="sentences",
        max_size=2,
        overlap=0,
        method_options={
            "combine_short": True,
            "min_sentence_length": 5,
        },
    )
    assert [item["text"] for item in hier] == base
