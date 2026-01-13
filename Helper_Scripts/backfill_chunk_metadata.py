#!/usr/bin/env python3
"""
Backfill normalized chunk metadata in Chroma collections.

Example:
  python Helper_Scripts/backfill_chunk_metadata.py --user-id 1 --all --dry-run
  python Helper_Scripts/backfill_chunk_metadata.py --user-id 1 --collection user_1_media_embeddings
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tldw_Server_API.app.core.Embeddings.chunk_metadata_backfill import normalize_chunk_metadata


logger = logging.getLogger("chunk_metadata_backfill")


def _list_collection_names(client: Any) -> List[str]:
    names: List[str] = []
    try:
        collections = client.list_collections()
    except Exception as exc:
        raise RuntimeError(f"Failed to list collections: {exc}") from exc
    for col in collections or []:
        if isinstance(col, str):
            names.append(col)
        else:
            name = getattr(col, "name", None)
            if name:
                names.append(str(name))
    return names


def _get_existing_collection(manager: Any, client: Any, name: str) -> Any:
    try:
        return client.get_collection(name=name)
    except Exception:
        return manager.get_or_create_collection(name)


def _iter_collection_batches(
    collection: Any,
    *,
    page_size: int,
    limit: Optional[int],
    include: List[str],
) -> Iterable[Tuple[List[str], List[Dict[str, Any]], Dict[str, Any]]]:
    offset = 0
    processed = 0
    while True:
        if limit is not None:
            remaining = max(limit - processed, 0)
            if remaining == 0:
                break
            batch_limit = min(page_size, remaining)
        else:
            batch_limit = page_size
        result = collection.get(limit=batch_limit, offset=offset, include=include)
        ids = list(result.get("ids") or [])
        if not ids:
            break
        metadatas = list(result.get("metadatas") or [])
        if len(metadatas) < len(ids):
            metadatas = metadatas + [{}] * (len(ids) - len(metadatas))
        processed += len(ids)
        offset += len(ids)
        yield ids, metadatas, result


def backfill_collection(
    *,
    collection: Any,
    page_size: int,
    limit: Optional[int],
    dry_run: bool,
    fill_offsets: bool,
    default_chunk_type: Optional[str],
) -> Tuple[int, int]:
    supports_update = callable(getattr(collection, "update", None))
    include = ["metadatas"] if supports_update else ["metadatas", "documents", "embeddings"]
    total_updates = 0
    total_seen = 0

    for ids, metadatas, raw in _iter_collection_batches(
        collection,
        page_size=page_size,
        limit=limit,
        include=include,
    ):
        updates: List[Dict[str, Any]] = []
        update_ids: List[str] = []
        for idx, meta in enumerate(metadatas):
            total_seen += 1
            updated, changed = normalize_chunk_metadata(
                meta,
                fill_offsets=fill_offsets,
                default_chunk_type=default_chunk_type,
            )
            if changed:
                update_ids.append(ids[idx])
                updates.append(updated)

        if not update_ids:
            continue

        if dry_run:
            logger.info("Dry-run: would update %d items", len(update_ids))
            total_updates += len(update_ids)
            continue

        if supports_update:
            collection.update(ids=update_ids, metadatas=updates)
        else:
            documents = raw.get("documents")
            embeddings = raw.get("embeddings") or []
            if len(embeddings) < len(ids):
                raise RuntimeError("Collection lacks embeddings; cannot upsert without update support.")
            emb_map = {ids[i]: embeddings[i] for i in range(len(ids))}
            batch_embs = [emb_map[i] for i in update_ids]
            if documents:
                doc_map = {ids[i]: documents[i] for i in range(len(documents))}
                if all(i in doc_map for i in update_ids):
                    batch_docs = [doc_map[i] for i in update_ids]
                    collection.upsert(
                        ids=update_ids,
                        metadatas=updates,
                        documents=batch_docs,
                        embeddings=batch_embs,
                    )
                else:
                    collection.upsert(
                        ids=update_ids,
                        metadatas=updates,
                        embeddings=batch_embs,
                    )
            else:
                collection.upsert(
                    ids=update_ids,
                    metadatas=updates,
                    embeddings=batch_embs,
                )

        total_updates += len(update_ids)

    return total_seen, total_updates


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill chunk metadata in Chroma collections.")
    parser.add_argument("--user-id", required=True, help="User ID for the ChromaDB manager")
    parser.add_argument("--collection", action="append", help="Collection name to backfill (repeatable)")
    parser.add_argument("--all", action="store_true", help="Process all collections for the user")
    parser.add_argument("--page-size", type=int, default=200, help="Batch size for collection.get")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of items to scan")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without updating metadata")
    parser.add_argument("--fill-offsets", dest="fill_offsets", action="store_true", default=True)
    parser.add_argument("--no-fill-offsets", dest="fill_offsets", action="store_false")
    parser.add_argument(
        "--default-chunk-type",
        default=None,
        help="Set chunk_type when missing and no heuristic matches (optional)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    if not args.all and not args.collection:
        raise SystemExit("Provide --collection or --all.")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from tldw_Server_API.app.core.config import settings
    from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager

    manager = ChromaDBManager(user_id=args.user_id, user_embedding_config=settings)
    client = getattr(manager, "client", None)
    if client is None:
        raise SystemExit("ChromaDB manager did not expose a client")

    if args.collection:
        collection_names = args.collection
    else:
        collection_names = _list_collection_names(client)

    if not collection_names:
        logger.info("No collections found to process.")
        return 0

    total_seen = 0
    total_updates = 0
    for name in collection_names:
        logger.info("Processing collection '%s'", name)
        collection = _get_existing_collection(manager, client, name)
        seen, updated = backfill_collection(
            collection=collection,
            page_size=args.page_size,
            limit=args.limit,
            dry_run=args.dry_run,
            fill_offsets=args.fill_offsets,
            default_chunk_type=args.default_chunk_type,
        )
        logger.info("Collection '%s': scanned=%d updated=%d", name, seen, updated)
        total_seen += seen
        total_updates += updated

    logger.info("Backfill complete. scanned=%d updated=%d", total_seen, total_updates)
    return 0


if __name__ == "__main__":
    sys.exit(main())
