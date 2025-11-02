import os
import tempfile
import pytest

from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


def test_evaluations_unified_sqlite_migration_and_crud(tmp_path):
    """
    Ensure unified evaluations table exists after SQLite migrations and basic
    CRUD works. This covers environments without Postgres.
    """
    db_file = tmp_path / "evals.db"
    db = EvaluationsDatabase(str(db_file))  # SQLite path

    # unified table present
    assert db._use_unified_table() is True

    # Basic CRUD
    eid = db.create_evaluation(
        name="t1",
        eval_type="geval",
        eval_spec={"k": 1},
        description="d",
        dataset_id=None,
        created_by="tester",
        metadata={"x": "y"},
    )
    obj = db.get_evaluation(eid)
    assert obj is not None
    assert obj["name"] == "t1"


@pytest.mark.skipif(
    os.getenv("TLDW_CONTENT_DB_BACKEND", "").strip().lower() not in {"postgres", "postgresql"},
    reason="PostgreSQL content backend not configured in this environment",
)
def test_evaluations_unified_postgres_presence():
    """
    Smoke test: when running against Postgres content backend, an EvaluationsDatabase
    should initialize without error and report unified table presence. Requires
    a configured Postgres instance and psycopg.
    """
    # The DB path is unused for Postgres-backed EvaluationsDatabase, but we pass a dummy path.
    db = EvaluationsDatabase(db_path="unused", backend=None)  # backend is auto-resolved in module
    assert db.backend_type in (BackendType.SQLITE, BackendType.POSTGRESQL)
    if db.backend_type == BackendType.POSTGRESQL:
        assert db._use_unified_table() is True
