#!/usr/bin/env python3
"""
Chroma → pgvector migration helper.

Example usage:

    export PGVECTOR_DSN=postgresql://postgres:postgres@localhost:5432/tldw
    python Helper_Scripts/chroma_to_pgvector_migrate.py \
        --user-id 1 \
        --collection user_1_media_embeddings \
        --dest-collection user_1_media_embeddings \
        --page-size 500 \
        --rebuild-index hnsw

For quick smoke tests without a real Chroma store:

    export PGVECTOR_DSN=postgresql://postgres:postgres@localhost:5432/tldw
    CHROMADB_FORCE_STUB=true python Helper_Scripts/chroma_to_pgvector_migrate.py \
        --user-id stub \
        --collection demo_cli \
        --seed-demo \
        --page-size 50
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


Vector = Any  # Replaced with pgvector.Vector when available


@dataclass
class MigrationResult:
    source_count: int
    written: int
    collection_metadata: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_count": self.source_count,
            "written": self.written,
            "collection_metadata": self.collection_metadata,
        }


def _vector_to_list(vec: Any) -> List[float]:
    if hasattr(vec, "tolist"):
        vec = vec.tolist()
    return [float(x) for x in vec]


async def migrate_collection(
    *,
    user_id: str,
    source_collection: str,
    dest_collection: Optional[str],
    dsn: str,
    page_size: int,
    drop_dest: bool,
    rebuild_index: str,
    hnsw_m: int,
    hnsw_ef_construction: int,
    ivfflat_lists: int,
    embedding_dim_override: Optional[int],
    seed_demo: bool,
    dry_run: bool,
) -> MigrationResult:
    # Lazy imports to honour environment flags (--seed-demo etc.)
    from tldw_Server_API.app.core.config import settings
    from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import (
        VectorStoreConfig,
        VectorStoreType,
    )
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import (
        PGVectorAdapter,
    )

    dest_name = dest_collection or source_collection

    manager = ChromaDBManager(user_id=user_id, user_embedding_config=settings)
    try:
        client = getattr(manager, "client", None)
        if client is None:
            raise RuntimeError("ChromaDB manager did not expose a client")

        if seed_demo:
            _ensure_seed_demo(
                manager=manager,
                collection_name=source_collection,
                embedding_dim=embedding_dim_override or 8,
            )

        # Attempt to fetch existing collection without creating a new one accidentally.
        collection = _get_existing_collection(manager, client, source_collection)
        total = _safe_count(collection)

        if total == 0 and not seed_demo:
            raise RuntimeError(
                f"Source collection '{source_collection}' contains no vectors; aborting."
            )

        sample_vec, source_meta = _sample_collection(collection)
        embedding_dim = (
            embedding_dim_override
            or _extract_embedding_dimension(source_meta)
            or (len(sample_vec) if sample_vec is not None else None)
        )
        if not embedding_dim:
            raise RuntimeError(
                "Unable to determine embedding dimension; provide --embedding-dim."
            )
        embedding_dim = int(embedding_dim)

        dest_meta = {
            "embedding_dimension": embedding_dim,
        }
        if isinstance(source_meta, dict):
            for key in ("embedder_name", "embedder_version"):
                if source_meta.get(key):
                    dest_meta[key] = source_meta[key]

        if dry_run:
            print(
                f"[DRY RUN] Would migrate {total} vectors "
                f"from '{source_collection}' → '{dest_name}' (dim={embedding_dim})."
            )
            return MigrationResult(total, 0, dest_meta)

        cfg = VectorStoreConfig(
            store_type=VectorStoreType.PGVECTOR,
            connection_params={"dsn": dsn},
            embedding_dim=embedding_dim,
            user_id=user_id,
        )
        adapter = PGVectorAdapter(cfg)
        await adapter.initialize()

        if drop_dest:
            try:
                await adapter.delete_collection(dest_name)
            except Exception:
                pass

        await adapter.create_collection(dest_name, metadata=dest_meta)

        written = 0
        offset = 0
        seen_names: set[str] = set()
        seen_versions: set[str] = set()
        while True:
            batch = _fetch_batch(collection, limit=page_size, offset=offset)
            if not batch.ids:
                break
            _maybe_warn_embedder_metadata(
                batch.metadatas,
                dest_meta,
                seen_names,
                seen_versions,
            )
            await adapter.upsert_vectors(
                collection_name=dest_name,
                ids=batch.ids,
                vectors=batch.embeddings,
                documents=batch.documents,
                metadatas=batch.metadatas,
            )
            written += len(batch.ids)
            offset += len(batch.ids)
            print(
                f"Migrated {written}/{total} vectors "
                f"({min(100.0, (written / max(total, 1)) * 100.0):.1f}% complete)"
            )

        if rebuild_index.lower() in {"hnsw", "ivfflat", "drop"}:
            await adapter.rebuild_index(
                dest_name,
                index_type=rebuild_index,
                m=hnsw_m,
                ef_construction=hnsw_ef_construction,
                lists=ivfflat_lists,
            )

        stats = await adapter.get_collection_stats(dest_name)
        print(
            f"Completed migration: {written} vectors written. "
            f"Destination count={stats.get('count')}."
        )
        return MigrationResult(total, written, dest_meta)
    finally:
        try:
            manager.close()
        except Exception:
            pass


def _get_existing_collection(manager: Any, client: Any, name: str) -> Any:
    get_fn = getattr(client, "get_collection", None)
    if callable(get_fn):
        try:
            collection = get_fn(name=name)
            if _safe_count(collection) > 0:
                return collection
        except Exception:
            pass

    # Attempt persistent client fallback if files exist on disk
    path = Path(getattr(manager, "user_chroma_path", "") or "")
    if path.exists():
        try:
            import chromadb  # type: ignore

            persistent = chromadb.PersistentClient(path=str(path))
            collection = persistent.get_collection(name)
            if _safe_count(collection) > 0:
                print(f"Using persistent Chroma collection at {path} for '{name}'")
                return collection
        except Exception:
            pass

    # Fall back to manager accessor (which may create if missing)
    collection = manager.get_or_create_collection(name)
    if _safe_count(collection) == 0:
        print(
            f"Warning: collection '{name}' did not previously exist; continuing with empty collection."
        )
    return collection


def _ensure_seed_demo(manager: Any, collection_name: str, embedding_dim: int) -> None:
    collection = manager.get_or_create_collection(
        collection_name,
        collection_metadata={
            "embedding_dimension": embedding_dim,
            "embedder_name": "demo_embedder",
            "embedder_version": "demo_v1",
        },
    )
    if _safe_count(collection) > 0:
        return
    ids = []
    embeddings = []
    metadatas = []
    documents = []
    for idx in range(50):
        ids.append(f"demo-{idx}")
        embeddings.append(
            [
                round(random.random(), 6) for _ in range(embedding_dim)
            ]
        )
        metadatas.append(
            {
                "media_id": str(1 + idx // 5),
                "kind": "chunk",
                "demo": True,
            }
        )
        documents.append(f"Demo document {idx}")
    add_fn = getattr(collection, "add", None)
    if not callable(add_fn):
        raise RuntimeError("Chroma collection does not support add()")
    add_fn(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=documents,
    )
    if hasattr(collection, "modify"):
        try:
            collection.modify(
                metadata={
                    "embedding_dimension": embedding_dim,
                    "embedder_name": "demo_embedder",
                    "embedder_version": "demo_v1",
                }
            )
        except Exception:
            pass


def _safe_count(collection: Any) -> int:
    try:
        count_fn = getattr(collection, "count", None)
        if callable(count_fn):
            return int(count_fn())
    except Exception:
        pass
    return 0


def _sample_collection(collection: Any) -> Tuple[Optional[List[float]], Dict[str, Any]]:
    try:
        meta = getattr(collection, "metadata", None)
    except Exception:
        meta = None
    sample = None
    try:
        if hasattr(collection, "get") and callable(getattr(collection, "get")):
            res = collection.get(include=["embeddings"], limit=1)
            embs = res.get("embeddings") if isinstance(res, dict) else None
            if embs is not None:
                try:
                    # Normalize to list for length check
                    if hasattr(embs, "tolist"):
                        embs_list = embs.tolist()
                    else:
                        embs_list = list(embs)
                    if len(embs_list) > 0:
                        sample = _vector_to_list(embs_list[0])
                except Exception:
                    sample = None
    except Exception:
        sample = None
    return sample, meta if isinstance(meta, dict) else {}


def _extract_embedding_dimension(metadata: Dict[str, Any]) -> Optional[int]:
    if not metadata:
        return None
    for key in ("embedding_dimension", "dimensions", "vector_dim"):
        if metadata.get(key) is not None:
            try:
                return int(metadata[key])
            except Exception:
                continue
    return None


@dataclass
class Batch:
    ids: List[str]
    embeddings: List[List[float]]
    documents: List[str]
    metadatas: List[Dict[str, Any]]


def _fetch_batch(collection: Any, *, limit: int, offset: int) -> Batch:
    if not hasattr(collection, "get") or not callable(getattr(collection, "get")):
        raise RuntimeError("Collection does not support get() calls for pagination")
    # Chroma's include does not accept 'ids'; ids are returned by default
    res = collection.get(
        include=["embeddings", "metadatas", "documents"],
        limit=limit,
        offset=offset,
    )
    if not isinstance(res, dict):
        raise RuntimeError("Unexpected response type from collection.get()")
    # Avoid boolean evaluation of numpy arrays; handle None explicitly
    ids_raw = res.get("ids", None)
    if ids_raw is None:
        ids_list = []
    else:
        try:
            ids_list = list(ids_raw.tolist())  # type: ignore[attr-defined]
        except Exception:
            ids_list = list(ids_raw)
    ids = [str(i) for i in ids_list]

    emb_raw = res.get("embeddings", None)
    if emb_raw is None:
        embeddings_iter = []
    else:
        try:
            embeddings_iter = list(emb_raw.tolist())  # type: ignore[attr-defined]
        except Exception:
            embeddings_iter = list(emb_raw)
    embeddings = [_vector_to_list(vec) for vec in embeddings_iter]

    docs_raw = res.get("documents", None)
    if docs_raw is None:
        documents_iter = []
    else:
        try:
            documents_iter = list(docs_raw.tolist())  # type: ignore[attr-defined]
        except Exception:
            documents_iter = list(docs_raw)
    documents = [
        str(doc) if doc is not None else ""
        for doc in _pad_sequence(documents_iter, len(ids), default="")
    ]

    metas_raw = res.get("metadatas", None)
    if metas_raw is None:
        metadatas_iter = []
    else:
        try:
            metadatas_iter = list(metas_raw.tolist())  # type: ignore[attr-defined]
        except Exception:
            metadatas_iter = list(metas_raw)
    metadatas = [
        meta if isinstance(meta, dict) else {}
        for meta in _pad_sequence(metadatas_iter, len(ids), default={})
    ]
    return Batch(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def _maybe_warn_embedder_metadata(
    metadatas: List[Dict[str, Any]],
    collection_meta: Dict[str, Any],
    seen_names: set[str],
    seen_versions: set[str],
) -> None:
    if not metadatas:
        return
    names = {
        str(meta.get("embedder_name"))
        for meta in metadatas
        if isinstance(meta, dict) and meta.get("embedder_name")
    }
    versions = {
        str(meta.get("embedder_version"))
        for meta in metadatas
        if isinstance(meta, dict) and meta.get("embedder_version")
    }
    dest_name = collection_meta.get("embedder_name")
    dest_version = collection_meta.get("embedder_version")

    combined_names = seen_names | names
    combined_versions = seen_versions | versions

    if combined_names and len(combined_names) > 1 and len(seen_names) <= 1:
        print(
            f"Warning: multiple embedder_name values detected in metadata: {sorted(combined_names)}"
        )
    elif names and dest_name and dest_name not in names and dest_name not in seen_names:
        print(
            f"Warning: destination embedder_name '{dest_name}' does not match source metadata {sorted(names)}"
        )

    if combined_versions and len(combined_versions) > 1 and len(seen_versions) <= 1:
        print(
            f"Warning: multiple embedder_version values detected in metadata: {sorted(combined_versions)}"
        )
    elif versions and dest_version and dest_version not in versions and dest_version not in seen_versions:
        print(
            f"Warning: destination embedder_version '{dest_version}' does not match source metadata {sorted(versions)}"
        )

    seen_names.update(names)
    seen_versions.update(versions)


def _pad_sequence(seq: Sequence[Any], target: int, default: Any) -> List[Any]:
    if len(seq) >= target:
        return list(seq[:target])
    padded = list(seq)
    padded.extend([default] * (target - len(seq)))
    return padded


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate a Chroma collection to pgvector."
    )
    parser.add_argument("--user-id", required=True, help="User ID that owns the source collection")
    parser.add_argument("--collection", required=True, help="Source Chroma collection name")
    parser.add_argument("--dest-collection", help="Destination collection name (defaults to source)")
    parser.add_argument(
        "--pgvector-dsn",
        default=os.getenv("PGVECTOR_DSN") or os.getenv("PG_TEST_DSN") or os.getenv("PG_DSN"),
        help="PostgreSQL DSN for pgvector (env: PGVECTOR_DSN)",
    )
    parser.add_argument(
        "--page-size", type=int, default=500, help="Batch size for reading from Chroma"
    )
    parser.add_argument(
        "--drop-dest",
        action="store_true",
        help="Drop destination collection before migrating",
    )
    parser.add_argument(
        "--rebuild-index",
        default="hnsw",
        choices=["hnsw", "ivfflat", "drop", "skip"],
        help="Rebuild ANN index after migration",
    )
    parser.add_argument(
        "--hnsw-m",
        type=int,
        default=16,
        help="HNSW m parameter when rebuilding index",
    )
    parser.add_argument(
        "--hnsw-ef",
        type=int,
        default=200,
        help="HNSW ef_construction parameter when rebuilding index",
    )
    parser.add_argument(
        "--ivfflat-lists",
        type=int,
        default=100,
        help="IVFFLAT list count when rebuilding index",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        help="Override embedding dimension if it cannot be inferred",
    )
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Populate the Chroma collection with demo data when using the in-memory stub",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write to pgvector; print planned action instead",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.pgvector_dsn:
        parser.error("Provide pgvector DSN via --pgvector-dsn or PGVECTOR_DSN environment variable")

    if args.seed_demo:
        os.environ.setdefault("CHROMADB_FORCE_STUB", "true")

    rebuild = args.rebuild_index.lower()
    if rebuild == "skip":
        rebuild = "drop"

    try:
        result = asyncio.run(
            migrate_collection(
                user_id=str(args.user_id),
                source_collection=str(args.collection),
                dest_collection=str(args.dest_collection) if args.dest_collection else None,
                dsn=str(args.pgvector_dsn),
                page_size=max(1, int(args.page_size)),
                drop_dest=bool(args.drop_dest),
                rebuild_index=rebuild,
                hnsw_m=int(args.hnsw_m),
                hnsw_ef_construction=int(args.hnsw_ef),
                ivfflat_lists=int(args.ivfflat_lists),
                embedding_dim_override=int(args.embedding_dim) if args.embedding_dim else None,
                seed_demo=bool(args.seed_demo),
                dry_run=bool(args.dry_run),
            )
        )
    except KeyboardInterrupt:
        print("Migration cancelled by user.")
        return 1
    except Exception as exc:
        print(f"Migration failed: {exc}")
        return 1

    if not args.dry_run:
        summary = result.as_dict()
        print("Migration summary:", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
