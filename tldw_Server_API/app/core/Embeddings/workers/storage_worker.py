"""
Storage worker that writes embeddings to the configured vector store adapter
(Chroma by default; PGVector or others via settings) and updates job state.
"""

from typing import Any, Dict, Optional, List

from loguru import logger
from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager

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
        logger.bind(job_id=message.job_id, stage="storage").info(
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

            # If the associated document was soft-deleted, remove vectors and short-circuit
            try:
                if await self._is_media_soft_deleted(int(message.media_id)):
                    logger.warning(f"Media {message.media_id} is soft-deleted; removing vectors and completing job {message.job_id}.")
                    # Remove any vectors for this media_id from the user-specific collection
                    first_meta = metadatas[0] if metadatas else {}
                    hint = {
                        "embedder_name": first_meta.get("embedder_name", ""),
                        "embedder_version": first_meta.get("embedder_version", ""),
                    }
                    collection = await self._get_or_create_collection(
                        str(message.user_id), message.collection_name, hint
                    )
                    try:
                        delete = getattr(collection, "delete", None)
                        if callable(delete):
                            delete(where={"media_id": str(message.media_id)})
                    except Exception as _del_err:
                        logger.error(f"Error removing vectors for soft-deleted media {message.media_id}: {_del_err}")
                    await self._update_job_status(message.job_id, JobStatus.COMPLETED)
                    # Update ledger to completed for idempotency
                    try:
                        ledger_ttl = int(os.getenv("EMBEDDINGS_LEDGER_TTL_SECONDS", "86400") or 86400)
                        ts = int(__import__('time').time())
                        if message.idempotency_key:
                            await self.redis_client.set(
                                f"embeddings:ledger:idemp:{message.idempotency_key}",
                                json.dumps({"status": "completed", "ts": ts, "job_id": message.job_id}),
                                ex=ledger_ttl
                            )
                        if message.dedupe_key:
                            await self.redis_client.set(
                                f"embeddings:ledger:dedupe:{message.dedupe_key}",
                                json.dumps({"status": "completed", "ts": ts, "job_id": message.job_id}),
                                ex=ledger_ttl
                            )
                    except Exception:
                        pass
                    return
            except Exception:
                # Non-fatal: if DB unavailable, proceed with normal store path
                pass

            # Ensure collection via helper (for test compatibility)
            # Provide embedder/version metadata hint on first creation
            first_meta = metadatas[0] if metadatas else {}
            cur_name = str(first_meta.get('embedder_name') or first_meta.get('model_provider') or '')
            cur_ver = str(first_meta.get('embedder_version') or first_meta.get('model_used') or '')
            col_meta_hint = {"embedder_name": cur_name, "embedder_version": cur_ver} if (cur_name or cur_ver) else None
            # Include embedding dimension in metadata hint when available
            try:
                inferred_dim = self._infer_embedding_dim(message.embeddings) if message.embeddings else None
            except Exception:
                inferred_dim = None
            if inferred_dim:
                cm = dict(col_meta_hint or {})
                cm["embedding_dimension"] = int(inferred_dim)
            else:
                cm = col_meta_hint
            collection = await self._get_or_create_collection(
                str(message.user_id), message.collection_name, cm
            )

            # Enforce embedder/version policy using collection metadata when available
            try:
                coll_meta = getattr(collection, 'metadata', None) or {}
                # If collection lacks embedder metadata, set it now (best-effort)
                if (not coll_meta.get('embedder_name') or not coll_meta.get('embedder_version')) and (cur_name or cur_ver):
                    try:
                        modify = getattr(collection, 'modify', None)
                        if callable(modify):
                            modify(metadata={"embedder_name": cur_name, "embedder_version": cur_ver})
                            # refresh local view
                            coll_meta = getattr(collection, 'metadata', coll_meta)
                    except Exception:
                        pass
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

            # Validate collection embedding dimension strictly and surface hard error on mismatch
            try:
                target_dim = int(inferred_dim) if inferred_dim else None
                if target_dim:
                    cmeta = getattr(collection, 'metadata', {}) or {}
                    expected = None
                    if isinstance(cmeta, dict) and cmeta.get('embedding_dimension'):
                        try:
                            expected = int(cmeta.get('embedding_dimension'))
                        except Exception:
                            expected = None
                    if expected is None and hasattr(collection, 'get') and callable(getattr(collection, 'get')):
                        # Sample one vector to infer existing dim when metadata absent
                        try:
                            sample = collection.get(limit=1, include=['embeddings'])
                            emb = None
                            if isinstance(sample, dict):
                                embs = sample.get('embeddings')
                                if embs and isinstance(embs, list) and len(embs) > 0:
                                    emb = embs[0]
                            if emb and hasattr(emb, '__len__'):
                                expected = int(len(emb))
                        except Exception:
                            expected = None
                    if expected is not None and expected != target_dim:
                        logger.error(f"Embedding dimension mismatch for collection '{message.collection_name}': expected {expected}, new {target_dim}")
                        raise RuntimeError("EMBEDDING_DIMENSION_MISMATCH")
            except Exception:
                # Fail fast per requirement
                raise

            # Store in batches with adaptive sizing based on observed latency
            import time as _time
            batch_size = min(100, max(1, len(ids)))
            i = 0
            tm = get_tracing_manager()
            while i < len(ids):
                batch_end = min(i + batch_size, len(ids))
                t0 = _time.perf_counter()
                async with tm.async_span(
                    "embeddings.storage.upsert_batch",
                    attributes={
                        "emb.collection": str(message.collection_name),
                        "emb.batch_size": int(batch_end - i),
                        "emb.job_id": str(message.job_id),
                    },
                ):
                    await self._store_batch(
                        collection,
                        ids=ids[i:batch_end],
                        embeddings=embeddings[i:batch_end],
                        documents=documents[i:batch_end],
                        metadatas=metadatas[i:batch_end],
                    )
                t1 = _time.perf_counter()
                # Update progress
                progress = 75 + (25 * batch_end / len(ids))
                await self._update_job_progress(message.job_id, progress)
                # Adapt batch size conservatively: speed up on very fast writes, slow down on slow ones
                elapsed = t1 - t0
                if elapsed < 0.10 and batch_size < 500:
                    batch_size = min(500, batch_size * 2)
                elif elapsed > 1.50 and batch_size > 10:
                    batch_size = max(10, batch_size // 2)
                i = batch_end

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

            logger.bind(job_id=message.job_id, stage="storage").info(
                f"Successfully stored embeddings for job {message.job_id}"
            )

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
    
    async def _is_media_soft_deleted(self, media_id: int) -> bool:
        """Return True if the media_id is marked deleted in Media DB.

        Best-effort check; returns False on any error.
        """
        try:
            from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase  # lazy import
            db_path = os.getenv("MEDIA_DB_PATH", "Databases/Media_DB_v2.db")
            db = MediaDatabase(db_path=db_path, client_id="embeddings_storage_worker")
            row = db.execute_query("SELECT deleted FROM Media WHERE id = ?", (int(media_id),)).fetchone()
            try:
                db.close_connection()
            except Exception:
                pass
            if row is None:
                return False
            try:
                # tuple or sqlite row
                val = row[0] if isinstance(row, (tuple, list)) else (row.get('deleted') if hasattr(row, 'get') else None)
            except Exception:
                val = None
            return bool(int(val)) if val is not None else False
        except Exception:
            return False
    
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

    async def _get_or_create_collection(self, user_id: str, collection_name: str, collection_metadata: Optional[Dict[str, Any]] = None):
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
            # Actual implementation signature is (collection_name, collection_metadata=None)
            try:
                return manager.get_or_create_collection(collection_name=collection_name, collection_metadata=collection_metadata)  # type: ignore[misc]
            except TypeError:
                # Fallback without metadata
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
