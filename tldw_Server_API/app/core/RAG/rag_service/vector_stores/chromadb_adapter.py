"""
ChromaDB implementation of the VectorStoreAdapter interface.

This module provides a ChromaDB-specific implementation that wraps
the existing ChromaDBManager functionality.
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
import numpy as np

from .base import VectorStoreAdapter, VectorStoreConfig, VectorSearchResult, VectorStoreType

# Import existing ChromaDB implementation
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import (
    ChromaDBManager,
    get_default_chroma_manager
)
from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager


class ChromaDBAdapter(VectorStoreAdapter):
    """ChromaDB implementation of the vector store adapter."""

    def __init__(self, config: VectorStoreConfig):
        """
        Initialize ChromaDB adapter.

        Args:
            config: Vector store configuration
        """
        super().__init__(config)
        self.manager: Optional[ChromaDBManager] = None
        self._loop = None

    async def initialize(self) -> None:
        """Initialize ChromaDB connection."""
        try:
            # Always use a fresh manager bound to current settings (avoids cross-test leakage)
            from tldw_Server_API.app.core.config import settings
            user_id = self.config.user_id
            embedding_config = self.config.connection_params.get("embedding_config", {}).copy()
            embedding_config["USER_DB_BASE_DIR"] = settings.get("USER_DB_BASE_DIR")
            self.manager = ChromaDBManager(
                user_id=user_id,
                user_embedding_config=embedding_config
            )

            self._initialized = True
            self._loop = asyncio.get_event_loop()
            logger.info(f"ChromaDB adapter initialized for user {self.config.user_id}")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB adapter: {e}")
            raise

    async def create_collection(self, collection_name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Create a new collection in ChromaDB.

        Args:
            collection_name: Name of the collection to create
            metadata: Optional metadata for the collection
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Add embedding dimension to metadata
            if metadata is None:
                metadata = {}
            metadata["embedding_dimension"] = self.config.embedding_dim

            # ChromaDBManager's get_or_create_collection handles creation
            tm = get_tracing_manager()
            with tm.span("vectorstore.chromadb.create_collection", attributes={
                "vs.collection": collection_name,
                "vs.embed_dim": int(self.config.embedding_dim),
            }):
                collection = self.manager.get_or_create_collection(collection_name)

            # Update metadata if provided
            if metadata and hasattr(collection, 'modify'):
                collection.modify(metadata=metadata)

            logger.info(f"Created/accessed collection '{collection_name}'")

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    async def delete_collection(self, collection_name: str) -> None:
        """
        Delete a collection from ChromaDB.

        Args:
            collection_name: Name of the collection to delete
        """
        if not self._initialized:
            await self.initialize()

        try:
            self.manager.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            raise

    async def list_collections(self) -> List[str]:
        """
        List all collections in ChromaDB.

        Returns:
            List of collection names
        """
        if not self._initialized:
            await self.initialize()

        try:
            collections = self.manager.client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise

    async def upsert_vectors(
        self,
        collection_name: str,
        ids: List[str],
        vectors: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> None:
        """
        Insert or update vectors in ChromaDB collection.

        Args:
            collection_name: Target collection name
            ids: Unique identifiers for each vector
            vectors: Embedding vectors
            documents: Original text documents
            metadatas: Metadata for each vector
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Validate vectors
            self._validate_vectors(vectors)
            tm = get_tracing_manager()
            with tm.span("vectorstore.chromadb.upsert", attributes={
                "vs.collection": collection_name,
                "vs.count": int(len(vectors)),
                "vs.embed_dim": int(self.config.embedding_dim),
            }):
                # Store in ChromaDB using existing manager
                self.manager.store_in_chroma(
                    collection_name=collection_name,
                    texts=documents,
                    embeddings=vectors,
                    ids=ids,
                    metadatas=metadatas
                )
            logger.info(f"Upserted {len(vectors)} vectors to collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Failed to upsert vectors to '{collection_name}': {e}")
            raise

    async def delete_vectors(self, collection_name: str, ids: List[str]) -> None:
        """
        Delete vectors from ChromaDB collection.

        Args:
            collection_name: Target collection name
            ids: IDs of vectors to delete
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Use get-only to avoid creating missing collections implicitly
            collection = self.manager.client.get_collection(name=collection_name)
            # Verify the vectors exist before attempting deletion
            try:
                data = collection.get(ids=ids, include=[])
                existing_ids = set(data.get("ids") or []) if isinstance(data, dict) else set()
                missing = [vid for vid in ids if vid not in existing_ids]
                if missing:
                    raise ValueError(f"Vector(s) not found: {missing}")
            except Exception as e:
                # Bubble up as not-found for endpoint to translate to 404/400
                raise
            collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} vectors from collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete vectors from '{collection_name}': {e}")
            raise

    async def delete_by_filter(self, collection_name: str, filter: Dict[str, Any]) -> int:
        """Delete vectors by metadata filter (best-effort) in ChromaDB.

        Returns 0 when count is not available.
        """
        if not self._initialized:
            await self.initialize()
        try:
            collection = self.manager.get_or_create_collection(collection_name)
            delete = getattr(collection, 'delete', None)
            if callable(delete):
                delete(where=filter)  # type: ignore
            return 0
        except Exception as e:
            logger.error(f"Failed to delete by filter in '{collection_name}': {e}")
            return 0

    # Adapter-specific helper: list vectors with pagination
    async def list_vectors_paginated(self, collection_name: str, limit: int, offset: int, filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._initialized:
            await self.initialize()
        collection = self.manager.get_or_create_collection(collection_name)
        total = 0
        try:
            total = int(collection.count())
        except Exception:
            total = 0
        # Best-effort where filter if supported
        try:
            data = collection.get(limit=limit, offset=offset, include=["documents", "metadatas"], where=filter)  # type: ignore
        except Exception:
            data = collection.get(limit=limit, offset=offset, include=["documents", "metadatas"])  # type: ignore
        items = []
        if isinstance(data, dict) and data.get('ids'):
            for i, vid in enumerate(data['ids']):
                items.append({
                    'id': vid,
                    'content': (data.get('documents') or [""])[i] if data.get('documents') else "",
                    'metadata': (data.get('metadatas') or [{}])[i] if data.get('metadatas') else {},
                })
        return {'items': items, 'total': total}

    # Adapter-specific helper: get single vector by id
    async def get_vector(self, collection_name: str, vector_id: str) -> Optional[Dict[str, Any]]:
        if not self._initialized:
            await self.initialize()
        try:
            collection = self.manager.client.get_collection(name=collection_name)
            data = collection.get(ids=[vector_id], include=["documents", "metadatas"])  # type: ignore
            ids = data.get('ids') if isinstance(data, dict) else None
            if not ids:
                return None
            content = (data.get('documents') or [""])[0] if isinstance(data, dict) else ""
            metadata = (data.get('metadatas') or [{}])[0] if isinstance(data, dict) else {}
            return {'id': vector_id, 'content': content, 'metadata': metadata}
        except Exception:
            return None

    # Adapter-specific helper: for duplication - vectors plus embeddings
    async def list_vectors_with_embeddings_paginated(self, collection_name: str, limit: int, offset: int, filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._initialized:
            await self.initialize()
        collection = self.manager.get_or_create_collection(collection_name)
        total = 0
        try:
            total = int(collection.count())
        except Exception:
            total = 0
        try:
            data = collection.get(limit=limit, offset=offset, include=["embeddings", "documents", "metadatas"], where=filter)  # type: ignore
        except Exception:
            data = collection.get(limit=limit, offset=offset, include=["embeddings", "documents", "metadatas"])  # type: ignore
        items = []
        if isinstance(data, dict) and data.get('ids'):
            embs = data.get('embeddings') or []
            # Convert numpy arrays to lists if needed
            try:
                if hasattr(embs, 'tolist'):
                    embs = embs.tolist()
            except Exception:
                pass
            for i, vid in enumerate(data['ids']):
                vec = []
                try:
                    vec = list(embs[i]) if isinstance(embs[i], (list, tuple)) else (embs[i].tolist() if hasattr(embs[i], 'tolist') else [])
                except Exception:
                    vec = []
                items.append({
                    'id': vid,
                    'vector': vec,
                    'content': (data.get('documents') or [""])[i] if data.get('documents') else "",
                    'metadata': (data.get('metadatas') or [{}])[i] if data.get('metadatas') else {},
                })
        return {'items': items, 'total': total}

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> List[VectorSearchResult]:
        """
        Search for similar vectors in ChromaDB collection.

        Args:
            collection_name: Collection to search in
            query_vector: Query embedding vector
            k: Number of results to return
            filter: Optional metadata filters
            include_metadata: Whether to include metadata in results

        Returns:
            List of search results ordered by similarity
        """
        if not self._initialized:
            await self.initialize()

        try:
            collection = self.manager.get_or_create_collection(collection_name)

            # Prepare include fields
            include_fields = ["documents", "metadatas", "distances"]
            if not include_metadata:
                include_fields.remove("metadatas")

            # Perform search
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=k,
                where=filter,
                include=include_fields
            )

            # Convert to VectorSearchResult format
            search_results = []
            if results and results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    result = VectorSearchResult(
                        id=results['ids'][0][i],
                        content=results['documents'][0][i] if 'documents' in results else "",
                        metadata=results['metadatas'][0][i] if 'metadatas' in results else {},
                        distance=results['distances'][0][i] if 'distances' in results else 0.0,
                        score=1.0 - results['distances'][0][i] if 'distances' in results else 1.0
                    )
                    search_results.append(result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to search in collection '{collection_name}': {e}")
            raise

    async def multi_search(
        self,
        collection_patterns: List[str],
        query_vector: List[float],
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        Search across multiple collections matching patterns.

        Args:
            collection_patterns: Patterns to match collection names
            query_vector: Query embedding vector
            k: Number of results per collection
            filter: Optional metadata filters

        Returns:
            Merged list of search results from all matching collections
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get all collections
            all_collections = await self.list_collections()

            # Filter collections by patterns
            matching_collections = []
            for pattern in collection_patterns:
                if pattern.endswith("*"):
                    prefix = pattern[:-1]
                    matching_collections.extend(
                        [col for col in all_collections if col.startswith(prefix)]
                    )
                else:
                    if pattern in all_collections:
                        matching_collections.append(pattern)

            # Remove duplicates
            matching_collections = list(set(matching_collections))

            if not matching_collections:
                logger.warning(f"No collections found matching patterns: {collection_patterns}")
                return []

            # Search in all matching collections
            all_results = []
            for collection_name in matching_collections:
                try:
                    results = await self.search(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        k=k,
                        filter=filter,
                        include_metadata=True
                    )
                    # Add collection source to metadata
                    for result in results:
                        result.metadata["source_collection"] = collection_name
                    all_results.extend(results)
                except Exception as e:
                    logger.warning(f"Failed to search collection '{collection_name}': {e}")
                    continue

            # Sort by score and return top k overall
            all_results.sort(key=lambda x: x.score, reverse=True)
            return all_results[:k]

        except Exception as e:
            logger.error(f"Failed to perform multi-search: {e}")
            raise

    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics about a ChromaDB collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with stats (count, dimension, metadata)
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Use get-only call; raise if collection does not exist
            collection = self.manager.client.get_collection(name=collection_name)

            # Get collection count
            count = collection.count()

            # Get collection metadata
            metadata = collection.metadata if hasattr(collection, 'metadata') else {}

            # Determine dimension: prefer metadata 'embedding_dimension', else sample, else config
            dimension = None
            try:
                if metadata and "embedding_dimension" in metadata:
                    dimension = int(metadata["embedding_dimension"]) or None
            except Exception:
                dimension = None
            if dimension is None and count > 0:
                sample = collection.get(limit=1, include=["embeddings"])
                emb = sample.get("embeddings") if isinstance(sample, dict) else None
                try:
                    if isinstance(emb, list) and len(emb) > 0:
                        dimension = len(emb[0])
                    elif hasattr(emb, "__len__") and len(emb) > 0:
                        first = emb[0]
                        try:
                            dimension = len(first)
                        except Exception:
                            pass
                except Exception:
                    pass
            if dimension is None:
                dimension = self.config.embedding_dim

            return {
                "name": collection_name,
                "count": count,
                "dimension": dimension,
                "metadata": metadata,
                "distance_metric": self.config.distance_metric
            }

        except Exception as e:
            logger.error(f"Failed to get stats for collection '{collection_name}': {e}")
            raise

    async def optimize_collection(self, collection_name: str) -> None:
        """
        Optimize the collection for better search performance.
        ChromaDB handles optimization internally, so this is a no-op.

        Args:
            collection_name: Name of the collection to optimize
        """
        if not self._initialized:
            await self.initialize()

        # ChromaDB handles optimization automatically
        logger.info(f"ChromaDB auto-optimizes collection '{collection_name}'")

    async def get_index_info(self, collection_name: str) -> Dict[str, Any]:
        # Chroma manages internal index structures; return generic info
        stats = await self.get_collection_stats(collection_name)
        return {
            'backend': 'chroma',
            'index_type': 'managed',
            'dimension': stats.get('dimension', self.config.embedding_dim),
            'count': stats.get('count', 0),
        }

    def set_ef_search(self, value: int) -> int:
        # No-op for Chroma
        return int(value)

    async def close(self) -> None:
        """Close ChromaDB connection."""
        # ChromaDB manager handles cleanup internally
        self._initialized = False
        logger.info("ChromaDB adapter closed")
