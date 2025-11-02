"""
Simplified RAG Module Test Configuration

Focused on testing only the unified pipeline that's actually in use.
"""

# Note: pgvector fixtures are registered at the top-level tests/conftest.py.
# Keep this file free of pytest_plugins to avoid pytest deprecation warnings.

import tempfile
from pathlib import Path
from typing import Dict, Any, Generator
from unittest.mock import MagicMock, AsyncMock

import pytest

# Import actual MediaDatabase for integration tests
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.core.RAG.rag_service.metrics_collector import QueryMetrics

# =====================================================================
# Test Markers
# =====================================================================

def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: Unit tests with minimal mocking")
    config.addinivalue_line("markers", "integration: Integration tests with real components")
    # Optionally register pgvector fixtures if available in this environment
    try:
        # Importing the helpers module registers its fixtures for this test package
        import tldw_Server_API.tests.helpers.pgvector  # noqa: F401
    except Exception:
        # If unavailable, tests that require pgvector will be skipped by their own guards
        pass

# =====================================================================
# Cross-suite fixtures (mirrors Embeddings fixtures used by RAG tests)
# =====================================================================

@pytest.fixture
def disable_heavy_startup():
    """Deprecated no-op fixture retained for backward compatibility."""
    yield


@pytest.fixture
def admin_user():
    """Provide an admin user override for routes that require it."""
    from tldw_Server_API.app.main import app  # lazy import to avoid startup costs
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User

    async def _admin():
        return User(id=42, username="admin", email="a@x", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = _admin
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_request_user, None)

# =====================================================================
# Database Fixtures
# =====================================================================

@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_media.db"
        yield db_path

@pytest.fixture
def media_database(temp_db_path) -> Generator[MediaDatabase, None, None]:
    """Create a real MediaDatabase instance for testing."""
    db = MediaDatabase(
        db_path=str(temp_db_path),
        client_id="test_client"
    )
    db.initialize_db()
    try:
        yield db
    finally:
        try:
            db.close_connection()
        except Exception:
            pass

@pytest.fixture
def populated_media_db(media_database) -> MediaDatabase:
    """Create a MediaDatabase with test data."""
    # Add test media items
    from datetime import datetime
    from uuid import uuid4

    test_items = [
        {
            "media_id": str(uuid4()),
            "title": "Introduction to RAG Systems",
            "content": "Retrieval-Augmented Generation (RAG) combines large language models with external knowledge retrieval.",
            "media_type": "article",
            "author": "AI Research Team",
            "ingestion_date": datetime.now().isoformat()
        },
        {
            "media_id": str(uuid4()),
            "title": "Vector Database Tutorial",
            "content": "Vector databases are essential for semantic search in RAG systems.",
            "media_type": "video",
            "author": "Database Expert",
            "ingestion_date": datetime.now().isoformat()
        }
    ]

    for item in test_items:
        media_database.add_media_with_keywords(
            title=item["title"],
            content=item["content"],
            media_type=item["media_type"],
            author=item.get("author"),
            ingestion_date=item.get("ingestion_date")
        )

    return media_database

# =====================================================================
# Mock Fixtures for Unit Tests
# =====================================================================

@pytest.fixture
def mock_llm():
    """Mock LLM for unit tests."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "This is a generated response based on the retrieved context."
    return mock_llm

# Additional fixtures used by unified pipeline tests
@pytest.fixture
def mock_media_database(media_database) -> MediaDatabase:
    """Alias fixture to match test naming expectations."""
    return media_database

@pytest.fixture
def mock_semantic_cache():
    """Simple mock semantic cache with get/find_similar methods."""
    from unittest.mock import MagicMock
    cache = MagicMock()
    cache.get = MagicMock()
    cache.find_similar = MagicMock()
    return cache

# =====================================================================
# Common Sample Fixtures for RAG tests
# =====================================================================

@pytest.fixture
def sample_documents():
    """Provide a small set of sample Document objects."""
    return [
        Document(id="1", content="First doc", metadata={"initial_score": 0.8}, source=DataSource.MEDIA_DB, score=0.8),
        Document(id="2", content="Second doc", metadata={"initial_score": 0.6}, source=DataSource.MEDIA_DB, score=0.6),
        Document(id="3", content="Third doc", metadata={"initial_score": 0.4}, source=DataSource.MEDIA_DB, score=0.4),
    ]

@pytest.fixture
def query_metrics():
    """Provide a QueryMetrics instance for timer/metrics tests."""
    import time as _time
    return QueryMetrics(query_id="q-test", query="test", timestamp=_time.time(), total_duration=0.0)

@pytest.fixture
def mock_multi_db_retriever(sample_documents):
    """Mock MultiDatabaseRetriever with retrieve returning sample docs."""
    m = MagicMock()
    m.retrieve = AsyncMock(return_value=sample_documents)
    return m

@pytest.fixture
def mock_vector_store():
    return MagicMock()

@pytest.fixture
def mock_embeddings():
    return MagicMock()

# =====================================================================
# RAG Configuration Fixtures
# =====================================================================

@pytest.fixture
def minimal_rag_config() -> Dict[str, Any]:
    """Minimal RAG configuration for testing."""
    return {
        "query": "What is RAG?",
        "top_k": 5
    }

@pytest.fixture
def typical_rag_config() -> Dict[str, Any]:
    """Typical production RAG configuration."""
    return {
        "query": "How does retrieval-augmented generation work?",
        "top_k": 10,
        "enable_cache": True,
        "enable_reranking": True,
        "temperature": 0.7
    }
