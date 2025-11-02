"""
Embeddings Module Test Configuration and Fixtures

Provides fixtures for testing embeddings functionality including
vector generation, worker orchestration, and ChromaDB integration.
"""

import os
import copy
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Generator, Optional
from unittest.mock import MagicMock, AsyncMock, Mock, patch
import json
import numpy as np
from datetime import datetime
import uuid
import types

import pytest
from fastapi.testclient import TestClient
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
import chromadb

# sentence-transformers is installed in this environment; no stub needed.

# Import actual embeddings components for integration tests
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
    _model_cache_subdir_name,
    HFModelCfg,
)
from tldw_Server_API.app.core.config import settings
# Delay heavy/buggy imports to fixtures to avoid import-time errors
try:
    from tldw_Server_API.app.core.Embeddings.queue_schemas import (
        JobRequest,
        JobStatus,
        JobResult,
        JobType
    )
except Exception:
    JobRequest = None
    JobStatus = None
    JobResult = None
    JobType = None
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

# =====================================================================
# Test Markers
# =====================================================================

def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: Unit tests with minimal mocking")
    config.addinivalue_line("markers", "integration: Integration tests with real components")
    config.addinivalue_line("markers", "property: Property-based tests")
    config.addinivalue_line("markers", "slow: Tests that take > 1 second")
    config.addinivalue_line("markers", "requires_gpu: Tests requiring GPU/CUDA")
    config.addinivalue_line("markers", "worker: Worker-specific tests")

# =====================================================================
# Environment Configuration
# =====================================================================

