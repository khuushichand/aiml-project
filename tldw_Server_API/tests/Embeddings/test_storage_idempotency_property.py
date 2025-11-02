from typing import Dict, List

import pytest
from hypothesis import given, strategies as st

from tldw_Server_API.app.core.Embeddings.workers.storage_worker import StorageWorker
from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig


class FakeCollection:
    """Minimal vector collection supporting add/upsert/update to verify idempotency by id."""

    def __init__(self, support_upsert: bool = True, support_update: bool = True):
        self.vectors: Dict[str, List[float]] = {}
        self.support_upsert = support_upsert
        self.support_update = support_update

    def upsert(self, ids, embeddings, documents=None, metadatas=None):
        if not self.support_upsert:
            raise AttributeError("no upsert")
        for i, e in zip(ids, embeddings):
            self.vectors[str(i)] = list(e)

    def add(self, ids, embeddings, documents=None, metadatas=None):
        # Simulate add semantics that overwrite by id as well (Chroma upsert would be preferred)
        for i, e in zip(ids, embeddings):
            self.vectors[str(i)] = list(e)

    def update(self, ids, embeddings, documents=None, metadatas=None):
        if not self.support_update:
            raise AttributeError("no update")
        for i, e in zip(ids, embeddings):
            self.vectors[str(i)] = list(e)


def _store_batch(worker: StorageWorker, coll: FakeCollection, ids: List[str], embs: List[List[float]]):
    worker._store_batch(
        collection=coll,
        ids=ids,
        embeddings=embs,
        documents=[""] * len(ids),
        metadatas=[{}] * len(ids),
    )


@pytest.mark.unit
@given(
    ids=st.lists(st.text(min_size=1, max_size=8), min_size=1, max_size=30, unique=True),
    dim=st.integers(min_value=4, max_value=16),
)
def test_upsert_idempotent_under_permutation(ids, dim):
    """Upsert/update should converge to same final state regardless of order."""
    w = StorageWorker(
        WorkerConfig(
            worker_id="sw",
            worker_type="storage",
            queue_name="embeddings:storage",
            consumer_group="cg",
        )
    )

    # Random embeddings per id
    rng = __import__("random")
    embs = [[rng.random() for _ in range(dim)] for _ in ids]
    # Permute order
    order = list(range(len(ids)))
    rng.shuffle(order)
    ids_perm = [ids[i] for i in order]
    embs_perm = [embs[i] for i in order]

    # Case A: upsert path
    coll_a = FakeCollection(support_upsert=True, support_update=True)
    _store_batch(w, coll_a, ids, embs)
    _store_batch(w, coll_a, ids_perm, embs_perm)

    # Case B: fallback add+update path
    coll_b = FakeCollection(support_upsert=False, support_update=True)
    _store_batch(w, coll_b, ids_perm, embs_perm)
    _store_batch(w, coll_b, ids, embs)

    assert coll_a.vectors == coll_b.vectors
    # Final state must map each id to last-write embedding regardless of input order
    assert set(coll_a.vectors.keys()) == set(map(str, ids))
