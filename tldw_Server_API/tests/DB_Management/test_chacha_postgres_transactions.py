from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

try:  # Optional dependency; mirror existing Postgres test patterns
    import psycopg as _psycopg_v3  # type: ignore
    _PG_DRIVER = "psycopg"
except Exception:  # pragma: no cover - fall back to psycopg2 if available
    try:
        import psycopg2 as _psycopg2  # type: ignore
        _PG_DRIVER = "psycopg2"
    except Exception:
        _PG_DRIVER = None


pytestmark = pytest.mark.skipif(_PG_DRIVER is None, reason="Postgres driver not installed")


@dataclass
class TempPostgresConfig:
    """Holds the temporary database configuration and admin connection details."""

    config: DatabaseConfig
    admin_db: str


def _base_postgres_config() -> DatabaseConfig:
    """Build a Postgres config using env overrides with sensible defaults."""

    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.getenv("POSTGRES_TEST_HOST", "127.0.0.1"),
        pg_port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
        pg_database=os.getenv("POSTGRES_TEST_DB", "tldw_users"),
        pg_user=os.getenv("POSTGRES_TEST_USER", "tldw_user"),
        pg_password=os.getenv("POSTGRES_TEST_PASSWORD", "TestPassword123!"),
    )


def _create_temp_postgres_database(base: DatabaseConfig) -> TempPostgresConfig:
    """Create a throwaway Postgres database for test isolation."""

    assert _PG_DRIVER is not None
    admin_db = os.getenv("POSTGRES_TEST_ADMIN_DB", "postgres")
    temp_db = f"tldw_test_{uuid.uuid4().hex[:8]}"

    if _PG_DRIVER == "psycopg":
        admin_conn = _psycopg_v3.connect(
            host=base.pg_host,
            port=base.pg_port,
            dbname=admin_db,
            user=base.pg_user,
            password=base.pg_password,
        )
    else:
        admin_conn = _psycopg2.connect(
            host=base.pg_host,
            port=base.pg_port,
            database=admin_db,
            user=base.pg_user,
            password=base.pg_password,
        )
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{temp_db}" OWNER {base.pg_user}')
    finally:
        admin_conn.close()

    return TempPostgresConfig(
        config=DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=base.pg_host,
            pg_port=base.pg_port,
            pg_database=temp_db,
            pg_user=base.pg_user,
            pg_password=base.pg_password,
        ),
        admin_db=admin_db,
    )


def _drop_temp_postgres_database(temp: TempPostgresConfig) -> None:
    """Drop the temporary Postgres database created for the test."""

    assert _PG_DRIVER is not None
    config = temp.config
    if _PG_DRIVER == "psycopg":
        admin_conn = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname=temp.admin_db,
            user=config.pg_user,
            password=config.pg_password,
        )
    else:
        admin_conn = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database=temp.admin_db,
            user=config.pg_user,
            password=config.pg_password,
        )
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s;",
                (config.pg_database,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{config.pg_database}"')
    finally:
        admin_conn.close()


@pytest.mark.integration
def test_chacha_transaction_context_commits_if_available(tmp_path, pg_eval_params):
    base_config = DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=pg_eval_params["host"],
        pg_port=int(pg_eval_params["port"]),
        pg_database=pg_eval_params["database"],
        pg_user=pg_eval_params["user"],
        pg_password=pg_eval_params.get("password"),
    )

    try:
        temp_conf = _create_temp_postgres_database(base_config)
    except Exception as exc:
        pytest.skip(f"Unable to create Postgres test database: {exc}")

    backend = DatabaseBackendFactory.create_backend(temp_conf.config)
    db = CharactersRAGDB(db_path=":memory:", client_id="txn-chacha", backend=backend)

    try:
        card_id = db.add_character_card(
            {
                "name": f"txn-char-{uuid.uuid4()}",
                "description": "transactional character",
                "client_id": db.client_id,
            }
        )
        assert card_id is not None

        conversation_id = db.add_conversation(
            {
                "character_id": card_id,
                "title": "original title",
                "client_id": db.client_id,
            }
        )
        assert conversation_id is not None

        updated_title = "updated title"
        with db.transaction():
            db.execute_query(
                "UPDATE conversations SET title = ?, version = version + 1 WHERE id = ?",
                (updated_title, conversation_id),
            )

        db.close_connection()

        fetch_cursor = db.execute_query(
            "SELECT title FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = fetch_cursor.fetchone()
        assert row is not None and row["title"] == updated_title  # type: ignore[index]

        failing_conversation = str(uuid.uuid4())
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.execute_query(
                    "INSERT INTO conversations (id, root_id, character_id, client_id) VALUES (?, ?, ?, ?)",
                    (failing_conversation, failing_conversation, card_id, db.client_id),
                )
                raise RuntimeError("force rollback")

        db.close_connection()

        not_found_cursor = db.execute_query(
            "SELECT id FROM conversations WHERE id = ?",
            (failing_conversation,),
        )
        assert not_found_cursor.fetchone() is None
    finally:
        try:
            db.close_connection()
            if db.backend_type == BackendType.POSTGRESQL:
                db.backend.get_pool().close_all()
        finally:
            try:
                _drop_temp_postgres_database(temp_conf)
            except Exception:
                pass