@pytest.fixture(scope="session")
def test_env_vars():
    """Set up test environment variables."""
    original_env = os.environ.copy()

    # Set test mode
    os.environ["TEST_MODE"] = "true"
    os.environ["DEFAULT_LLM_PROVIDER"] = "openai"
    os.environ["SINGLE_USER_API_KEY"] = "test-api-key-12345"
    os.environ["API_BEARER"] = "test-api-key-12345"
    os.environ["EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"
    os.environ["CHROMA_BATCH_SIZE"] = "100"
    os.environ["EMBEDDING_BATCH_SIZE"] = "32"
    os.environ["MAX_WORKERS"] = "2"
    os.environ["CHROMADB_FORCE_STUB"] = "true"
    os.environ.setdefault("CHROMADB_DEFAULT_TENANT", "default_tenant")
    os.environ["TESTING"] = "true"

    # Isolate user DB base dir to a temporary location to avoid migrating/using repo DBs
    tmp_user_base = tempfile.mkdtemp(prefix="emb_user_db_base_")
    os.environ["USER_DB_BASE_DIR"] = tmp_user_base
    # Also isolate AuthNZ main DB to the same temp base (not strictly required here but safer)
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tmp_user_base, 'users.db')}"

    # Ensure local embedding assets are available and wired into runtime config
    download_root = Path(os.environ.get("TLDW_EMBEDDING_MODELS_DIR", Path.cwd() / "models" / "embeddings")).expanduser()
    default_model = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    required_models = {
        default_model,
        "sentence-transformers/all-MiniLM-L6-v2",
        "sentence-transformers/all-mpnet-base-v2",
        "BAAI/bge-small-en-v1.5",
    }

    local_model_dirs: Dict[str, Path] = {}
    missing_models = []
    for model_id in sorted(required_models):
        candidate_dir = download_root / model_id.replace("/", "__")
        if candidate_dir.exists():
            local_model_dirs[model_id] = candidate_dir.resolve()
        else:
            missing_models.append((model_id, candidate_dir))

    if missing_models:
        missing_str = ", ".join(f"{mid} (expected at {path})" for mid, path in missing_models)
        raise RuntimeError(
            "Local embedding assets are required for embeddings tests. "
            f"Missing models: {missing_str}. Run Helper_Scripts/download_embedding_models.py first."
        )

    cache_root = Path(tempfile.mkdtemp(prefix="embeddings_cache_")).resolve()
    hf_cache_root = cache_root / "huggingface_cache"

    for model_id, src_dir in local_model_dirs.items():
        target_dir = hf_cache_root / _model_cache_subdir_name(model_id)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            continue
        try:
            os.symlink(src_dir, target_dir, target_is_directory=True)
        except (AttributeError, OSError, NotImplementedError):
            shutil.copytree(src_dir, target_dir, dirs_exist_ok=True)

    os.environ["EMBEDDINGS_MODEL_STORAGE_DIR"] = str(cache_root)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_cache_root)
    os.environ.setdefault("HF_HOME", str(cache_root))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    embedding_config_present = "EMBEDDING_CONFIG" in settings
    original_embedding_config = copy.deepcopy(settings.get("EMBEDDING_CONFIG", {})) if embedding_config_present else None
    storage_dir_present = "EMBEDDINGS_MODEL_STORAGE_DIR" in settings
    original_storage_dir_setting = settings.get("EMBEDDINGS_MODEL_STORAGE_DIR") if storage_dir_present else None

    configured_models = sorted(local_model_dirs.keys())
    hf_model_configs: Dict[str, HFModelCfg] = {}
    def _hf_cfg(model_identifier: str) -> HFModelCfg:
        return HFModelCfg(
            provider="huggingface",
            model_name_or_path=model_identifier,
            trust_remote_code=False,
            hf_cache_dir_subpath="huggingface_cache",
        )

    for model_id in configured_models:
        hf_model_configs[model_id] = _hf_cfg(model_id)

    # Provide aliases so OpenAI ids fall back to local HF models during tests
    alias_targets = {
        "text-embedding-3-small": "sentence-transformers/all-MiniLM-L6-v2",
        "openai:text-embedding-3-small": "sentence-transformers/all-MiniLM-L6-v2",
        "text-embedding-3-large": "sentence-transformers/all-mpnet-base-v2",
        "openai:text-embedding-3-large": "sentence-transformers/all-mpnet-base-v2",
        "openai:text-embedding-ada-002": "sentence-transformers/all-mpnet-base-v2",
    }
    for alias, target in alias_targets.items():
        if target not in hf_model_configs:
            hf_model_configs[target] = _hf_cfg(target)
        hf_model_configs[alias] = _hf_cfg(hf_model_configs[target].model_name_or_path)

    new_embedding_config = dict(original_embedding_config or {})
    new_embedding_config.update({
        "embedding_provider": "huggingface",
        "embedding_model": default_model,
        "default_model_id": default_model,
        "available_models": configured_models,
        "model_storage_base_dir": str(cache_root),
        "default_provider": "huggingface",
        "default_model": default_model,
    })
    existing_models = dict(new_embedding_config.get("models", {}) or {})
    existing_models.update(hf_model_configs)
    new_embedding_config["models"] = existing_models
    settings["EMBEDDING_CONFIG"] = new_embedding_config
    settings["EMBEDDINGS_MODEL_STORAGE_DIR"] = str(cache_root)

    try:
        yield
    finally:
        if embedding_config_present:
            settings["EMBEDDING_CONFIG"] = original_embedding_config
        else:
            try:
                del settings["EMBEDDING_CONFIG"]
            except AttributeError:
                pass

        if storage_dir_present:
            try:
                settings["EMBEDDINGS_MODEL_STORAGE_DIR"] = original_storage_dir_setting
            except Exception:
                pass
        else:
            try:
                # Only attempt deletion if present to avoid KeyError under
                # concurrent config cache resets in other test packages.
                if "EMBEDDINGS_MODEL_STORAGE_DIR" in settings:
                    del settings["EMBEDDINGS_MODEL_STORAGE_DIR"]
            except Exception:
                pass

        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)

        # Cleanup temporary dirs
        for path in (cache_root, tmp_user_base):
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass

# =====================================================================
# Autouse safety fixtures (mirrored from legacy embeddings tests)
# =====================================================================

