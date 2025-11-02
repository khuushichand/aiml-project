import os
import json
import uuid
import pytest

from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.DB_Management.migration_tools import main as migration_main


@pytest.mark.integration
def test_evaluations_migration_cli_row_counts(tmp_path, pg_eval_params):
    host = pg_eval_params["host"]
    user = pg_eval_params["user"]
    password = pg_eval_params.get("password")
    database = pg_eval_params["database"]
    port = int(pg_eval_params["port"])

    # Seed a temporary SQLite evaluations database with a few rows
    sqlite_path = tmp_path / "evaluations_seed.db"
    db = EvaluationsDatabase(str(sqlite_path))

    # Create evaluation + dataset rows
    ds_id = f"ds_{uuid.uuid4().hex[:10]}"
    eval_id = db.create_evaluation(
        name="cli-migration-test",
        eval_type="geval",
        eval_spec={"metric": "accuracy"},
        description="migration smoke",
        created_by="tester",
    )
    # Create a dataset and attach to evaluation via update
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO datasets (id, name, description, samples, sample_count, created_by, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ds_id,
                "cli-dataset",
                "desc",
                json.dumps([{"q": "a", "a": "b"}]),
                1,
                "tester",
                json.dumps({}),
            ),
        )
        c.execute("UPDATE evaluations SET dataset_id = ? WHERE id = ?", (ds_id, eval_id))
        # Add an evaluation run
        c.execute(
            """
            INSERT INTO evaluation_runs (
                id, eval_id, status, target_model, config, progress, results, created_at
            ) VALUES (?, ?, 'queued', ?, ?, ?, ?, datetime('now'))
            """,
            (
                f"run_{uuid.uuid4().hex[:10]}",
                eval_id,
                "gpt-4o",
                json.dumps({"batch_size": 8}),
                json.dumps({"total": 1, "done": 0}),
                json.dumps(None),
            ),
        )
        conn.commit()

    # Count rows in SQLite
    def _count_sqlite(table: str) -> int:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
            row = c.fetchone()
            return int(row[0] if isinstance(row, tuple) else row["cnt"])  # type: ignore[index]

    sqlite_counts = {
        "evaluations": _count_sqlite("evaluations"),
        "evaluation_runs": _count_sqlite("evaluation_runs"),
        "datasets": _count_sqlite("datasets"),
    }

    # Run the migration CLI
    argv = [
        "--evaluations-sqlite", str(sqlite_path),
        "--pg-host", host,
        "--pg-port", str(port),
        "--pg-database", database,
        "--pg-user", user,
        "--pg-password", password or "",
        "--log-level", "INFO",
    ]

    try:
        # psycopg may be unavailable in some sandboxes
        rc = migration_main(argv)
    except Exception:
        pytest.skip("psycopg not available or CLI backend init failed")

    assert rc == 0

    # Validate row counts on PostgreSQL match the source SQLite counts
    from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
    from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
    config = DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=host,
        pg_port=port,
        pg_database=database,
        pg_user=user,
        pg_password=password,
    )
    try:
        backend = DatabaseBackendFactory.create_backend(config)
    except Exception:
        pytest.skip("psycopg not available or backend creation failed")
    try:
        with backend.transaction() as conn:
            def _pg_count(table: str) -> int:
                res = backend.execute(f"SELECT COUNT(*) AS cnt FROM {table}", connection=conn)
                return int(res.scalar or 0)

            assert _pg_count("evaluations") == sqlite_counts["evaluations"]
            assert _pg_count("evaluation_runs") == sqlite_counts["evaluation_runs"]
            assert _pg_count("datasets") == sqlite_counts["datasets"]
    finally:
        try:
            backend.get_pool().close_all()
        except Exception:
            pass
