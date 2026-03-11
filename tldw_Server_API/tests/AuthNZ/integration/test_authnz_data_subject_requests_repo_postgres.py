from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_data_subject_requests_repo_idempotent_postgres(
    isolated_test_environment,
):
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.data_subject_requests_repo import (
        AuthnzDataSubjectRequestsRepo,
    )
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB

    client, _db_name = isolated_test_environment
    assert client is not None

    pool = await get_db_pool()
    users_db = UsersDB(pool)
    await users_db.initialize()

    requested_by = await users_db.create_user(
        username="dsr_admin_pg",
        email="dsr_admin_pg@example.com",
        password_hash="hash",
        role="admin",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
    )
    subject = await users_db.create_user(
        username="dsr_subject_pg",
        email="dsr_subject_pg@example.com",
        password_hash="hash",
        role="user",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
    )

    repo = AuthnzDataSubjectRequestsRepo(db_pool=pool)
    await repo.ensure_schema()

    first = await repo.create_or_get_request(
        client_request_id="pg-dsr-1",
        requester_identifier="dsr_subject_pg@example.com",
        resolved_user_id=int(subject["id"]),
        request_type="access",
        status="recorded",
        selected_categories=["media_records", "chat_messages"],
        preview_summary=[
            {"key": "media_records", "count": 4},
            {"key": "chat_messages", "count": 9},
        ],
        coverage_metadata={"supported": ["media_records", "chat_messages"]},
        requested_by_user_id=int(requested_by["id"]),
        notes="repo integration",
    )
    second = await repo.create_or_get_request(
        client_request_id="pg-dsr-1",
        requester_identifier="dsr_subject_pg@example.com",
        resolved_user_id=int(subject["id"]),
        request_type="access",
        status="recorded",
        selected_categories=["media_records", "chat_messages"],
        preview_summary=[
            {"key": "media_records", "count": 4},
            {"key": "chat_messages", "count": 9},
        ],
        coverage_metadata={"supported": ["media_records", "chat_messages"]},
        requested_by_user_id=int(requested_by["id"]),
        notes="repo integration",
    )

    assert first["id"] == second["id"]
    rows, total = await repo.list_requests(limit=10, offset=0)
    assert total == 1
    assert rows[0]["client_request_id"] == "pg-dsr-1"
