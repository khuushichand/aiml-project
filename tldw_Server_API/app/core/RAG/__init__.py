"""
RAG public API exports for the unified pipeline.

Prefer these unified helpers over archived presets.
"""

from .rag_service.types import DataSource, Document, SearchResult
from .rag_service.unified_pipeline import (
    unified_rag_pipeline,
    unified_batch_pipeline,
    simple_search,
    advanced_search,
)

__all__ = [
    'DataSource',
    'Document',
    'SearchResult',
    'unified_rag_pipeline',
    'unified_batch_pipeline',
    'simple_search',
    'advanced_search',
]
