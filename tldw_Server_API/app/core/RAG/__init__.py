"""
RAG public API exports for the unified pipeline.

Prefer these unified helpers over archived presets.
"""

from .rag_service.profiles import (
    RAGProfile,
    apply_profile_to_kwargs,
    get_multi_tenant_safe_kwargs,
    get_profile,
    get_profile_kwargs,
    list_profiles,
)
from .rag_service.types import DataSource, Document, SearchResult
from .rag_service.unified_pipeline import (
    advanced_search,
    simple_search,
    unified_batch_pipeline,
    unified_rag_pipeline,
)

__all__ = [
    'DataSource',
    'Document',
    'SearchResult',
    'unified_rag_pipeline',
    'unified_batch_pipeline',
    'simple_search',
    'advanced_search',
    'RAGProfile',
    'list_profiles',
    'get_profile',
    'get_profile_kwargs',
    'apply_profile_to_kwargs',
    'get_multi_tenant_safe_kwargs',
]
