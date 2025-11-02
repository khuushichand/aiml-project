import os
import json
import pytest

from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


def test_sqlite_evaluations_basic(tmp_path):
    db_path = tmp_path / "evaluations.db"
    db = EvaluationsDatabase(str(db_path))

    eval_id = db.create_evaluation(
        name="unit-sqlite",
        eval_type="geval",
        eval_spec={"metric": "accuracy"},
        description="sqlite smoke",
        created_by="tester",
    )
    assert isinstance(eval_id, str) and eval_id

    items, has_more = db.list_evaluations(limit=5)
    assert isinstance(items, list)
    assert any(it["id"] == eval_id for it in items)
    assert has_more in (True, False)


@pytest.mark.integration
def test_postgres_evaluations_basic_if_available(tmp_path):
    host = os.getenv("POSTGRES_TEST_HOST")
    user = os.getenv("POSTGRES_TEST_USER")
    password = os.getenv("POSTGRES_TEST_PASSWORD")
    database = os.getenv("POSTGRES_TEST_DATABASE", "tldw_content")
    port = int(os.getenv("POSTGRES_TEST_PORT", "5432"))

    if not host or not user:
        pytest.skip("Postgres test env not configured")

    try:
        config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=host,
            pg_port=port,
            pg_database=database,
            pg_user=user,
            pg_password=password,
        )
        backend = DatabaseBackendFactory.create_backend(config)
    except Exception:
        pytest.skip("psycopg not available or backend creation failed")

    db = EvaluationsDatabase(":memory:", backend=backend)

    eval_id = db.create_evaluation(
        name="unit-pg",
        eval_type="geval",
        eval_spec={"metric": "accuracy"},
        description="postgres smoke",
        created_by="tester",
    )
    assert isinstance(eval_id, str) and eval_id

    items, has_more = db.list_evaluations(limit=5)
    assert isinstance(items, list)
    assert any(it["id"] == eval_id for it in items)
    assert has_more in (True, False)
