from __future__ import annotations

import hashlib
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional
import uuid

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

try:  # Optional dependency; Postgres tests are skipped when unavailable (prefer psycopg v3)
    import psycopg as _psycopg_v3  # type: ignore
    _PG_DRIVER = "psycopg"
except Exception:  # pragma: no cover - the skip hook handles missing driver
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


@dataclass
class DualBackendEnv:
    """Container for the dual-backend regression fixtures."""

    label: str
    media_db: MediaDatabase
    chacha_db: CharactersRAGDB


def _create_temp_postgres_database(config: DatabaseConfig) -> DatabaseConfig:
    """Create a temporary Postgres database for this test and return a config pointing to it."""

    assert _PG_DRIVER is not None
    temp_db = f"tldw_test_{uuid.uuid4().hex[:8]}"
    if _PG_DRIVER == "psycopg":
        admin_conn = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    else:
        admin_conn = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE {temp_db} OWNER {config.pg_user};")
    finally:
        admin_conn.close()

    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=config.pg_host,
        pg_port=config.pg_port,
        pg_database=temp_db,
        pg_user=config.pg_user,
        pg_password=config.pg_password,
    )


def _drop_postgres_database(config: DatabaseConfig) -> None:
    """Drop the temporary Postgres database created for this test."""
    assert _PG_DRIVER is not None
    if _PG_DRIVER == "psycopg":
        admin_conn = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    else:
        admin_conn = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            # terminate existing connections to allow drop
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s;",
                (config.pg_database,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {config.pg_database};")
    finally:
        admin_conn.close()


def _build_postgres_config() -> DatabaseConfig:
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.environ["POSTGRES_TEST_HOST"],
        pg_port=int(os.environ["POSTGRES_TEST_PORT"]),
        pg_database=os.environ["POSTGRES_TEST_DB"],
        pg_user=os.environ["POSTGRES_TEST_USER"],
        pg_password=os.environ["POSTGRES_TEST_PASSWORD"],
    )


@pytest.fixture(params=["sqlite", "postgres"])
def dual_backend_env(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[DualBackendEnv]:
    """Yield Media + ChaCha database instances for the requested backend."""

    label: str = request.param
    media_db: Optional[MediaDatabase] = None
    chacha_db: Optional[CharactersRAGDB] = None

    if label == "sqlite":
        # Use file-backed DBs under pytest tmp_path so migration helper can operate
        media_path = tmp_path / "media.sqlite"
        chacha_path = tmp_path / "chacha.sqlite"
        media_db = MediaDatabase(db_path=str(media_path), client_id="dual-sqlite-media")
        chacha_db = CharactersRAGDB(db_path=str(chacha_path), client_id="dual-sqlite-chacha")
    else:  # postgres
        # Build base config from env or fall back to compose defaults, then create a temp DB
        base_config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=os.getenv("POSTGRES_TEST_HOST", "127.0.0.1"),
            pg_port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
            pg_database=os.getenv("POSTGRES_TEST_DB", "tldw_users"),
            pg_user=os.getenv("POSTGRES_TEST_USER", "tldw_user"),
            pg_password=os.getenv("POSTGRES_TEST_PASSWORD", "TestPassword123!"),
        )
        config = _create_temp_postgres_database(base_config)

        media_backend = DatabaseBackendFactory.create_backend(config)
        chacha_backend = DatabaseBackendFactory.create_backend(config)

        media_db = MediaDatabase(db_path=":memory:", client_id="dual-postgres-media", backend=media_backend)
        chacha_db = CharactersRAGDB(db_path=":memory:", client_id="dual-postgres-chacha", backend=chacha_backend)

    try:
        yield DualBackendEnv(label=label, media_db=media_db, chacha_db=chacha_db)
    finally:
        if chacha_db is not None:
            chacha_db.close_connection()
            if chacha_db.backend_type == BackendType.POSTGRESQL:
                chacha_db.backend.get_pool().close_all()

        if media_db is not None:
            media_db.close_connection()
            if media_db.backend_type == BackendType.POSTGRESQL:
                media_db.backend.get_pool().close_all()

        if label == "postgres":
            try:
                _drop_postgres_database(config)  # type: ignore[name-defined]
            except Exception:
                pass


@pytest.fixture
def deterministic_embeddings(monkeypatch: pytest.MonkeyPatch):
    """Patch embedding helpers to produce deterministic vectors for regression tests."""

    def _create_embeddings_batch(texts, config, metadata):  # noqa: ANN001 - external signature contract
        vectors = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
            rng = random.Random(seed)
            vectors.append([round(rng.uniform(-1.0, 1.0), 6) for _ in range(16)])
        return vectors

    def _get_embedding_config():  # noqa: ANN001 - matches production helper
        return {"provider": "deterministic-test"}

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch",
        _create_embeddings_batch,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.get_embedding_config",
        _get_embedding_config,
        raising=False,
    )

    return _create_embeddings_batch
