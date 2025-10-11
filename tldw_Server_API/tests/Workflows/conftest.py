"""Fixtures for dual-backend workflow tests."""

from __future__ import annotations

import os
from typing import Generator, Tuple

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

_HAS_POSTGRES = (_PG_DRIVER is not None) and all(env in os.environ for env in _POSTGRES_ENV_VARS)


def _build_postgres_config() -> DatabaseConfig:
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.environ["POSTGRES_TEST_HOST"],
        pg_port=int(os.environ["POSTGRES_TEST_PORT"]),
        pg_database=os.environ["POSTGRES_TEST_DB"],
        pg_user=os.environ["POSTGRES_TEST_USER"],
        pg_password=os.environ["POSTGRES_TEST_PASSWORD"],
    )


def _reset_postgres_database(config: DatabaseConfig) -> None:
    if _PG_DRIVER is None:  # pragma: no cover - guarded by skip
        raise RuntimeError("psycopg (or psycopg2) is required for postgres workflow tests")

    if _PG_DRIVER == "psycopg":
        conn = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname=config.pg_database,
            user=config.pg_user,
            password=config.pg_password,
        )
    else:
        conn = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database=config.pg_database,
            user=config.pg_user,
            password=config.pg_password,
        )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        conn.close()


@pytest.fixture(params=[
    "sqlite",
    pytest.param(
        "postgres",
        marks=pytest.mark.skipif(not _HAS_POSTGRES, reason="Postgres fixtures unavailable"),
    ),
])
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
        config = _build_postgres_config()
        _reset_postgres_database(config)
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
