import os
import uuid
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import ClaimsRetriever

try:
    import psycopg as _psycopg_v3  # type: ignore
    _PG_DRIVER = "psycopg"
except Exception:  # pragma: no cover - optional dependency
    try:
        import psycopg2 as _psycopg2  # type: ignore
        _PG_DRIVER = "psycopg2"
    except Exception:
        _PG_DRIVER = None


HAS_POSTGRES = (_PG_DRIVER is not None)


def _reset_postgres_database(config: DatabaseConfig) -> None:
    assert _PG_DRIVER is not None
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


def _bootstrap_media_record(db: MediaDatabase, *, claim_text: str) -> None:
    media_id, _uuid, _hash = db.add_media_with_keywords(
        title="Dual Backend Media",
        media_type="text",
        content="This is a backend parity test document.",
        keywords=["parity", "postgres"],
    )
    assert media_id is not None

    db.upsert_claims(
        [
            {
                "media_id": media_id,
                "chunk_index": 0,
                "claim_text": claim_text,
                "chunk_hash": f"chunk-{uuid.uuid4()}",
                "extractor": "pytest",
                "extractor_version": "v1",
            }
        ]
    )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("backend_label", ["sqlite", "postgres"])
async def test_claims_retrieval_backend_parity(backend_label: str, tmp_path: Path, pg_eval_params) -> None:
    """Ensure ClaimsRetriever returns results for both SQLite and PostgreSQL deployments."""

    db_path = tmp_path / "media.db"
    backend = None

    if backend_label == "postgres":
        params = pg_eval_params
        config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=params["host"],
            pg_port=int(params["port"]),
            pg_database=params["database"],
            pg_user=params["user"],
            pg_password=params.get("password"),
        )
        _reset_postgres_database(config)
        backend = DatabaseBackendFactory.create_backend(config)
        db_path = Path(":memory:")

    db = MediaDatabase(db_path=str(db_path), client_id=f"dual-{backend_label}", backend=backend)

    try:
        _bootstrap_media_record(db, claim_text="Backend migrations succeed across databases.")

        retriever = ClaimsRetriever(str(db_path), media_db=db)
        results = await retriever.retrieve("migrations succeed")

        assert results, f"Expected at least one claim result for backend {backend_label}"
        assert any("migrations" in doc.content for doc in results)
    finally:
        db.close_connection()
