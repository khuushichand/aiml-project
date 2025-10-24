import sqlite3
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Embeddings_Jobs_DB import (
    EmbeddingsJobsDatabase,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "embeddings_jobs.db"


def test_embeddings_jobs_db_initializes_without_index_errors(db_path: Path) -> None:
    EmbeddingsJobsDatabase(str(db_path))

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            ("idx_embedding_jobs_user_id",),
        )
        assert cursor.fetchone() is not None


def test_create_job_enforces_concurrent_limit(db_path: Path) -> None:
    db = EmbeddingsJobsDatabase(str(db_path))
    user_id = "user-123"
    base_job = {
        "job_id": "job-1",
        "user_id": user_id,
        "media_id": 1,
        "status": "pending",
        "priority": 50,
        "user_tier": "free",
        "model_name": "example",
        "chunking_config": None,
        "metadata": None,
    }

    db.get_or_create_user_quota(user_id)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE user_quotas
            SET concurrent_jobs_limit = 1
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()

    assert db.create_job(base_job) is True

    second_job = dict(base_job, job_id="job-2")
    assert db.create_job(second_job) is False
    assert db.get_job("job-2") is None

    quota_after = db.get_or_create_user_quota(user_id)
    assert quota_after["concurrent_jobs_active"] == 1


def test_create_job_rolls_back_concurrency_on_insert_failure(db_path: Path) -> None:
    db = EmbeddingsJobsDatabase(str(db_path))
    user_id = "user-duplicate"

    base_job = {
        "job_id": "duplicate-job",
        "user_id": user_id,
        "media_id": 1,
        "status": "pending",
        "priority": 50,
        "user_tier": "free",
        "model_name": "example",
        "chunking_config": None,
        "metadata": None,
    }

    assert db.create_job(base_job) is True

    # Second attempt uses the same job_id and should trigger a unique constraint violation.
    duplicate_job = dict(base_job)
    assert db.create_job(duplicate_job) is False

    quota_after = db.get_or_create_user_quota(user_id)
    assert quota_after["concurrent_jobs_active"] == 1


def test_check_and_update_quota_handles_missing_reset(db_path: Path) -> None:
    db = EmbeddingsJobsDatabase(str(db_path))
    user_id = "quota-user"
    db.get_or_create_user_quota(user_id)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE user_quotas
            SET daily_reset_time = NULL,
                daily_chunks_used = 5
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()

    assert db.check_and_update_quota(user_id, 10) is True
    quota = db.get_or_create_user_quota(user_id)
    assert quota["daily_chunks_used"] == 10

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE user_quotas
            SET daily_reset_time = 'invalid timestamp'
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()

    assert db.check_and_update_quota(user_id, 5) is True
    quota_after = db.get_or_create_user_quota(user_id)
    assert quota_after["daily_chunks_used"] == 5
