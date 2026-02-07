import json
import pytest
from datetime import datetime, timedelta

from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase


def _seed_evaluations(db: EvaluationsDatabase, rows: list[dict]) -> None:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        for row in rows:
            cursor.execute(
                """
                INSERT INTO evaluations (
                    id, name, description, eval_type, eval_spec,
                    dataset_id, created_at, created_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["name"],
                    row.get("description"),
                    row["eval_type"],
                    json.dumps(row["eval_spec"]),
                    row.get("dataset_id"),
                    row["created_at"],
                    row.get("created_by"),
                    json.dumps(row.get("metadata", {})),
                ),
            )
        conn.commit()


@pytest.mark.unit
def test_list_evaluations_filtered_by_user_and_date(tmp_path):
    db = EvaluationsDatabase(str(tmp_path / "evals.db"))
    now = datetime.utcnow().replace(microsecond=0)
    older = now - timedelta(days=2)
    recent = now - timedelta(hours=12)

    rows = [
        {
            "id": "eval_old_a",
            "name": "old_a",
            "description": "old",
            "eval_type": "model_graded",
            "eval_spec": {"metrics": ["accuracy"], "threshold": 0.7},
            "dataset_id": "dataset_old",
            "created_at": older.isoformat(sep=" "),
            "created_by": "user_a",
        },
        {
            "id": "eval_recent_a",
            "name": "recent_a",
            "description": "recent",
            "eval_type": "model_graded",
            "eval_spec": {"metrics": ["accuracy"], "threshold": 0.7},
            "dataset_id": "dataset_recent",
            "created_at": recent.isoformat(sep=" "),
            "created_by": "user_a",
        },
        {
            "id": "eval_recent_b",
            "name": "recent_b",
            "description": "recent",
            "eval_type": "model_graded",
            "eval_spec": {"metrics": ["accuracy"], "threshold": 0.7},
            "dataset_id": "dataset_recent_b",
            "created_at": recent.isoformat(sep=" "),
            "created_by": "user_b",
        },
    ]

    _seed_evaluations(db, rows)

    items = db.list_evaluations_filtered(
        limit=10,
        offset=0,
        created_by="user_a",
        start_date=now - timedelta(days=1),
        end_date=now,
    )

    assert len(items) == 1
    assert items[0]["id"] == "eval_recent_a"


@pytest.mark.unit
def test_count_evaluations_filtered_by_user(tmp_path):
    db = EvaluationsDatabase(str(tmp_path / "evals.db"))
    now = datetime.utcnow().replace(microsecond=0)

    rows = [
        {
            "id": "eval_a_1",
            "name": "a1",
            "description": "a1",
            "eval_type": "exact_match",
            "eval_spec": {"threshold": 1.0},
            "dataset_id": "dataset_a1",
            "created_at": now.isoformat(sep=" "),
            "created_by": "user_a",
        },
        {
            "id": "eval_a_2",
            "name": "a2",
            "description": "a2",
            "eval_type": "exact_match",
            "eval_spec": {"threshold": 1.0},
            "dataset_id": "dataset_a2",
            "created_at": now.isoformat(sep=" "),
            "created_by": "user_a",
        },
        {
            "id": "eval_b_1",
            "name": "b1",
            "description": "b1",
            "eval_type": "exact_match",
            "eval_spec": {"threshold": 1.0},
            "dataset_id": "dataset_b1",
            "created_at": now.isoformat(sep=" "),
            "created_by": "user_b",
        },
    ]

    _seed_evaluations(db, rows)

    assert db.count_evaluations_filtered(created_by="user_a") == 2
    assert db.count_evaluations_filtered(created_by="user_b") == 1
