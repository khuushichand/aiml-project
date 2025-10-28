"""
VectorStores integration test configuration.

Ensures each test run uses an isolated ChromaDB base directory and test mode,
so PersistentClient initialization is stable and does not reuse prior state.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

# Note: pgvector fixtures are registered at the top-level tests/conftest.py.


@pytest.fixture(autouse=True, scope="session")
def vectorstores_isolated_env():
    # Enable test mode signals for API code paths
    prev_test_mode = os.getenv("TEST_MODE")
    os.environ["TEST_MODE"] = "true"
    # Force stubbed Chroma client for CI stability
    prev_force_stub = os.getenv("CHROMADB_FORCE_STUB")
    os.environ["CHROMADB_FORCE_STUB"] = "true"

    # Create a fresh base dir for USER_DB_BASE_DIR used by ChromaDBManager
    tmp_base = tempfile.mkdtemp(prefix="vs_chroma_base_")
    try:
        # Patch settings at import time to avoid reusing any existing path
        from tldw_Server_API.app.core.config import settings
        settings["USER_DB_BASE_DIR"] = Path(tmp_base)
        try:
            from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import reset_media_db_cache

            reset_media_db_cache()
        except Exception:
            pass
        # Ensure vector batches DB is initialized for the default user
        try:
            from tldw_Server_API.app.core.Embeddings.vector_store_batches_db import init_db as _init_batches
            uid = str(settings.get("SINGLE_USER_FIXED_ID", "1"))
            _init_batches(uid)
        except Exception:
            pass
        yield
    finally:
        # Restore TEST_MODE env
        if prev_test_mode is None:
            os.environ.pop("TEST_MODE", None)
        else:
            os.environ["TEST_MODE"] = prev_test_mode
        if prev_force_stub is None:
            os.environ.pop("CHROMADB_FORCE_STUB", None)
        else:
            os.environ["CHROMADB_FORCE_STUB"] = prev_force_stub
        # Cleanup temporary directory
        try:
            shutil.rmtree(tmp_base, ignore_errors=True)
        except Exception:
            pass


# Local admin_user fixture (avoid importing other conftests that override pgvector_dsn)
@pytest.fixture
def admin_user():
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User

    async def _admin():
        return User(id=42, username="admin", email="a@x", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = _admin
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_request_user, None)
