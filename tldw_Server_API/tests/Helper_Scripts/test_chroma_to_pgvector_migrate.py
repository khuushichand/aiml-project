import asyncio
import uuid

import pytest

from Helper_Scripts import chroma_to_pgvector_migrate as migrate_script
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import (
    VectorStoreConfig,
    VectorStoreType,
)
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import (
    PGVectorAdapter,
)


pytestmark = pytest.mark.pg_integration


def test_chroma_to_pgvector_seeds_and_migrates(pgvector_dsn, monkeypatch):
    monkeypatch.setenv("CHROMADB_FORCE_STUB", "true")

    user_id = f"cli_test_{uuid.uuid4().hex[:8]}"
    source_collection = "demo_cli_collection"
    dest_collection = f"{source_collection}_pg_{uuid.uuid4().hex[:6]}"

    result = asyncio.run(
        migrate_script.migrate_collection(
            user_id=user_id,
            source_collection=source_collection,
            dest_collection=dest_collection,
            dsn=pgvector_dsn,
            page_size=32,
            drop_dest=True,
            rebuild_index="hnsw",
            hnsw_m=8,
            hnsw_ef_construction=64,
            ivfflat_lists=10,
            embedding_dim_override=8,
            seed_demo=True,
            dry_run=False,
        )
    )

    assert result.source_count == result.written
    assert result.written > 0
    assert result.collection_metadata.get("embedding_dimension") == 8

    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": pgvector_dsn},
        embedding_dim=8,
        user_id=user_id,
    )

    async def _verify_and_cleanup():
        adapter = PGVectorAdapter(cfg)
        await adapter.initialize()
        stats = await adapter.get_collection_stats(dest_collection)
        await adapter.delete_collection(dest_collection)
        return stats

    stats = asyncio.run(_verify_and_cleanup())
    assert stats.get("count") == result.written