@pytest.fixture(autouse=True)
def _sanitize_jsonschema_module(monkeypatch):
    """Ensure sys.modules['jsonschema'] is hashable (Hypothesis introspects it)."""
    mod = sys.modules.get("jsonschema")
    if mod is not None and not isinstance(mod, types.ModuleType):
        wrapper = types.ModuleType("jsonschema")
        for attr in ("validate",):
            try:
                setattr(wrapper, attr, getattr(mod, attr))
            except Exception:
                pass
        monkeypatch.setitem(sys.modules, "jsonschema", wrapper)


@pytest.fixture(autouse=True)
def _patch_hypothesis_local_constants(monkeypatch):
    """Guard Hypothesis against unhashable stubs left in sys.modules."""
    try:
        from hypothesis.internal.conjecture import providers as _providers  # type: ignore
    except Exception:
        return

    original = getattr(_providers, "_get_local_constants", None)
    if not callable(original):
        return

    def _safe_get_local_constants():  # type: ignore[return-type]
        try:
            return original()
        except TypeError:
            for name, module in list(sys.modules.items()):
                try:
                    hash(module)
                    continue
                except Exception:
                    pass
                if isinstance(module, types.SimpleNamespace):
                    wrapper = types.ModuleType(name)
                    for attr in dir(module):
                        if attr.startswith("__") and attr.endswith("__"):
                            continue
                        try:
                            setattr(wrapper, attr, getattr(module, attr))
                        except Exception:
                            pass
                    sys.modules[name] = wrapper
            try:
                return original()
            except Exception:
                return getattr(_providers, "_local_constants", None)

    monkeypatch.setattr(_providers, "_get_local_constants", _safe_get_local_constants, raising=False)


@pytest.fixture(autouse=True)
def _reset_chromadb_shared_state():
    """Reset shared Chromadb client caches between tests to avoid cross-test leakage."""
    try:
        from chromadb.api import client as _client  # local import to avoid circulars
        _client.SharedSystemClient.clear_system_cache()
    except Exception:
        pass
    yield
    try:
        from chromadb.api import client as _client  # type: ignore
        _client.SharedSystemClient.clear_system_cache()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _chromadb_inmemory_clients(monkeypatch):
    """Route chromadb Client/PersistentClient calls to the in-memory stub for deterministic tests."""
    try:
        import chromadb as _chromadb
    except Exception:
        yield
        return

    try:
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import _InMemoryChromaClient
    except Exception:
        # If the embeddings library isn't available yet, skip patching (tests will use default clients).
        yield
        return

    stub_cache: Dict[str, _InMemoryChromaClient] = {}

    def _stub_persistent_client(*args, **kwargs):
        key = str(kwargs.get("path") or "default")
        cli = stub_cache.get(key)
        if cli is None:
            cli = _InMemoryChromaClient()
            stub_cache[key] = cli
        return cli

    def _stub_client(*args, **kwargs):
        return _InMemoryChromaClient()

    monkeypatch.setattr(_chromadb, "PersistentClient", _stub_persistent_client, raising=False)
    monkeypatch.setattr(_chromadb, "Client", _stub_client, raising=False)
    yield


@pytest.fixture(scope="session", autouse=True)
def _chromadb_stub_clients_session():
    """Global safeguard so unittest-style tests also get the in-memory chroma stub."""
    try:
        import chromadb as _chromadb
    except Exception:
        yield
        return

    try:
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import _InMemoryChromaClient
    except Exception:
        yield
        return

    original_persistent = getattr(_chromadb, "PersistentClient", None)
    original_client = getattr(_chromadb, "Client", None)

    def _stub_persistent_client(*args, **kwargs):
        return _InMemoryChromaClient()

    def _stub_client(*args, **kwargs):
        return _InMemoryChromaClient()

    if original_persistent is not None:
        _chromadb.PersistentClient = _stub_persistent_client  # type: ignore[attr-defined]
    if original_client is not None:
        _chromadb.Client = _stub_client  # type: ignore[attr-defined]
    try:
        yield
    finally:
        if original_persistent is not None:
            _chromadb.PersistentClient = original_persistent  # type: ignore[attr-defined]
        if original_client is not None:
            _chromadb.Client = original_client  # type: ignore[attr-defined]

