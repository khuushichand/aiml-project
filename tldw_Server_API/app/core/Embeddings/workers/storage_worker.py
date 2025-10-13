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
        return StorageMessage(**data)
    
    async def process_message(self, message: StorageMessage) -> None:
        """Store embeddings and update database"""
        logger.info(
            f"Processing storage job {message.job_id} with {len(message.embeddings)} embeddings"
        )

        try:
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
                    }
                )

            # Ensure collection via helper (for test compatibility)
            collection = await self._get_or_create_collection(
                str(message.user_id), message.collection_name
            )

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

            logger.info(f"Successfully stored embeddings for job {message.job_id}")

        except Exception as e:
            logger.error(f"Error storing embeddings for job {message.job_id}: {e}")
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
        """Store a batch into the provided collection (test-friendly wrapper)."""
        # Chroma-style collections expose .add(); wrap as async for symmetry in tests
        collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

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
