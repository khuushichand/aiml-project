#!/usr/bin/env python3
"""
Chroma → pgvector migration helper (paged, optional seed/demo, optional rebuild).

Usage examples:
  # Use local pgvector (see CI job), seed 10 demo vectors in stub Chroma, migrate to 'demo'
  CHROMADB_FORCE_STUB=true \
  PGVECTOR_DSN=postgresql://postgres:postgres@localhost:5432/tldw \
  python Helper_Scripts/chroma_to_pgvector_migrate.py --user-id 1 --collection demo --seed-demo --page-size 100 --rebuild-index hnsw

Notes:
  - When CHROMADB_FORCE_STUB=true, an in-memory Chroma stub is used; data exists only within this process.
  - For real Chroma, ensure USER_DB_BASE_DIR points to the correct storage root in your config.
"""
import argparse
import os
import random
import string
from typing import Any, Dict, List


def _seed_stub_chroma(user_id: str, collection: str, dim: int = 8, n: int = 10):
    from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
    from tldw_Server_API.app.core.config import settings
    mgr = ChromaDBManager(user_id=user_id, user_embedding_config=settings)
    col = mgr.get_or_create_collection(collection_name=collection, collection_metadata={"embedding_dimension": dim})
    ids = ["seed_" + ''.join(random.choices(string.ascii_lowercase+string.digits, k=6)) for _ in range(n)]
    vecs = [[random.random() for _ in range(dim)] for _ in range(n)]
    docs = [f"demo content {i}" for i in range(n)]
    metas = [{"media_id": str(100+i), "kind": "chunk"} for i in range(n)]
    try:
        upsert = getattr(col, 'upsert', None)
        if callable(upsert):
            upsert(ids=ids, embeddings=vecs, documents=docs, metadatas=metas)
        else:
            col.add(ids=ids, embeddings=vecs, documents=docs, metadatas=metas)
    except Exception:
        col.add(ids=ids, embeddings=vecs, documents=docs, metadatas=metas)


def migrate(collection: str, user_id: str, page_size: int, dry_run: bool, rebuild: str|None, state_file: str|None):
    from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
    from tldw_Server_API.app.core.config import settings
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter

    dim_hint = int(os.getenv('MIGRATE_DIM', '8'))
    mgr = ChromaDBManager(user_id=user_id, user_embedding_config=settings)
    src = mgr.get_or_create_collection(collection_name=collection)
    # PG adapter
    dsn = os.getenv('PGVECTOR_DSN') or os.getenv('PG_TEST_DSN')
    if not dsn:
        raise SystemExit('PGVECTOR_DSN or PG_TEST_DSN is required')
    cfg = VectorStoreConfig(store_type=VectorStoreType.PGVECTOR, connection_params={'dsn': dsn}, embedding_dim=dim_hint, user_id=user_id)
    pg = PGVectorAdapter(cfg)
    
    # Prepare resume state (id-based)
    migrated_ids: set[str] = set()
    if state_file:
        try:
            if os.path.exists(state_file):
                with open(state_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            import json as _json
                            rec = _json.loads(line)
                            if rec.get('user_id') == str(user_id) and rec.get('collection') == collection:
                                mid = str(rec.get('id') or '')
                                if mid:
                                    migrated_ids.add(mid)
                        except Exception:
                            # tolerate partially written lines
                            continue
        except Exception:
            pass

    import asyncio
    async def _run():
        await pg.initialize()
        await pg.create_collection(collection, metadata={"embedding_dimension": dim_hint})
        offset = 0
        total = 0
        # Open state file for append if enabled and not dry-run
        sfh = None
        if state_file and not dry_run:
            try:
                sfh = open(state_file, 'a', encoding='utf-8')
            except Exception:
                sfh = None

        while True:
            try:
                batch = src.get(limit=page_size, offset=offset, include=["embeddings","documents","metadatas"])  # type: ignore
            except Exception:
                batch = src.get(limit=page_size, offset=offset, include=["embeddings","documents","metadatas"])  # type: ignore
            ids: List[str] = list(batch.get('ids') or [])
            if not ids:
                break
            # Filter out ids already migrated (resume)
            todo_mask = [i for i, _id in enumerate(ids) if _id not in migrated_ids]
            if not todo_mask:
                # Advance and continue
                offset += len(ids)
                continue
            embs = batch.get('embeddings') or []
            docs = batch.get('documents') or []
            metas = batch.get('metadatas') or []
            # normalize numpy -> list
            try:
                if hasattr(embs, 'tolist'):
                    embs = embs.tolist()
            except Exception:
                pass
            # Slice by todo_mask
            ids_t = [ids[i] for i in todo_mask]
            embs_t = [embs[i] for i in todo_mask]
            docs_t = [docs[i] for i in todo_mask]
            metas_t = [metas[i] for i in todo_mask]
            if not dry_run and ids_t:
                await pg.upsert_vectors(collection, ids=ids_t, vectors=embs_t, documents=docs_t, metadatas=metas_t)
                # Append to state file
                if sfh:
                    try:
                        import json as _json
                        for _id in ids_t:
                            sfh.write(_json.dumps({"user_id": str(user_id), "collection": collection, "id": _id}) + "\n")
                        sfh.flush()
                    except Exception:
                        pass
                # Update in-memory set
                for _id in ids_t:
                    migrated_ids.add(_id)
            total += len(ids_t)
            if len(ids) < page_size:
                break
            offset += len(ids)
        if rebuild and not dry_run:
            await pg.rebuild_index(collection, index_type=rebuild)
        print({"collection": collection, "migrated": total, "dry_run": dry_run, "rebuild": rebuild or "none"})
        try:
            if sfh:
                sfh.close()
        except Exception:
            pass

    asyncio.run(_run())


def main():
    ap = argparse.ArgumentParser(description="Chroma → pgvector migration helper")
    ap.add_argument('--user-id', default=os.getenv('SINGLE_USER_FIXED_ID', '1'))
    ap.add_argument('--collection', required=True)
    ap.add_argument('--page-size', type=int, default=500)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--seed-demo', action='store_true', help='Populate demo vectors in stub Chroma before migration')
    ap.add_argument('--rebuild-index', choices=['hnsw','ivfflat','drop'], default=None)
    ap.add_argument('--state-file', default=None, help='Path to JSONL resume file (id-based)')
    args = ap.parse_args()

    if args.seed_demo:
        os.environ.setdefault('CHROMADB_FORCE_STUB', 'true')
        _seed_stub_chroma(args.user_id, args.collection)
    # Default state file if not provided
    state = args.state_file
    if state is None and not args.dry_run:
        state = f"Databases/migrate_{args.user_id}_{args.collection}.jsonl"
    migrate(args.collection, args.user_id, args.page_size, args.dry_run, args.rebuild_index, state)


if __name__ == '__main__':
    main()
