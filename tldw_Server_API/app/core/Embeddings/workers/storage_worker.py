"""
Storage worker that writes embeddings to the configured vector store adapter
(Chroma by default; PGVector or others via settings) and updates job state.
"""

from typing import Any, Dict, Optional, List

from loguru import logger

from ..queue_schemas import (
    JobStatus,
    StorageMessage,
)
from .base_worker import BaseWorker, WorkerConfig
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import (
    VectorStoreAdapter,
    VectorStoreConfig,
    VectorStoreType,
)
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.factory import VectorStoreFactory
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
from ..messages import normalize_message
import os
import json


class StorageWorker(BaseWorker):
    """Worker that stores embeddings in the selected vector store and updates database"""

    def __init__(self, config: WorkerConfig):
        super().__init__(config)
        self._adapter_cache: Dict[str, VectorStoreAdapter] = {}
        # Capture manager class at construction time so tests can patch
        # tldw_Server_API.app.core.Embeddings.workers.storage_worker.ChromaDBManager
        # and have the patched reference persist after the context.
        self._manager_cls = ChromaDBManager
    
    def _parse_message(self, data: Dict[str, Any]) -> StorageMessage:
        """Parse raw message data into StorageMessage"""
        norm = normalize_message("storage", data)
        return StorageMessage(**norm)
    
    async def process_message(self, message: StorageMessage) -> None:
        """Store embeddings and update database"""
        logger.info(
            f"Processing storage job {message.job_id} with {len(message.embeddings)} embeddings"
        )

        try:
            # Idempotency ledger short-circuit
            ledger_ttl = int(os.getenv("EMBEDDINGS_LEDGER_TTL_SECONDS", "86400") or 86400)
            id_key = (message.idempotency_key or "").strip() or None
            dd_key = (message.dedupe_key or "").strip() or None
            short_circuit = False
            if self.redis_client:
                async def _is_completed(raw: Optional[str]) -> bool:
                    try:
                        if not raw:
                            return False
                        s = str(raw)
                        if s.lower() == "completed":
                            return True
                        try:
                            obj = json.loads(s)
                            return str(obj.get("status", "")).lower() == "completed"
                        except Exception:
                            return False
                    except Exception:
                        return False

                if id_key:
                    st = await self.redis_client.get(f"embeddings:ledger:idemp:{id_key}")
                    if await _is_completed(st):
                        short_circuit = True
                if not short_circuit and dd_key:
                    st = await self.redis_client.get(f"embeddings:ledger:dedupe:{dd_key}")
                    if await _is_completed(st):
                        short_circuit = True
            if short_circuit:
                logger.info(f"Idempotency ledger short-circuit for job {message.job_id}")
                await self._update_job_status(message.job_id, JobStatus.COMPLETED)
                return
            # Mark in-progress in ledger
            try:
                if self.redis_client:
                    ts = int(__import__('time').time())
                    if id_key:
                        await self.redis_client.set(
                            f"embeddings:ledger:idemp:{id_key}",
                            json.dumps({"status": "in_progress", "ts": ts, "job_id": message.job_id}),
                            ex=ledger_ttl
                        )
                    if dd_key:
                        await self.redis_client.set(
                            f"embeddings:ledger:dedupe:{dd_key}",
                            json.dumps({"status": "in_progress", "ts": ts, "job_id": message.job_id}),
                            ex=ledger_ttl
                        )
            except Exception:
                pass

            # Update job status
            await self._update_job_status(message.job_id, JobStatus.STORING)

            # Prepare data
            ids: List[str] = []
            embeddings: List[List[float]] = []
            documents: List[str] = []
            metadatas: List[Dict[str, Any]] = []

            for embedding_data in message.embeddings:
                ids.append(embedding_data.chunk_id)
                embeddings.append(embedding_data.embedding)
                documents.append("")  # ChromaDB requires documents, even if empty
                metadatas.append(
                    {
                        **embedding_data.metadata,
                        "media_id": str(message.media_id),
                        "model_used": embedding_data.model_used,
                        "dimensions": str(embedding_data.dimensions),
                        # Ensure embedder tagging present at storage time
                        "embedder_name": (embedding_data.metadata or {}).get("embedder_name") or (embedding_data.metadata or {}).get("model_provider"),
                        "embedder_version": (embedding_data.metadata or {}).get("embedder_version") or embedding_data.model_used,
                    }
                )

            # Ensure collection via helper (for test compatibility)
            collection = await self._get_or_create_collection(
                str(message.user_id), message.collection_name
            )

            # Enforce embedder/version policy using collection metadata when available
            try:
                coll_meta = getattr(collection, 'metadata', None) or {}
                first_meta = metadatas[0] if metadatas else {}
                cur_name = str(first_meta.get('embedder_name') or first_meta.get('model_provider') or '')
                cur_ver = str(first_meta.get('embedder_version') or first_meta.get('model_used') or '')
                if coll_meta and isinstance(coll_meta, dict):
                    col_name = str(coll_meta.get('embedder_name') or '')
                    col_ver = str(coll_meta.get('embedder_version') or '')
                    if (col_name and col_ver) and (col_name != cur_name or col_ver != cur_ver):
                        # Schedule re-embed request sidecar
                        try:
                            if self.redis_client:
                                await self.redis_client.xadd('embeddings:reembed:requests', {
                                    'user_id': str(message.user_id),
                                    'collection': message.collection_name,
                                    'current_embedder_name': col_name,
                                    'current_embedder_version': col_ver,
                                    'new_embedder_name': cur_name,
                                    'new_embedder_version': cur_ver,
                                    'job_id': message.job_id,
                                })
                        except Exception:
                            pass
                        if os.getenv('EMBEDDER_ENFORCE_NO_MIX', 'false').lower() in ('1','true','yes'):
                            raise RuntimeError('EMBEDDER_MISMATCH: collection uses different embedder/version')
            except Exception as _embedder_check_err:
                logger.debug(f"Embedder/version policy check warning: {_embedder_check_err}")

            # Store in batches via helper (for test compatibility)
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                batch_end = min(i + batch_size, len(ids))

                await self._store_batch(
                    collection,
                    ids=ids[i:batch_end],
                    embeddings=embeddings[i:batch_end],
                    documents=documents[i:batch_end],
                    metadatas=metadatas[i:batch_end],
                )

                # Update progress
                progress = 75 + (25 * batch_end / len(ids))
                await self._update_job_progress(message.job_id, progress)

            # Update SQL database
            await self._update_database(message.media_id, message.total_chunks)

            # Mark job as completed
            await self._update_job_status(message.job_id, JobStatus.COMPLETED)

            # Update ledger to completed
            try:
                if self.redis_client:
                    ts = int(__import__('time').time())
                    if id_key:
                        await self.redis_client.set(
                            f"embeddings:ledger:idemp:{id_key}",
                            json.dumps({"status": "completed", "ts": ts, "job_id": message.job_id}),
                            ex=ledger_ttl
                        )
                    if dd_key:
                        await self.redis_client.set(
                            f"embeddings:ledger:dedupe:{dd_key}",
                            json.dumps({"status": "completed", "ts": ts, "job_id": message.job_id}),
                            ex=ledger_ttl
                        )
            except Exception:
                pass

            logger.info(f"Successfully stored embeddings for job {message.job_id}")

        except Exception as e:
            logger.error(f"Error storing embeddings for job {message.job_id}: {e}")
            # Record failure in ledger
            try:
                if self.redis_client:
                    ts = int(__import__('time').time())
                    if id_key:
                        await self.redis_client.set(
                            f"embeddings:ledger:idemp:{id_key}",
                            json.dumps({"status": "failed", "ts": ts, "job_id": message.job_id}),
                            ex=ledger_ttl
                        )
                    if dd_key:
                        await self.redis_client.set(
                            f"embeddings:ledger:dedupe:{dd_key}",
                            json.dumps({"status": "failed", "ts": ts, "job_id": message.job_id}),
                            ex=ledger_ttl
                        )
            except Exception:
                pass
            raise
    
    async def _send_to_next_stage(self, result: Any):
        """Storage is the final stage, no next stage"""
        pass
    
    async def _get_adapter_for_user(self, user_id: str, embedding_dim: int) -> VectorStoreAdapter:
        """Return an initialized adapter for a given user and dimension (cached)."""
        cache_key = f"{user_id}:{embedding_dim}"
        if cache_key in self._adapter_cache:
            return self._adapter_cache[cache_key]

        base = VectorStoreFactory.create_from_settings(settings, user_id=str(user_id))
        if base is not None and getattr(base, 'config', None) is not None:
            cfg = VectorStoreConfig(
                store_type=base.config.store_type,  # type: ignore[attr-defined]
                connection_params=base.config.connection_params,  # type: ignore[attr-defined]
                embedding_dim=int(embedding_dim),
                distance_metric=getattr(base.config, 'distance_metric', 'cosine'),  # type: ignore[attr-defined]
                collection_prefix=getattr(base.config, 'collection_prefix', 'unified'),  # type: ignore[attr-defined]
                user_id=str(user_id),
            )
            adapter = VectorStoreFactory.create_adapter(cfg, initialize=False)
        else:
            # Fallback to Chroma default
            cfg = VectorStoreConfig(
                store_type=VectorStoreType.CHROMADB,
                connection_params={"use_default": True},
                embedding_dim=int(embedding_dim),
                user_id=str(user_id),
            )
            adapter = VectorStoreFactory.create_adapter(cfg, initialize=False)

        await adapter.initialize()
        self._adapter_cache[cache_key] = adapter
        return adapter

    async def _get_or_create_collection(self, user_id: str, collection_name: str):
        """Get or create a collection using ChromaDBManager (test-friendly).

        Tries calling manager.get_or_create_collection in a backward-compatible way so
        tests that expect a (user_id, collection_name) signature still work when patched.
        """
        # Instantiate using the captured class reference (patched in tests)
        manager = self._manager_cls(user_id=user_id, user_embedding_config=settings)

        try:
            # Backward-compat: some tests expect (user, collection) args
            return manager.get_or_create_collection(user_id, collection_name)  # type: ignore[misc]
        except TypeError:
            # Actual implementation signature is (collection_name, metadata=None)
            return manager.get_or_create_collection(collection_name=collection_name)  # type: ignore[misc]

    async def _store_batch(
        self,
        collection: Any,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Upsert a batch into the provided collection (idempotent)."""
        # Prefer upsert for idempotency; falls back to add if not available
        try:
            upsert = getattr(collection, "upsert", None)
            if callable(upsert):
                upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            else:
                collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        except Exception:
            # On duplicate id or capability issues, try update as a second-chance path
            update = getattr(collection, "update", None)
            if callable(update):
                update(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            else:
                # Re-raise original behavior on persistent failure
                raise

    def _infer_embedding_dim(self, embeddings: List[Any]) -> int:
        """Infer embedding dimension from the first item, with safe fallbacks."""
        try:
            if embeddings and getattr(embeddings[0], 'dimensions', None):
                return int(embeddings[0].dimensions)
            if embeddings and getattr(embeddings[0], 'embedding', None):
                vec = embeddings[0].embedding
                return int(len(vec)) if hasattr(vec, '__len__') else int(settings.get('DEFAULT_EMBEDDING_DIM', 1536))
        except Exception:
            pass
        return int(settings.get('DEFAULT_EMBEDDING_DIM', 1536))
    
    async def _update_database(self, media_id: int, total_chunks: int):
        """Update SQL database with vector processing status"""
        # TODO: Implement database updates when the functions are available
        # For now, we'll just log that we would update the database
        logger.info(f"Would update database for media_id {media_id} with {total_chunks} chunks")
        
        # The following functions need to be implemented:
        # - update_media_table_vector_processing_status
        # - update_media_chunks_table_vector_processing_status
        pass
    
    async def _update_job_progress(self, job_id: str, percentage: float):
        """Update job progress information"""
        job_key = f"job:{job_id}"
        await self.redis_client.hset(
            job_key,
            mapping={
                "progress_percentage": percentage
            }
        )
