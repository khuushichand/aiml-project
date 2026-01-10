"""Fixtures for dual-backend workflow tests."""

from __future__ import annotations

import os
from typing import Generator, Tuple
import uuid

import pytest

# Note: pytest >= 8 forbids defining `pytest_plugins` in non top-level
# conftest files. The unified Postgres fixtures are loaded globally via
# `pyproject.toml` under `[tool.pytest.ini_options].plugins`.

from tldw_Server_API.app.core.DB_Management.DB_Manager import (
    create_workflows_database,
)
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@pytest.fixture()
def auth_headers():
     settings = get_settings()
    return {"X-API-KEY": settings.SINGLE_USER_API_KEY}


@pytest.fixture(params=["sqlite", "postgres"])
def workflows_dual_backend_db(
    request: pytest.FixtureRequest,
    tmp_path,
) -> Generator[Tuple[str, object], None, None]:
    """Yield workflow database instances for both SQLite and PostgreSQL backends."""

    label: str = request.param
    backend = None

    if label == "sqlite":
        db_path = tmp_path / "workflows_sqlite.db"
        db_instance = create_workflows_database(db_path=db_path, backend=None)
    else:
        # Resolve unified pg temp database config only for the postgres branch
        config: DatabaseConfig = request.getfixturevalue("pg_database_config")
        backend = DatabaseBackendFactory.create_backend(config)
        db_instance = create_workflows_database(
            db_path=tmp_path / "workflows_pg_placeholder.db",
            backend=backend,
        )

    try:
        yield label, db_instance
    finally:
        if backend is not None:
            try:
                backend.get_pool().close_all()
            except Exception:
                pass
        # No explicit drop; pg_database_config fixture cleans up the temp DB
