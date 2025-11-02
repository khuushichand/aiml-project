import os
import json
import uuid
import pytest

from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


@pytest.mark.integration
def test_postgres_evaluations_crud_unified_if_available(tmp_path, pg_eval_params):
    try:
        cfg = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=pg_eval_params["host"],
            pg_port=int(pg_eval_params["port"]),
            pg_database=pg_eval_params["database"],
            pg_user=pg_eval_params["user"],
            pg_password=pg_eval_params.get("password"),
        )
        backend = DatabaseBackendFactory.create_backend(cfg)
    except Exception:
        pytest.skip("Postgres test env not configured or backend unavailable")

    db = EvaluationsDatabase(":memory:", backend=backend)

    # Create evaluation and verify fetch/list
    eval_id = db.create_evaluation(
        name="pg-crud",
        eval_type="geval",
        eval_spec={"metric": "rouge"},
        description="pg smoke",
        created_by="tester",
    )
    got = db.get_evaluation(eval_id)
    assert got and got["id"] == eval_id
    items, _ = db.list_evaluations(limit=10)
    assert any(row["id"] == eval_id for row in items)

    # Create a run and update status/progress
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    db.create_run(
        run_id=run_id,
        eval_id=eval_id,
        target_model="gpt-4o",
        config={"batch_size": 4},
    )
    db.update_run_status(run_id, "running")
    db.update_run_progress(run_id, {"total": 2, "done": 1})
    runs, _ = db.list_runs(eval_id, limit=10, return_has_more=True)
    assert any(r["id"] == run_id for r in runs)

    # Unified upsert path (evaluations_unified exists on PG by default)
    ok = db.store_unified_evaluation(
        evaluation_id=eval_id,
        name="pg-crud",
        evaluation_type="geval",
        input_data={"samples": 1},
        results={"score": 0.9},
        status="completed",
        user_id="tester",
        metadata={"k": "v"},
        embedding_provider="openai",
        embedding_model="text-embedding-3-large",
    )
    assert ok is True
    unified = db.get_unified_evaluation(eval_id)
    assert unified and (unified.get("evaluation_id") == eval_id or unified.get("id") == eval_id)


def test_sqlite_evaluations_unified_fallback(tmp_path):
    # SQLite path: unified table may not exist; fallback to internal_evaluations should still work
    db_path = tmp_path / "evaluations_fallback.db"
    db = EvaluationsDatabase(str(db_path))
    eval_id = db.create_evaluation(
        name="sqlite-fallback",
        eval_type="geval",
        eval_spec={"metric": "bleu"},
        description="sqlite smoke",
        created_by="tester",
    )
    ok = db.store_unified_evaluation(
        evaluation_id=eval_id,
        name="sqlite-fallback",
        evaluation_type="geval",
        input_data={"n": 1},
        results={"score": 0.5},
        status="completed",
        user_id="tester",
    )
    assert ok is True
    # Should find a record either in unified table (if created by migrations) or internal_evaluations fallback
    got = db.get_unified_evaluation(eval_id)
    assert got is not None
