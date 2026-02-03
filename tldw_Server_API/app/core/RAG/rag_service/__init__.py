"""
RAG (Retrieval-Augmented Generation) Service

This package provides a functional pipeline implementation of RAG functionality
for the tldw_server application. It uses composable functions that can be
combined into custom pipelines for different use cases.

Main components:
- functional_pipeline.py: Core pipeline functions and presets
- config.py: Configuration management
- types.py: Type definitions
- database_retrievers.py: Database retrieval strategies
- query_expansion.py: Query expansion strategies
- advanced_reranking.py: Document reranking
- Various feature modules for caching, monitoring, etc.
"""

# Expose commonly patched submodules for tests
from . import (
    advanced_reranking,  # noqa: F401
    chromadb_optimizer,  # noqa: F401
    semantic_cache,  # noqa: F401
)
from .config import RAGConfig
from .types import DataSource, Document, SearchResult

__all__ = [
    'RAGConfig', 'DataSource', 'Document', 'SearchResult',
    'semantic_cache', 'chromadb_optimizer', 'advanced_reranking'
]