# =====================================================================
# Vector/Embedding Fixtures
# =====================================================================

@pytest.fixture
def sample_embedding() -> List[float]:
    """Generate a sample embedding vector."""
    # Standard 384-dimensional vector for all-MiniLM-L6-v2
    np.random.seed(42)
    return np.random.randn(384).tolist()

@pytest.fixture
def sample_embeddings_batch() -> List[List[float]]:
    """Generate a batch of embedding vectors."""
    np.random.seed(42)
    return [np.random.randn(384).tolist() for _ in range(10)]

@pytest.fixture
def text_chunks() -> List[str]:
    """Sample text chunks for embedding."""
    return [
        "This is the first chunk of text about machine learning.",
        "The second chunk discusses natural language processing.",
        "Deep learning models require significant computational resources.",
        "Transfer learning helps reduce training time and improves accuracy.",
        "Fine-tuning pre-trained models is a common practice.",
        "Embeddings capture semantic meaning in vector space.",
        "Similarity search finds related documents using vector distance.",
        "ChromaDB is a vector database for storing embeddings.",
        "RAG systems combine retrieval and generation.",
        "Context window limits affect model performance."
    ]

@pytest.fixture
def document_metadata() -> List[Dict[str, Any]]:
    """Sample metadata for documents."""
    return [
        {"source": "doc1.pdf", "page": 1, "chunk_id": 0},
        {"source": "doc1.pdf", "page": 2, "chunk_id": 1},
        {"source": "doc2.txt", "page": 1, "chunk_id": 0},
        {"source": "doc2.txt", "page": 1, "chunk_id": 1},
        {"source": "video1.mp4", "timestamp": 120, "chunk_id": 0},
        {"source": "video1.mp4", "timestamp": 240, "chunk_id": 1},
        {"source": "article.html", "section": "intro", "chunk_id": 0},
        {"source": "article.html", "section": "main", "chunk_id": 1},
        {"source": "notes.md", "heading": "Overview", "chunk_id": 0},
        {"source": "notes.md", "heading": "Details", "chunk_id": 1}
    ]

# =====================================================================
# ChromaDB Fixtures
# =====================================================================

@pytest.fixture
def chroma_client():
    """Return the same per-user Chroma client the API uses."""
    from tldw_Server_API.app.core.config import settings as app_settings

    prev_force_stub = os.environ.get("CHROMADB_FORCE_STUB")
    os.environ["CHROMADB_FORCE_STUB"] = "1"
    prev_default_tenant = os.environ.get("CHROMADB_DEFAULT_TENANT")
    os.environ.setdefault("CHROMADB_DEFAULT_TENANT", "default_tenant")

    user_base = app_settings.get("USER_DB_BASE_DIR") or os.environ.get("USER_DB_BASE_DIR")
    if not user_base:
        user_base = tempfile.mkdtemp(prefix="api_chroma_base_")
        os.environ["USER_DB_BASE_DIR"] = user_base

    embedding_cfg = app_settings.get("EMBEDDING_CONFIG", {}).copy()
    embedding_cfg["USER_DB_BASE_DIR"] = user_base

    user_id = str(app_settings.get("SINGLE_USER_FIXED_ID", "1"))
    manager = ChromaDBManager(user_id=user_id, user_embedding_config=embedding_cfg)
    client = manager.client

    try:
        yield client
    finally:
        if prev_force_stub is None:
            os.environ.pop("CHROMADB_FORCE_STUB", None)
        else:
            os.environ["CHROMADB_FORCE_STUB"] = prev_force_stub
        if prev_default_tenant is None:
            os.environ.pop("CHROMADB_DEFAULT_TENANT", None)
        else:
            os.environ["CHROMADB_DEFAULT_TENANT"] = prev_default_tenant
        try:
            if hasattr(client, "close"):
                client.close()  # type: ignore[attr-defined]
            else:
                system = getattr(client, "_system", None)
                stop_fn = getattr(system, "stop", None) if system else None
                if callable(stop_fn):
                    stop_fn()
        except Exception:
            pass

