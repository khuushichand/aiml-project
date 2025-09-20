"""
Simple benchmark-style tests for chunking performance and metrics.

These tests enforce broad performance expectations to catch large regressions.
They also verify that core metrics are emitted with expected labels.
"""

import json
import time
import pytest

from tldw_Server_API.app.core.Chunking.Chunk_Lib import Chunker
from tldw_Server_API.app.core.Metrics import get_metrics_registry


@pytest.mark.bench
@pytest.mark.slow
def test_bench_words_100k():
    text = " ".join(["word"] * 100_000)  # ~500k chars
    chunker = Chunker(options={'method': 'words', 'max_size': 100, 'overlap': 10, 'adaptive': False})
    t0 = time.perf_counter()
    chunks = chunker.chunk_text(text)
    dt = time.perf_counter() - t0
    assert len(chunks) > 0
    # Expect under 3s on CI for a basic regex/token-free splitter
    assert dt < 3.0


@pytest.mark.bench
@pytest.mark.slow
def test_bench_sentences_500():
    text = " ".join([f"Sentence {i}." for i in range(500)])
    chunker = Chunker(options={'method': 'sentences', 'max_size': 5, 'overlap': 1, 'adaptive': False, 'sentence_splitter': 'regex'})
    t0 = time.perf_counter()
    chunks = chunker.chunk_text(text)
    dt = time.perf_counter() - t0
    assert len(chunks) > 0
    assert dt < 1.5


@pytest.mark.bench
@pytest.mark.slow
def test_bench_json_large_array():
    arr = [{"id": i, "text": f"item {i}"} for i in range(5000)]
    text = json.dumps(arr)
    chunker = Chunker(options={'method': 'json', 'max_size': 1000, 'overlap': 100})
    t0 = time.perf_counter()
    chunks = chunker.chunk_text(text)
    dt = time.perf_counter() - t0
    assert len(chunks) > 0
    assert dt < 1.5


@pytest.mark.bench
def test_metrics_emitted_for_words():
    text = " ".join(["word"] * 10_000)
    chunker = Chunker(options={'method': 'words', 'max_size': 100, 'overlap': 10})
    _ = chunker.chunk_text(text)

    metrics_text = get_metrics_registry().export_prometheus_format()
    # Check core metric names exist
    assert 'chunk_time_seconds' in metrics_text
    assert 'chunk_output_bytes' in metrics_text
    assert 'chunk_input_bytes' in metrics_text
    assert 'chunk_count' in metrics_text
    assert 'chunk_avg_chunk_size_bytes' in metrics_text

