import hashlib
import unicodedata
from typing import List

import pytest
from hypothesis import given, strategies as st

from tldw_Server_API.app.core.Embeddings.workers.chunking_worker import ChunkingWorker
from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import ChunkingConfig


def _norm_ws(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    t = t.strip()
    t = " ".join(t.split())
    t = t.lower()
    return t


def _concat_normalized_chunks(chunks: List[tuple[str, int, int]]) -> str:
    from tldw_Server_API.app.core.Embeddings.workers.chunking_worker import (
        ChunkingWorker,
    )
    # Reuse worker normalization for exact parity
    w = ChunkingWorker(
        WorkerConfig(
            worker_id="w",
            worker_type="chunking",
            queue_name="embeddings:chunking",
            consumer_group="cg",
        )
    )
    parts = [w._normalize_for_hash(c[0]) for c in chunks]
    return "".join(parts)


@pytest.mark.unit
@given(
    text=st.text(min_size=0, max_size=200),
    # Random whitespace injection character and unicode normalization form
    ws=st.sampled_from([" ", "\n", "\t"]),
    chunk_size=st.integers(min_value=50, max_value=200),
    overlap=st.integers(min_value=0, max_value=30),
)
def test_chunking_concat_matches_global_normalization(text, ws, chunk_size, overlap):
    """For any text and config, the concatenation of normalized chunk texts
    must equal the globally-normalized original text (whitespace/Unicode invariant)."""
    w = ChunkingWorker(
        WorkerConfig(
            worker_id="w",
            worker_type="chunking",
            queue_name="embeddings:chunking",
            consumer_group="cg",
        )
    )

    # Create a variant by injecting extra whitespace and a different normalization form
    variant = (ws + text + ws).replace(" ", ws)
    variant = unicodedata.normalize("NFD", variant)

    cfg = ChunkingConfig(chunk_size=chunk_size, overlap=overlap, separator=ws)
    chunks_a = w._chunk_text(text, cfg)
    chunks_b = w._chunk_text(variant, cfg)

    norm_all_a = _norm_ws(text)
    norm_all_b = _norm_ws(variant)
    norm_concat_a = _concat_normalized_chunks(chunks_a)
    norm_concat_b = _concat_normalized_chunks(chunks_b)

    assert norm_concat_a == norm_all_a
    assert norm_concat_b == norm_all_b


@pytest.mark.unit
@given(
    s=st.text(min_size=0, max_size=200),
)
def test_content_hash_normalization_stability(s):
    """Normalized content hashing should be stable across Unicode forms and whitespace variations."""
    w = ChunkingWorker(
        WorkerConfig(
            worker_id="w",
            worker_type="chunking",
            queue_name="embeddings:chunking",
            consumer_group="cg",
        )
    )
    a = s
    b = unicodedata.normalize("NFD", f"  {s}\n\n")
    na = w._normalize_for_hash(a)
    nb = w._normalize_for_hash(b)
    assert na == nb
    ha = hashlib.sha256(na.encode("utf-8")).hexdigest()
    hb = hashlib.sha256(nb.encode("utf-8")).hexdigest()
    assert ha == hb