@pytest.fixture
def chroma_collection(chroma_client):
    """Create a test collection in ChromaDB."""
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    return chroma_client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

@pytest.fixture
def populated_chroma_collection(chroma_collection, sample_embeddings_batch, text_chunks, document_metadata):
    """Create a ChromaDB collection with test data."""
    ids = [f"doc_{i}" for i in range(len(text_chunks))]

    chroma_collection.add(
        embeddings=sample_embeddings_batch,
        documents=text_chunks,
        metadatas=document_metadata,
        ids=ids
    )

    return chroma_collection

@pytest.fixture
def chromadb_manager(chroma_client):
    """Create a ChromaDBManager instance for testing."""
    manager = ChromaDBManager()
    manager.client = chroma_client
    manager.collection = None
    return manager

# =====================================================================
# Worker Fixtures
# =====================================================================

@pytest.fixture
def mock_embedding_worker():
    """Create a mock embedding worker."""
    worker = MagicMock()
    worker.process = AsyncMock(return_value=np.random.randn(10, 384).tolist())
    worker.batch_size = 32
    worker.model_name = "sentence-transformers/all-MiniLM-L6-v2"
    return worker

@pytest.fixture
def mock_chunking_worker():
    """Create a mock chunking worker."""
    worker = MagicMock()
    worker.process = AsyncMock(return_value=[
        {"text": "chunk1", "metadata": {"chunk_id": 0}},
        {"text": "chunk2", "metadata": {"chunk_id": 1}}
    ])
    worker.chunk_size = 500
    worker.chunk_overlap = 50
    return worker

@pytest.fixture
def mock_storage_worker():
    """Create a mock storage worker."""
    worker = MagicMock()
    worker.store = AsyncMock(return_value={"status": "success", "stored_count": 10})
    worker.retrieve = AsyncMock(return_value=[])
    return worker

@pytest.fixture
def worker_orchestrator(mock_embedding_worker, mock_chunking_worker, mock_storage_worker):
    """Create a worker orchestrator with mock workers."""
    # Lazy import to avoid import-time errors; fallback to simple object
    try:
        from tldw_Server_API.app.core.Embeddings.worker_orchestrator import WorkerOrchestrator
        orchestrator = WorkerOrchestrator()
    except Exception:
        orchestrator = type("WorkerOrchestrator", (), {})()
    orchestrator.embedding_worker = mock_embedding_worker
    orchestrator.chunking_worker = mock_chunking_worker
    orchestrator.storage_worker = mock_storage_worker
    orchestrator.is_initialized = True
    return orchestrator

# =====================================================================
# Job/Queue Fixtures
# =====================================================================

@pytest.fixture
def sample_job_request() -> Dict[str, Any]:
    """Create a sample job request (dict fallback if schemas unavailable)."""
    if JobRequest and JobType:
        return JobRequest(
            job_id=str(uuid.uuid4()),
            job_type=JobType.EMBEDDING,
            media_id=123,
            collection_name="test_collection",
            data={
                "text": "Sample text for embedding",
                "metadata": {"source": "test.txt"}
            },
            priority=5,
            created_at=datetime.utcnow()
        )
    return {
        "job_id": str(uuid.uuid4()),
        "job_type": "EMBEDDING",
        "media_id": 123,
        "collection_name": "test_collection",
        "data": {"text": "Sample text for embedding", "metadata": {"source": "test.txt"}},
        "priority": 5,
        "created_at": datetime.utcnow().isoformat()
    }

@pytest.fixture
def batch_job_requests() -> List[Any]:
    """Create multiple job requests."""
    jobs = []
    for i in range(5):
        if JobRequest and JobType:
            jobs.append(JobRequest(
                job_id=str(uuid.uuid4()),
                job_type=JobType.EMBEDDING if i % 2 == 0 else JobType.CHUNKING,
                media_id=100 + i,
                collection_name="test_collection",
                data={
                    "text": f"Text for job {i}",
                    "metadata": {"source": f"doc{i}.txt"}
                },
                priority=i,
                created_at=datetime.utcnow()
            ))
        else:
            jobs.append({
                "job_id": str(uuid.uuid4()),
                "job_type": "EMBEDDING" if i % 2 == 0 else "CHUNKING",
                "media_id": 100 + i,
                "collection_name": "test_collection",
                "data": {"text": f"Text for job {i}", "metadata": {"source": f"doc{i}.txt"}},
                "priority": i,
                "created_at": datetime.utcnow().isoformat()
            })
    return jobs

