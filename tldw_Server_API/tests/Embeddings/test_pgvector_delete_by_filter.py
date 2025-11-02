import asyncio
import os
from typing import Any, Dict, List

import pytest

from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType


@pytest.mark.usefixtures("pgvector_temp_table")
def test_pgvector_delete_by_filter_removes_matching_rows(pgvector_dsn, pgvector_temp_table):
    # Derive collection name from table (strip leading 'vs_' as adapter prefixes it)
    table_name: str = pgvector_temp_table
    assert table_name.startswith("vs_")
    collection = table_name[3:]

    # Build adapter
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": pgvector_dsn},
        embedding_dim=8,
        distance_metric="cosine",
        user_id="test",
    )
    adapter = PGVectorAdapter(cfg)

    async def _run():
        await adapter.initialize()
        # Upsert three rows with media_id metadata (two matching, one different)
        ids = ["a", "b", "c"]
        vecs = [[0.0]*8, [0.1]*8, [0.2]*8]
        docs = ["", "", ""]
        metas: List[Dict[str, Any]] = [
            {"media_id": "42", "kind": "chunk"},
            {"media_id": "42", "kind": "chunk"},
            {"media_id": "43", "kind": "chunk"},
        ]
        await adapter.upsert_vectors(collection, ids, vecs, docs, metas)

        # Delete by filter
        deleted = await adapter.delete_by_filter(collection, {"media_id": "42"})
        # Should report 2
        assert isinstance(deleted, int)
        assert deleted >= 2  # some drivers may report exact

        # Ensure remaining id is 'c'
        page = await adapter.list_vectors_paginated(collection, limit=10, offset=0, filter=None)  # type: ignore[attr-defined]
        items = (page or {}).get("items", [])
        remaining_ids = {it.get("id") for it in items}
        assert remaining_ids == {"c"}

    asyncio.run(_run())
