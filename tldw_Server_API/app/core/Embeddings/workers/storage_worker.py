"""Storage worker for embeddings pipeline."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from tldw_Server_API.app.core.Embeddings.workers.base_worker import BaseWorker, WorkerConfig


class StorageWorker(BaseWorker):
    """Minimal storage worker used for embeddings idempotency checks."""

    def __init__(self, config: WorkerConfig) -> None:
        super().__init__(config)

    def _store_batch(
        self,
        *,
        collection: Any,
        ids: List[str],
        embeddings: List[List[float]],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[dict]] = None,
    ) -> None:
        """Store embeddings batch with upsert fallback logic."""
        if hasattr(collection, "upsert"):
            try:
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
                return
            except AttributeError:
                pass

        if hasattr(collection, "add"):
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        if hasattr(collection, "update"):
            try:
                collection.update(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
            except AttributeError:
                pass
            except Exception:
                raise
        elif not hasattr(collection, "add"):
            raise AttributeError("collection does not support add/update/upsert")