@pytest.fixture
def job_result() -> Dict[str, Any]:
    """Create a sample job result."""
    if JobResult and JobStatus:
        return JobResult(
            job_id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            result={
                "embeddings_generated": 10,
                "chunks_processed": 5,
                "time_taken": 1.23
            },
            error=None,
            completed_at=datetime.utcnow()
        )
    return {
        "job_id": str(uuid.uuid4()),
        "status": "COMPLETED",
        "result": {"embeddings_generated": 10, "chunks_processed": 5, "time_taken": 1.23},
        "error": None,
        "completed_at": datetime.utcnow().isoformat()
    }

# =====================================================================
# Database Fixtures
# =====================================================================

@pytest.fixture
def media_database(test_client) -> MediaDatabase:
    """Return the shared MediaDatabase used by API routes."""
    from tldw_Server_API.app.main import app

    db = getattr(app.state, "test_media_db", None)
    if db is None:
        base_dir = Path(os.environ.get("USER_DB_BASE_DIR", tempfile.mkdtemp(prefix="fallback_media_db_")))
        user_dir = base_dir / "1"
        user_dir.mkdir(parents=True, exist_ok=True)
        db_path = user_dir / "Media_DB_v2.db"
        db = MediaDatabase(db_path=str(db_path), client_id="test_client")
        db.initialize_db()
        app.state.test_media_db = db
    return db

@pytest.fixture
def populated_media_database(media_database) -> MediaDatabase:
    """Create a media database with test data."""
    # Add test media items
    for i in range(5):
        media_database.add_media_with_keywords(
            title=f"Test Document {i}",
            content=f"This is the content of document {i}. It contains various information about topic {i}.",
            media_type="document",
            author=f"Author {i}",
            ingestion_date=datetime.utcnow().isoformat()
        )

    return media_database

# =====================================================================
# Model Configuration Fixtures
# =====================================================================

@pytest.fixture
def embedding_models():
    """Available embedding models configuration."""
    return {
        "sentence-transformers/all-MiniLM-L6-v2": {
            "dimension": 384,
            "max_tokens": 256,
            "batch_size": 32
        },
        "sentence-transformers/all-mpnet-base-v2": {
            "dimension": 768,
            "max_tokens": 384,
            "batch_size": 16
        },
        "BAAI/bge-small-en-v1.5": {
            "dimension": 384,
            "max_tokens": 512,
            "batch_size": 32
        },
        "openai/text-embedding-ada-002": {
            "dimension": 1536,
            "max_tokens": 8191,
            "batch_size": 100
        }
    }

@pytest.fixture
def chunking_strategies():
    """Available chunking strategies."""
    return {
        "fixed": {
            "chunk_size": 500,
            "chunk_overlap": 50
        },
        "sentence": {
            "sentences_per_chunk": 5,
            "min_chunk_size": 100
        },
        "semantic": {
            "similarity_threshold": 0.7,
            "max_chunk_size": 1000
        },
        "token": {
            "tokens_per_chunk": 256,
            "token_overlap": 25
        }
    }

# =====================================================================
# Mock API Responses
# =====================================================================

@pytest.fixture
def mock_openai_embedding_response():
    """Mock OpenAI embedding API response."""
    return {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "index": 0,
                "embedding": np.random.randn(1536).tolist()
            }
        ],
        "model": "text-embedding-ada-002",
        "usage": {
            "prompt_tokens": 8,
            "total_tokens": 8
        }
    }

@pytest.fixture
def mock_huggingface_embedding_response():
    """Mock HuggingFace embedding API response."""
    return np.random.randn(5, 384).tolist()  # Batch of 5 embeddings

