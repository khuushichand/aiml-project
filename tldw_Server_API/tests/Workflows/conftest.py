"""Fixtures for dual-backend workflow tests."""

from __future__ import annotations

import os
from typing import Generator, Tuple
import uuid

import pytest

from tldw_Server_API.app.core.DB_Management.DB_Manager import (
    create_workflows_database,
)
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

try:
    import psycopg as _psycopg_v3  # type: ignore
    _PG_DRIVER = "psycopg"
except Exception:  # pragma: no cover - optional dependency
    try:
        import psycopg2 as _psycopg2  # type: ignore
        _PG_DRIVER = "psycopg2"
    except Exception:
        _PG_DRIVER = None

_POSTGRES_ENV_VARS = (
    "POSTGRES_TEST_HOST",
    "POSTGRES_TEST_PORT",
    "POSTGRES_TEST_DB",
    "POSTGRES_TEST_USER",
    "POSTGRES_TEST_PASSWORD",
)

_HAS_POSTGRES = (_PG_DRIVER is not None)


def _build_postgres_config() -> DatabaseConfig:
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.environ["POSTGRES_TEST_HOST"],
        pg_port=int(os.environ["POSTGRES_TEST_PORT"]),
        pg_database=os.environ["POSTGRES_TEST_DB"],
        pg_user=os.environ["POSTGRES_TEST_USER"],
        pg_password=os.environ["POSTGRES_TEST_PASSWORD"],
    )


def _create_temp_postgres_database(config: DatabaseConfig) -> DatabaseConfig:
    """Create a temporary database for this test and return a derived config."""
    if _PG_DRIVER is None:  # pragma: no cover - guarded by skip
        raise RuntimeError("psycopg (or psycopg2) is required for postgres workflow tests")

    db_name = f"tldw_test_{uuid.uuid4().hex[:8]}"
    if _PG_DRIVER == "psycopg":
        admin = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    else:
        admin = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(f"CREATE DATABASE {db_name} OWNER {config.pg_user};")
    finally:
        admin.close()

    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=config.pg_host,
        pg_port=config.pg_port,
        pg_database=db_name,
        pg_user=config.pg_user,
        pg_password=config.pg_password,
    )


def _drop_postgres_database(config: DatabaseConfig) -> None:
    if _PG_DRIVER is None:  # pragma: no cover
        return
    if _PG_DRIVER == "psycopg":
        admin = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    else:
        admin = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s;",
                (config.pg_database,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {config.pg_database};")
    finally:
        admin.close()


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
        base_config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=os.getenv("POSTGRES_TEST_HOST", "127.0.0.1"),
            pg_port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
            pg_database=os.getenv("POSTGRES_TEST_DB", "tldw_users"),
            pg_user=os.getenv("POSTGRES_TEST_USER", "tldw_user"),
            pg_password=os.getenv("POSTGRES_TEST_PASSWORD", "TestPassword123!"),
        )
        config = _create_temp_postgres_database(base_config)
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
        if label == "postgres":
            try:
                _drop_postgres_database(config)  # type: ignore[name-defined]
            except Exception:
                pass
