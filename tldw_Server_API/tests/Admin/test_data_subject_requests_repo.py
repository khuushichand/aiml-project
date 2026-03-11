from __future__ import annotations

import os
import uuid

import pytest


def _setup_env(tmp_path) -> None:
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'users_test_dsr_repo.db'}"
    os.environ["TLDW_DB_ALLOWED_BASE_DIRS"] = str(tmp_path)
    os.environ["TLDW_DB_BACKUP_PATH"] = str(tmp_path / "backups")
    os.environ["USER_DB_BASE_DIR"] = str(tmp_path / "user_dbs")


@pytest.mark.asyncio
async def test_repo_create_request_is_idempotent(tmp_path):
    _setup_env(tmp_path)

    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.data_subject_requests_repo import (
        AuthnzDataSubjectRequestsRepo,
    )
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    await reset_db_pool()
    reset_settings()

    pool = await get_db_pool()
    await pool.execute(
        """
        INSERT INTO users (id, username, email, password_hash, role, is_active, uuid)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        1,
        "admin_requester",
        "admin_requester@example.com",
        "hash",
        "admin",
        1,
        str(uuid.uuid4()),
    )
    await pool.execute(
        """
        INSERT INTO users (id, username, email, password_hash, role, is_active, uuid)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        7,
        "subject_user",
        "subject_user@example.com",
        "hash",
        "user",
        1,
        str(uuid.uuid4()),
    )
    repo = AuthnzDataSubjectRequestsRepo(db_pool=pool)
    await repo.ensure_schema()

    first = await repo.create_or_get_request(
        client_request_id="dsr-1",
        requester_identifier="user@example.com",
        resolved_user_id=7,
        request_type="export",
        status="recorded",
        selected_categories=["media_records"],
        preview_summary=[{"key": "media_records", "count": 3}],
        coverage_metadata={"supported": ["media_records"]},
        requested_by_user_id=1,
        notes=None,
    )
    second = await repo.create_or_get_request(
        client_request_id="dsr-1",
        requester_identifier="user@example.com",
        resolved_user_id=7,
        request_type="export",
        status="recorded",
        selected_categories=["media_records"],
        preview_summary=[{"key": "media_records", "count": 3}],
        coverage_metadata={"supported": ["media_records"]},
        requested_by_user_id=1,
        notes=None,
    )

    assert first["id"] == second["id"]
    assert first["client_request_id"] == "dsr-1"
    assert first["request_type"] == "export"
    assert first["status"] == "recorded"
    assert first["selected_categories"] == ["media_records"]
    assert first["preview_summary"] == [{"key": "media_records", "count": 3}]

    rows, total = await repo.list_requests(limit=10, offset=0)
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["id"] == first["id"]