# =====================================================================
# Performance Testing Fixtures
# =====================================================================

@pytest.fixture
def large_text_corpus() -> List[str]:
    """Generate a large corpus for performance testing."""
    base_texts = [
        "Machine learning algorithms can identify patterns in data.",
        "Natural language processing enables computers to understand text.",
        "Deep neural networks have revolutionized computer vision.",
        "Reinforcement learning trains agents through trial and error.",
        "Transfer learning leverages knowledge from pre-trained models."
    ]

    # Replicate and vary to create larger corpus
    corpus = []
    for i in range(100):
        for base in base_texts:
            corpus.append(f"{base} Variation {i}: {base.replace('.', f' in iteration {i}.')}")

    return corpus

@pytest.fixture
def performance_metrics():
    """Track performance metrics during tests."""
    return {
        "embedding_time": [],
        "storage_time": [],
        "retrieval_time": [],
        "memory_usage": [],
        "batch_processing_time": []
    }

# =====================================================================
# Circuit Breaker and Rate Limiting Fixtures
# =====================================================================

@pytest.fixture
def mock_circuit_breaker():
    """Mock circuit breaker for testing."""
    breaker = MagicMock()
    breaker.is_open = False
    breaker.call = AsyncMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
    breaker.record_success = Mock()
    breaker.record_failure = Mock()
    return breaker

@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter for testing."""
    limiter = MagicMock()
    limiter.check_rate_limit = AsyncMock(return_value=True)
    limiter.consume = AsyncMock()
    limiter.reset = Mock()
    return limiter

# =====================================================================
# API Client Fixtures
# =====================================================================

@pytest.fixture
def test_client(test_env_vars):
    """Create a test client for the FastAPI app with DB override to isolate per-user database."""
    from tldw_Server_API.app.main import app

    # Prepare a clean per-user database to avoid repo-level migrations
    base_dir = os.environ.get("USER_DB_BASE_DIR") or tempfile.mkdtemp(prefix="emb_user_db_base_client_")
    user_dir = Path(base_dir) / "1"
    user_dir.mkdir(parents=True, exist_ok=True)
    per_user_db_path = user_dir / "Media_DB_v2.db"

    db = MediaDatabase(db_path=str(per_user_db_path), client_id="test_client")
    db.initialize_db()

    async def _override_db(current_user=None):
        return db

    app.dependency_overrides[get_media_db_for_user] = _override_db
    app.state.test_media_db = db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        yield client
    finally:
        # Clean up override and close DB
        app.dependency_overrides.pop(get_media_db_for_user, None)
        app.state.test_media_db = None
        try:
            db.close_connection()
        except Exception:
            pass

@pytest.fixture
def auth_headers():
    """Authentication headers for API requests."""
    api_key = os.environ.get("SINGLE_USER_API_KEY", "test-api-key-12345")
    return {
        "X-API-KEY": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def mock_embedding_backends():
    """Patch embedding generation calls to avoid external provider dependencies."""

    fake_vector = [0.05] * 384

    async def fake_async_embeddings(*args, **kwargs):
        texts = kwargs.get("texts") if "texts" in kwargs else (args[0] if args else [])
        if isinstance(texts, str):
            texts = [texts]
        return [fake_vector.copy() for _ in texts]

    def fake_sync_embeddings(texts, *args, **kwargs):
        payloads = texts if isinstance(texts, list) else [texts]
        return [fake_vector.copy() for _ in payloads]

    with patch(
        'tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced.create_embeddings_batch_async',
        new=AsyncMock(side_effect=fake_async_embeddings)
    ), patch(
        'tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced.create_embeddings_batch',
        new=fake_sync_embeddings
    ), patch(
        'tldw_Server_API.app.api.v1.endpoints.vector_stores_openai._get_embeddings_fn',
        return_value=fake_sync_embeddings
    ):
        yield

# =====================================================================
# Cleanup Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Cleanup any temporary files or resources
    import gc
    gc.collect()
