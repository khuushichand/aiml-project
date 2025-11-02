"""
Factory for creating vector store adapters.

This module provides a factory pattern for instantiating the appropriate
vector store adapter based on configuration.
"""

from typing import Dict, Type, Optional
import inspect
from loguru import logger

from .base import VectorStoreAdapter, VectorStoreConfig, VectorStoreType
from .chromadb_adapter import ChromaDBAdapter
try:
    from .pgvector_adapter import PGVectorAdapter
except Exception:
    PGVectorAdapter = None  # Optional


class VectorStoreFactory:
    """Factory for creating vector store adapters."""

    # Registry of available adapters
    _adapters: Dict[VectorStoreType, Type[VectorStoreAdapter]] = {
        VectorStoreType.CHROMADB: ChromaDBAdapter,
        # Future adapters:
        # VectorStoreType.PINECONE: PineconeAdapter,
        # VectorStoreType.WEAVIATE: WeaviateAdapter,
        # VectorStoreType.QDRANT: QdrantAdapter,
        # VectorStoreType.FAISS: FAISSAdapter,
    }
    if PGVectorAdapter is not None:
        _adapters[VectorStoreType.PGVECTOR] = PGVectorAdapter

    @classmethod
    def create_adapter(
        cls,
        config: VectorStoreConfig,
        initialize: bool = True
    ) -> VectorStoreAdapter:
        """
        Create a vector store adapter based on configuration.

        Args:
            config: Vector store configuration
            initialize: Whether to initialize the adapter immediately

        Returns:
            Configured vector store adapter instance

        Raises:
            ValueError: If the requested vector store type is not supported
        """
        adapter_class = cls._adapters.get(config.store_type)

        if not adapter_class:
            available = ", ".join([t.value for t in cls._adapters.keys()])
            raise ValueError(
                f"Unsupported vector store type: {config.store_type}. "
                f"Available types: {available}"
            )

        logger.info(f"Creating {config.store_type.value} adapter")
        adapter = adapter_class(config)

        if initialize:
            # If async initialization is needed, it should be done separately
            logger.info(f"Adapter created (initialization pending)")

        return adapter

    @classmethod
    def register_adapter(
        cls,
        store_type: VectorStoreType,
        adapter_class: Type[VectorStoreAdapter]
    ) -> None:
        """
        Register a new adapter type.

        This allows for dynamic registration of custom adapters.

        Args:
            store_type: Vector store type identifier
            adapter_class: Adapter class to register
        """
        cls._adapters[store_type] = adapter_class
        logger.info(f"Registered adapter for {store_type.value}")

    @classmethod
    def get_available_stores(cls) -> list[str]:
        """
        Get list of available vector store types.

        Returns:
            List of available store type names
        """
        return [store_type.value for store_type in cls._adapters.keys()]

    @classmethod
    def create_from_settings(
        cls,
        settings: Dict,
        user_id: str = "0"
    ) -> Optional[VectorStoreAdapter]:
        """
        Create an adapter from application settings.

        Args:
            settings: Application settings dictionary
            user_id: User identifier for multi-tenant scenarios

        Returns:
            Configured adapter or None if not configured
        """
        # Extract vector store configuration from settings
        vector_store_type = settings.get("RAG", {}).get("vector_store_type", "chromadb")

        # Get embedding configuration
        embedding_config = settings.get("EMBEDDING_CONFIG", {})
        embedding_dim = embedding_config.get("embedding_dimension", 384)

        # Get connection parameters based on store type
        connection_params = {}
        if vector_store_type == "chromadb":
            connection_params = {
                "use_default": True,  # Use existing singleton
                "embedding_config": embedding_config
            }
        elif vector_store_type in ("pgvector", "postgres", "postgresql"):
            # Collect PG connection params from settings
            rag_cfg = settings.get("RAG", {})
            pg_cfg = rag_cfg.get("pgvector", {}) if isinstance(rag_cfg.get("pgvector"), dict) else {}
            connection_params = {
                "host": pg_cfg.get("host", "localhost"),
                "port": pg_cfg.get("port", 5432),
                "database": pg_cfg.get("database", "postgres"),
                "user": pg_cfg.get("user", "postgres"),
                "password": pg_cfg.get("password", ""),
                "sslmode": pg_cfg.get("sslmode", "prefer"),
                # Optional DSN override
                "dsn": pg_cfg.get("dsn"),
            }
        # Add other store types here as needed

        # Create configuration
        try:
            store_type_enum = VectorStoreType(vector_store_type if vector_store_type != "postgres" and vector_store_type != "postgresql" else "pgvector")
        except ValueError:
            logger.warning(f"Unknown vector store type: {vector_store_type}, defaulting to ChromaDB")
            store_type_enum = VectorStoreType.CHROMADB

        config = VectorStoreConfig(
            store_type=store_type_enum,
            connection_params=connection_params,
            embedding_dim=embedding_dim,
            distance_metric=settings.get("RAG", {}).get("distance_metric", "cosine"),
            collection_prefix=settings.get("RAG", {}).get("collection_prefix", "unified"),
            user_id=user_id
        )

        return cls.create_adapter(config, initialize=False)


def create_from_settings_for_user(settings: Dict, user_id: str = "0") -> Optional[VectorStoreAdapter]:
    """
    Helper that adapts to runtime monkeypatches of create_from_settings.

    Tests frequently replace VectorStoreFactory.create_from_settings with classmethods
    whose parameter names differ from the production definition. This wrapper inspects
    the bound signature and supplies keyword arguments so the call remains compatible.
    """
    bound = VectorStoreFactory.create_from_settings
    try:
        sig = inspect.signature(bound)
        params = list(sig.parameters.values())
    except (TypeError, ValueError):
        params = []

    kwargs = {}
    try:
        if params:
            kwargs[params[0].name] = settings
        if len(params) > 1:
            kwargs[params[1].name] = user_id
        if kwargs:
            return bound(**kwargs)  # type: ignore[arg-type]
    except TypeError:
        # Fall through to positional attempt
        pass

    # Fallback to positional invocation (best-effort)
    try:
        return bound(settings, user_id)  # type: ignore[misc]
    except TypeError:
        return bound(settings)  # type: ignore[misc]
